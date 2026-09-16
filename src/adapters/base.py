from abc import ABC, abstractmethod
from typing import Optional, Tuple
from src.models.channel import ChannelEvent, OutboundMessage, PlatformType

class ChannelAdapter(ABC):
    @property
    @abstractmethod
    def platform(self) -> PlatformType:
        pass

    @abstractmethod
    async def parse_webhook(self, payload: dict) -> Optional[ChannelEvent]:
        """Parses raw webhook JSON payload into normalized ChannelEvent."""
        pass

    @abstractmethod
    async def send_message(self, message: OutboundMessage) -> bool:
        """Sends message back to platform (with buttons/media if applicable)."""
        pass

    @abstractmethod
    async def send_typing(self, channel_id: str):
        """Dispatches typing action to platform."""
        pass
