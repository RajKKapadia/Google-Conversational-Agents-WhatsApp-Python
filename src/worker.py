"""
ARQ worker tasks and settings for async message processing.

Run with:  uv run arq src.worker.WorkerSettings
"""

from arq.connections import RedisSettings

from src import logging
from src.ca_client import get_ca_client
from src.config import REDIS_URL
from src.gemini_client import get_gemini_client
from src.models import Contact, LocationMessage, MediaMessage
from src.whatsapp_client import get_whatsapp_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Main task
# ---------------------------------------------------------------------------

async def process_message(
    ctx: dict,
    sender: str,
    message_type: str,
    content_data: str | dict | list | None,
    message_id: str,
) -> None:
    """Route an incoming message to the appropriate handler."""
    logger.info(f"Processing message {message_id} from {sender} (type={message_type})")

    try:
        handlers = {
            "text": _handle_text,
            "image": _handle_image,
            "document": _handle_document,
            "audio": _handle_audio,
            "voice": _handle_audio,
            "video": _handle_video,
            "location": _handle_location,
            "contacts": _handle_contacts,
        }

        handler = handlers.get(message_type)
        if handler is not None:
            await handler(sender, content_data, message_id)
        else:
            await _handle_unsupported(sender, message_type, message_id)

    except Exception as e:
        logger.error(f"Error processing message {message_id}: {e}")
        try:
            whatsapp_client = get_whatsapp_client()
            await whatsapp_client.send_text_message(
                sender,
                "Sorry, I encountered an error processing your message. Please try again.",
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Per-type handlers
# ---------------------------------------------------------------------------

async def _handle_text(sender: str, content_data: str, message_id: str) -> None:
    """Handle text messages using Conversational Agents."""
    logger.info(f"Text message from {sender}: {content_data}")

    ca_client = get_ca_client()
    result = await ca_client.detect_intent(text=content_data, user_id=sender)

    response_text = result["response_text"]
    if not response_text:
        logger.warning(
            f"No response from CA - Intent: {result['intent']}, "
            f"Confidence: {result['confidence']}, Match Type: {result['match_type']}"
        )
        response_text = "I'm not sure how to help with that. Could you please rephrase?"

    whatsapp_client = get_whatsapp_client()
    await whatsapp_client.send_text_message(sender, response_text)

    logger.info(
        f"CA response sent to {sender} - Intent: {result['intent']}, "
        f"Confidence: {result['confidence']:.2f}"
    )


async def _handle_image(sender: str, content_data: dict, message_id: str) -> None:
    """Handle image messages."""
    content = MediaMessage(**content_data)
    logger.info(f"Image message from {sender}: media_id={content.id}, caption={content.caption}")

    whatsapp_client = get_whatsapp_client()
    await whatsapp_client.send_text_message(sender, "Reading image...")

    image_data, mime_type = await whatsapp_client.download_media(content.id)

    gemini_client = get_gemini_client()
    summary = await gemini_client.process_image(image_data, mime_type, content.caption)
    logger.info(f"Image summarized by Gemini, forwarding to CA for {sender}")

    ca_client = get_ca_client()
    result = await ca_client.detect_intent(text=summary, user_id=sender)

    response_text = result["response_text"]
    if not response_text:
        logger.warning(
            f"No response from CA for image - Intent: {result['intent']}, "
            f"Confidence: {result['confidence']}, Match Type: {result['match_type']}"
        )
        response_text = "I'm not sure how to help with that. Could you please rephrase?"

    await whatsapp_client.send_text_message(sender, response_text)
    logger.info(f"Image processed via CA and response sent to {sender}")


async def _handle_document(sender: str, content_data: dict, message_id: str) -> None:
    """Handle document messages."""
    content = MediaMessage(**content_data)
    logger.info(
        f"Document message from {sender}: media_id={content.id}, "
        f"filename={content.filename}, mime_type={content.mime_type}"
    )

    whatsapp_client = get_whatsapp_client()
    await whatsapp_client.send_text_message(sender, "Reading document...")

    document_data, mime_type = await whatsapp_client.download_media(content.id)

    gemini_client = get_gemini_client()
    summary = await gemini_client.process_document(document_data, mime_type, content.filename)
    logger.info(f"Document summarized by Gemini, forwarding to CA for {sender}")

    ca_client = get_ca_client()
    result = await ca_client.detect_intent(text=summary, user_id=sender)

    response_text = result["response_text"]
    if not response_text:
        logger.warning(
            f"No response from CA for document - Intent: {result['intent']}, "
            f"Confidence: {result['confidence']}, Match Type: {result['match_type']}"
        )
        response_text = "I'm not sure how to help with that. Could you please rephrase?"

    await whatsapp_client.send_text_message(sender, response_text)
    logger.info(f"Document processed via CA and response sent to {sender}")


async def _handle_audio(sender: str, content_data: dict, message_id: str) -> None:
    """Handle audio/voice messages."""
    content = MediaMessage(**content_data)
    logger.info(f"Audio message from {sender}: media_id={content.id}, mime_type={content.mime_type}")

    whatsapp_client = get_whatsapp_client()
    await whatsapp_client.send_text_message(sender, "Listening to audio...")

    audio_data, mime_type = await whatsapp_client.download_media(content.id)

    gemini_client = get_gemini_client()
    transcription = await gemini_client.process_audio(audio_data, mime_type)
    logger.info(f"Audio transcribed by Gemini, forwarding to CA for {sender}")

    ca_client = get_ca_client()
    result = await ca_client.detect_intent(text=transcription, user_id=sender)

    response_text = result["response_text"]
    if not response_text:
        logger.warning(
            f"No response from CA for audio - Intent: {result['intent']}, "
            f"Confidence: {result['confidence']}, Match Type: {result['match_type']}"
        )
        response_text = "I'm not sure how to help with that. Could you please rephrase?"

    await whatsapp_client.send_text_message(sender, response_text)
    logger.info(f"Audio processed via CA and response sent to {sender}")


async def _handle_video(sender: str, content_data: dict, message_id: str) -> None:
    """Handle video messages."""
    content = MediaMessage(**content_data)
    logger.info(f"Video message from {sender}: media_id={content.id}, caption={content.caption}")
    # TODO: Download and process video


async def _handle_location(sender: str, content_data: dict, message_id: str) -> None:
    """Handle location messages."""
    content = LocationMessage(**content_data)
    logger.info(
        f"Location message from {sender}: lat={content.latitude}, "
        f"lon={content.longitude}, name={content.name}"
    )
    # TODO: Process location data


async def _handle_contacts(sender: str, content_data: list, message_id: str) -> None:
    """Handle contact messages."""
    contacts = [Contact(**c) for c in content_data]
    logger.info(f"Contacts message from {sender}: {len(contacts)} contact(s)")
    # TODO: Process contact information


async def _handle_unsupported(sender: str, message_type: str, message_id: str) -> None:
    """Handle unsupported message types."""
    logger.warning(f"Unsupported message type '{message_type}' from {sender}")
    # TODO: Send error message back to user


# ---------------------------------------------------------------------------
# Worker lifecycle hooks
# ---------------------------------------------------------------------------

async def startup(ctx: dict) -> None:
    """Eagerly initialize client singletons on worker start."""
    logger.info("ARQ worker starting up — initializing clients")
    get_whatsapp_client()
    get_ca_client()
    get_gemini_client()
    logger.info("ARQ worker startup complete")


async def shutdown(ctx: dict) -> None:
    """Cleanup on worker shutdown."""
    logger.info("ARQ worker shutting down")


# ---------------------------------------------------------------------------
# ARQ WorkerSettings
# ---------------------------------------------------------------------------

class WorkerSettings:
    functions = [process_message]
    redis_settings = RedisSettings.from_dsn(REDIS_URL)
    max_jobs = 10
    job_timeout = 300
    max_tries = 3
    on_startup = startup
    on_shutdown = shutdown
