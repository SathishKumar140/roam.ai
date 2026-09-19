from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import hashlib
import json

PlatformType = Literal["telegram", "whatsapp", "discord", "mock"]


class ChannelUser(BaseModel):
    id: str = Field(description="Unique platform user ID (e.g. phone number or Telegram UID)")
    name: str = Field(description="Display name of user (e.g. 'Alice')")
    handle: Optional[str] = Field(default=None, description="Platform @handle if available")


class ChannelMedia(BaseModel):
    type: Literal["photo", "voice", "document", "location"]
    file_id: Optional[str] = None
    url: Optional[str] = None
    mime_type: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ChannelEvent(BaseModel):
    """
    Unified inbound message envelope abstracting away Telegram, WhatsApp, and Discord specifics.
    """

    event_id: str
    platform: PlatformType
    connection_id: str = "default"
    channel_id: str = Field(description="Group chat ID or 1-on-1 private chat ID")
    is_group: bool = True
    sender: ChannelUser
    text: Optional[str] = None
    media: Optional[ChannelMedia] = None
    reply_to_message_id: Optional[str] = None
    message_id: Optional[str] = None
    is_reply_to_bot: bool = False
    callback_data: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_bot_mentioned: bool = False
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

    @property
    def conversation_id(self) -> str:
        identity = json.dumps([self.platform, self.connection_id, self.channel_id])
        return "conversation_" + hashlib.sha256(identity.encode()).hexdigest()

    @property
    def explicitly_addressed(self) -> bool:
        return not self.is_group or self.is_bot_mentioned or self.is_reply_to_bot


class InteractiveButton(BaseModel):
    id: str
    label: str
    type: Literal["callback", "url"] = "callback"
    url: Optional[str] = None


class OutboundMessage(BaseModel):
    """
    Unified outbound response envelope dispatched back to Telegram or WhatsApp.
    """

    platform: PlatformType
    channel_id: str
    reply_to_message_id: Optional[str] = None
    text: str
    media_url: Optional[str] = None
    buttons: Optional[List[List[InteractiveButton]]] = None


class DeliveryResult(BaseModel):
    success: bool
    provider_ids: List[str] = Field(default_factory=list)
    retry_after: Optional[float] = None
    permanent: bool = False
    error: str = ""
