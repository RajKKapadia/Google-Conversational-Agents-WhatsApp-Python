from fastapi import FastAPI, HTTPException, Query, Request, Header
from fastapi.responses import PlainTextResponse, JSONResponse

from src import logging
from src.config import WEBHOOK_VERIFICATION_TOKEN
from src.models import WebhookPayload, MessageType
from src.security import verify_webhook_signature
from src.ca_client import get_ca_client
from src.gemini_client import get_gemini_client
from src.whatsapp_client import get_whatsapp_client

app = FastAPI(title="CA WhatsApp Integration")


logger = logging.getLogger(__name__)


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

    # Check if mode is 'subscribe' and verify token matches
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
    Verifies the request signature and processes incoming messages.
    """
    # Get raw body for signature verification
    raw_body = await request.body()

    # Verify webhook signature
    if not verify_webhook_signature(raw_body, x_hub_signature_256):
        logger.warning("Webhook signature verification failed")
        raise HTTPException(status_code=403, detail="Invalid signature")

    logger.info("Webhook signature verified successfully")

    # Parse the webhook payload
    try:
        payload = WebhookPayload.model_validate_json(raw_body)
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid payload: {str(e)}")

    logger.info(f"Received webhook for object: {payload.object}")

    # Extract and process messages
    messages = payload.get_messages()
    phone_number_id = payload.get_phone_number_id()

    if not messages:
        logger.info("No messages in webhook payload (might be status update)")
        return JSONResponse(content={"status": "ok"}, status_code=200)

    logger.info(f"Processing {len(messages)} message(s) from phone_number_id: {phone_number_id}")

    # Process each message
    for message in messages:
        message_type = message.get_message_type()
        content = message.get_content()
        sender = message.from_

        logger.info(
            f"Message received - ID: {message.id}, From: {sender}, "
            f"Type: {message_type.value}, Timestamp: {message.timestamp}"
        )

        # Route based on message type
        if message_type == MessageType.TEXT:
            await handle_text_message(sender, content, message.id)
        elif message_type == MessageType.IMAGE:
            await handle_image_message(sender, content, message.id)
        elif message_type == MessageType.DOCUMENT:
            await handle_document_message(sender, content, message.id)
        elif message_type == MessageType.AUDIO or message_type == MessageType.VOICE:
            await handle_audio_message(sender, content, message.id)
        elif message_type == MessageType.VIDEO:
            await handle_video_message(sender, content, message.id)
        elif message_type == MessageType.LOCATION:
            await handle_location_message(sender, content, message.id)
        elif message_type == MessageType.CONTACTS:
            await handle_contacts_message(sender, content, message.id)
        else:
            logger.warning(f"Unsupported message type: {message_type.value}")
            await handle_unsupported_message(sender, message_type.value, message.id)

    # Return 200 OK to acknowledge receipt
    return JSONResponse(content={"status": "ok"}, status_code=200)


async def handle_text_message(sender: str, content: str, message_id: str):
    """Handle incoming text messages using Conversational Agents"""
    logger.info(f"Text message from {sender}: {content}")

    try:
        # Mark message as read
        whatsapp_client = get_whatsapp_client()
        await whatsapp_client.mark_message_as_read(message_id)

        # Detect intent using Conversational Agent
        ca_client = get_ca_client()
        result = await ca_client.detect_intent(text=content, user_id=sender)

        # Get the response from CA
        response_text = result["response_text"]

        # If no response from CA, log the details
        if not response_text:
            logger.warning(
                f"No response from CA - Intent: {result['intent']}, "
                f"Confidence: {result['confidence']}, Match Type: {result['match_type']}"
            )
            response_text = "I'm not sure how to help with that. Could you please rephrase?"

        # Send the response back to the user
        await whatsapp_client.send_text_message(sender, response_text)

        logger.info(
            f"CA response sent to {sender} - Intent: {result['intent']}, "
            f"Confidence: {result['confidence']:.2f}"
        )

    except Exception as e:
        logger.error(f"Error handling text message: {e}")
        # Send error message to user
        try:
            whatsapp_client = get_whatsapp_client()
            await whatsapp_client.send_text_message(
                sender, "Sorry, I encountered an error processing your message. Please try again."
            )
        except Exception:
            pass


async def handle_image_message(sender: str, content, message_id: str):
    """Handle incoming image messages"""
    logger.info(f"Image message from {sender}: media_id={content.id}, caption={content.caption}")

    try:
        # Mark message as read
        whatsapp_client = get_whatsapp_client()
        await whatsapp_client.mark_message_as_read(message_id)

        # Download the image from WhatsApp
        image_data, mime_type = await whatsapp_client.download_media(content.id)

        # Process the image with Gemini
        gemini_client = get_gemini_client()
        summary = await gemini_client.process_image(image_data, mime_type, content.caption)

        # Send the summary back to the user
        response_message = f"📸 Image Analysis:\n\n{summary}"
        await whatsapp_client.send_text_message(sender, response_message)

        logger.info(f"Image processed and response sent to {sender}")

    except Exception as e:
        logger.error(f"Error handling image message: {e}")
        # Send error message to user
        try:
            whatsapp_client = get_whatsapp_client()
            await whatsapp_client.send_text_message(
                sender, "Sorry, I encountered an error processing your image. Please try again."
            )
        except Exception:
            pass


async def handle_document_message(sender: str, content, message_id: str):
    """Handle incoming document messages"""
    logger.info(
        f"Document message from {sender}: media_id={content.id}, "
        f"filename={content.filename}, mime_type={content.mime_type}"
    )

    try:
        # Mark message as read
        whatsapp_client = get_whatsapp_client()
        await whatsapp_client.mark_message_as_read(message_id)

        # Download the document from WhatsApp
        document_data, mime_type = await whatsapp_client.download_media(content.id)

        # Process the document with Gemini
        gemini_client = get_gemini_client()
        summary = await gemini_client.process_document(document_data, mime_type, content.filename)

        # Send the summary back to the user
        response_message = f"📄 Document Summary:\n\n{summary}"
        if content.filename:
            response_message = f"📄 Document Summary ({content.filename}):\n\n{summary}"
        await whatsapp_client.send_text_message(sender, response_message)

        logger.info(f"Document processed and response sent to {sender}")

    except Exception as e:
        logger.error(f"Error handling document message: {e}")
        # Send error message to user
        try:
            whatsapp_client = get_whatsapp_client()
            await whatsapp_client.send_text_message(
                sender, "Sorry, I encountered an error processing your document. Please try again."
            )
        except Exception:
            pass


async def handle_audio_message(sender: str, content, message_id: str):
    """Handle incoming audio/voice messages"""
    logger.info(f"Audio message from {sender}: media_id={content.id}, mime_type={content.mime_type}")

    try:
        # Mark message as read
        whatsapp_client = get_whatsapp_client()
        await whatsapp_client.mark_message_as_read(message_id)

        # Download the audio from WhatsApp
        audio_data, mime_type = await whatsapp_client.download_media(content.id)

        # Process the audio with Gemini (transcription + summary)
        gemini_client = get_gemini_client()
        transcription = await gemini_client.process_audio(audio_data, mime_type)

        # Send the transcription back to the user
        response_message = f"🎤 Audio Transcription:\n\n{transcription}"
        await whatsapp_client.send_text_message(sender, response_message)

        logger.info(f"Audio processed and response sent to {sender}")

    except Exception as e:
        logger.error(f"Error handling audio message: {e}")
        # Send error message to user
        try:
            whatsapp_client = get_whatsapp_client()
            await whatsapp_client.send_text_message(
                sender, "Sorry, I encountered an error processing your audio. Please try again."
            )
        except Exception:
            pass


async def handle_video_message(sender: str, content, message_id: str):
    """Handle incoming video messages"""
    logger.info(f"Video message from {sender}: media_id={content.id}, caption={content.caption}")
    # TODO: Download and process video
    pass


async def handle_location_message(sender: str, content, message_id: str):
    """Handle incoming location messages"""
    logger.info(
        f"Location message from {sender}: lat={content.latitude}, "
        f"lon={content.longitude}, name={content.name}"
    )
    # TODO: Process location data
    pass


async def handle_contacts_message(sender: str, content: list, message_id: str):
    """Handle incoming contact messages"""
    logger.info(f"Contacts message from {sender}: {len(content)} contact(s)")
    # TODO: Process contact information
    pass


async def handle_unsupported_message(sender: str, message_type: str, message_id: str):
    """Handle unsupported message types"""
    logger.warning(f"Unsupported message type '{message_type}' from {sender}")
    # TODO: Send error message back to user
    pass
