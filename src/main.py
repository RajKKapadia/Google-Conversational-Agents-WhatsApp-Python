from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, Header
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel

from src import logging
from src.config import WEBHOOK_VERIFICATION_TOKEN
from src.models import WebhookPayload, MessageType, MediaMessage, LocationMessage, Contact
from src.queue import init_pool, close_pool, enqueue_message_task
from src.security import verify_webhook_signature
from src.whatsapp_client import get_whatsapp_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage Redis pool lifecycle."""
    await init_pool()
    yield
    await close_pool()


app = FastAPI(title="CA WhatsApp Integration", lifespan=lifespan)


def _serialize_content(content) -> str | dict | list | None:
    """Serialize message content for queue transport."""
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, BaseModel):
        return content.model_dump()
    if isinstance(content, list):
        return [item.model_dump() if isinstance(item, BaseModel) else item for item in content]
    return None


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "service": "CA WhatsApp Integration",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "webhook_verification": "GET /webhook",
            "webhook_messages": "POST /webhook",
            "health": "GET /health",
        },
        "session_format": "meta-whatsapp-{user_id}",
        "description": "WhatsApp webhook integration with Google Conversational Agents and Gemini AI",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "CA WhatsApp Integration",
    }


@app.get("/webhook", response_class=PlainTextResponse)
async def handle_get_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    """
    Webhook verification endpoint for Meta WhatsApp.
    Meta sends a GET request with hub.mode, hub.verify_token, and hub.challenge.
    We verify the token and return the challenge if valid.
    """
    logger.info(f"Webhook verification request received: mode={hub_mode}")

    if hub_mode == "subscribe" and hub_verify_token == WEBHOOK_VERIFICATION_TOKEN:
        logger.info("Webhook verification successful")
        return hub_challenge

    logger.warning(f"Webhook verification failed: mode={hub_mode}, token_match={hub_verify_token == WEBHOOK_VERIFICATION_TOKEN}")
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def handle_post_webhook(
    request: Request,
    x_hub_signature_256: str = Header(alias="X-Hub-Signature-256"),
):
    """
    Webhook endpoint for receiving WhatsApp messages.
    Verifies the request signature, marks messages as read,
    and enqueues them for async processing via ARQ.
    """
    raw_body = await request.body()

    if not verify_webhook_signature(raw_body, x_hub_signature_256):
        logger.warning("Webhook signature verification failed")
        raise HTTPException(status_code=403, detail="Invalid signature")

    logger.info("Webhook signature verified successfully")

    try:
        payload = WebhookPayload.model_validate_json(raw_body)
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")

    logger.info(f"Received webhook for object: {payload.object}")

    messages = payload.get_messages()
    phone_number_id = payload.get_phone_number_id()

    if not messages:
        logger.info("No messages in webhook payload (might be status update)")
        return JSONResponse(content={"status": "ok"}, status_code=200)

    logger.info(f"Processing {len(messages)} message(s) from phone_number_id: {phone_number_id}")

    whatsapp_client = get_whatsapp_client()

    for message in messages:
        message_type = message.get_message_type()
        content = message.get_content()
        sender = message.from_

        logger.info(
            f"Message received - ID: {message.id}, From: {sender}, "
            f"Type: {message_type.value}, Timestamp: {message.timestamp}"
        )

        # Mark as read immediately (non-critical, best-effort)
        await whatsapp_client.mark_message_as_read(message.id)

        # Serialize and enqueue for async processing
        serialized = _serialize_content(content)
        await enqueue_message_task(sender, message_type.value, serialized, message.id)

    return JSONResponse(content={"status": "ok"}, status_code=200)
