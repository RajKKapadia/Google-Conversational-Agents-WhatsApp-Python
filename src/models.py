"""
Pydantic models for WhatsApp webhook payloads.
Based on Meta WhatsApp Cloud API documentation.
"""

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Supported message types from WhatsApp"""

    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    AUDIO = "audio"
    VIDEO = "video"
    VOICE = "voice"
    STICKER = "sticker"
    LOCATION = "location"
    CONTACTS = "contacts"
    INTERACTIVE = "interactive"
    BUTTON = "button"
    UNKNOWN = "unknown"


class TextMessage(BaseModel):
    """Text message content"""

    body: str


class MediaMessage(BaseModel):
    """Media message content (image, document, audio, video, voice)"""

    id: str
    mime_type: Optional[str] = None
    sha256: Optional[str] = None
    caption: Optional[str] = None
    filename: Optional[str] = None


class LocationMessage(BaseModel):
    """Location message content"""

    latitude: float
    longitude: float
    name: Optional[str] = None
    address: Optional[str] = None


class ContactProfile(BaseModel):
    """Contact profile information"""

    name: str


class Contact(BaseModel):
    """Contact information"""

    profile: ContactProfile
    wa_id: str


class Message(BaseModel):
    """Individual message object"""

    from_: str = Field(alias="from")
    id: str
    timestamp: str
    type: str
    text: Optional[TextMessage] = None
    image: Optional[MediaMessage] = None
    document: Optional[MediaMessage] = None
    audio: Optional[MediaMessage] = None
    video: Optional[MediaMessage] = None
    voice: Optional[MediaMessage] = None
    sticker: Optional[MediaMessage] = None
    location: Optional[LocationMessage] = None
    contacts: Optional[list[Contact]] = None

    def get_message_type(self) -> MessageType:
        """Identify and return the message type"""
        try:
            return MessageType(self.type)
        except ValueError:
            return MessageType.UNKNOWN

    def get_content(self) -> str | MediaMessage | LocationMessage | list[Contact] | None:
        """Extract the actual content based on message type"""
        msg_type = self.get_message_type()

        if msg_type == MessageType.TEXT and self.text:
            return self.text.body
        elif msg_type == MessageType.IMAGE and self.image:
            return self.image
        elif msg_type == MessageType.DOCUMENT and self.document:
            return self.document
        elif msg_type == MessageType.AUDIO and self.audio:
            return self.audio
        elif msg_type == MessageType.VIDEO and self.video:
            return self.video
        elif msg_type == MessageType.VOICE and self.voice:
            return self.voice
        elif msg_type == MessageType.STICKER and self.sticker:
            return self.sticker
        elif msg_type == MessageType.LOCATION and self.location:
            return self.location
        elif msg_type == MessageType.CONTACTS and self.contacts:
            return self.contacts

        return None


class StatusUpdate(BaseModel):
    """Status update for sent messages"""

    id: str
    status: str
    timestamp: str
    recipient_id: str
    conversation: Optional[dict] = None
    pricing: Optional[dict] = None


class Metadata(BaseModel):
    """Metadata about the phone number"""

    display_phone_number: str
    phone_number_id: str


class Value(BaseModel):
    """Value object containing messages and metadata"""

    messaging_product: Literal["whatsapp"]
    metadata: Metadata
    contacts: Optional[list[Contact]] = None
    messages: Optional[list[Message]] = None
    statuses: Optional[list[StatusUpdate]] = None


class Change(BaseModel):
    """Change object in the webhook payload"""

    value: Value
    field: Literal["messages"]


class Entry(BaseModel):
    """Entry object in the webhook payload"""

    id: str
    changes: list[Change]


class WebhookPayload(BaseModel):
    """Root webhook payload from WhatsApp"""

    object: Literal["whatsapp_business_account"]
    entry: list[Entry]

    def get_messages(self) -> list[Message]:
        """Extract all messages from the payload"""
        messages = []
        for entry in self.entry:
            for change in entry.changes:
                if change.value.messages:
                    messages.extend(change.value.messages)
        return messages

    def get_phone_number_id(self) -> Optional[str]:
        """Get the phone number ID from metadata"""
        if self.entry and self.entry[0].changes:
            return self.entry[0].changes[0].value.metadata.phone_number_id
        return None
