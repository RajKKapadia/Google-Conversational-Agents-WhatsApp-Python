"""
WhatsApp Cloud API client for downloading media and sending messages.
"""

import httpx

from src.config import ACCESS_TOKEN
from src import logging

logger = logging.getLogger(__name__)

WHATSAPP_API_BASE_URL = "https://graph.facebook.com/v22.0"


class WhatsAppClient:
    """Client for interacting with WhatsApp Cloud API"""

    def __init__(self):
        """Initialize the WhatsApp client"""
        if not ACCESS_TOKEN:
            raise ValueError("ACCESS_TOKEN is not set in environment variables")

        self.access_token = ACCESS_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
        }
        logger.info("WhatsApp client initialized")

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        """
        Download media from WhatsApp.

        Args:
            media_id: The media ID from WhatsApp

        Returns:
            Tuple of (media_bytes, mime_type)
        """
        try:
            logger.info(f"Downloading media: {media_id}")

            async with httpx.AsyncClient() as client:
                # Step 1: Get the media URL
                media_url_response = await client.get(
                    f"{WHATSAPP_API_BASE_URL}/{media_id}",
                    headers=self.headers,
                    timeout=30.0,
                )
                media_url_response.raise_for_status()
                media_info = media_url_response.json()

                media_url = media_info.get("url")
                mime_type = media_info.get("mime_type", "application/octet-stream")

                if not media_url:
                    raise ValueError("No URL found in media info response")

                logger.info(f"Media URL retrieved: {media_url}, mime_type: {mime_type}")

                # Step 2: Download the actual media file
                media_response = await client.get(
                    media_url,
                    headers=self.headers,
                    timeout=60.0,
                )
                media_response.raise_for_status()

                media_bytes = media_response.content
                logger.info(f"Media downloaded successfully. Size: {len(media_bytes)} bytes")

                return media_bytes, mime_type

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error downloading media {media_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error downloading media {media_id}: {e}")
            raise

    async def send_text_message(self, to: str, message: str) -> dict:
        """
        Send a text message via WhatsApp.

        Args:
            to: Recipient phone number (with country code, no +)
            message: Text message to send

        Returns:
            Response from WhatsApp API
        """
        try:
            logger.info(f"Sending text message to {to}")

            async with httpx.AsyncClient() as client:
                from src.config import PHONE_ID

                response = await client.post(
                    f"{WHATSAPP_API_BASE_URL}/{PHONE_ID}/messages",
                    headers={
                        **self.headers,
                        "Content-Type": "application/json",
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "recipient_type": "individual",
                        "to": to,
                        "type": "text",
                        "text": {"body": message},
                    },
                    timeout=30.0,
                )
                response.raise_for_status()

                result = response.json()
                logger.info(f"Message sent successfully to {to}")
                return result

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error sending message to {to}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error sending message to {to}: {e}")
            raise

    async def mark_message_as_read(self, message_id: str) -> dict:
        """
        Mark a message as read.

        Args:
            message_id: The message ID to mark as read

        Returns:
            Response from WhatsApp API
        """
        try:
            logger.info(f"Marking message as read: {message_id}")

            async with httpx.AsyncClient() as client:
                from src.config import PHONE_ID

                response = await client.post(
                    f"{WHATSAPP_API_BASE_URL}/{PHONE_ID}/messages",
                    headers={
                        **self.headers,
                        "Content-Type": "application/json",
                    },
                    json={
                        "messaging_product": "whatsapp",
                        "status": "read",
                        "message_id": message_id,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()

                result = response.json()
                logger.info(f"Message marked as read: {message_id}")
                return result

        except Exception as e:
            logger.error(f"Error marking message as read {message_id}: {e}")
            # Don't raise - this is not critical
            return {}


# Singleton instance
_whatsapp_client: WhatsAppClient | None = None


def get_whatsapp_client() -> WhatsAppClient:
    """Get or create the WhatsApp client singleton"""
    global _whatsapp_client
    if _whatsapp_client is None:
        _whatsapp_client = WhatsAppClient()
    return _whatsapp_client
