import httpx
from typing import Optional, Dict, Any, List
from src.config import settings
from src.adapters.base import ChannelAdapter
from src.models.channel import ChannelEvent, ChannelUser, ChannelMedia, OutboundMessage, PlatformType

class TelegramAdapter(ChannelAdapter):
    def __init__(self, bot_token: Optional[str] = None):
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None

    @property
    def platform(self) -> PlatformType:
        return "telegram"

    async def parse_webhook(self, payload: Dict[str, Any]) -> Optional[ChannelEvent]:
        """Normalizes Telegram Update JSON into unified ChannelEvent."""
        msg = payload.get("message") or payload.get("channel_post")
        callback = payload.get("callback_query")

        # Handle button callback taps
        if callback:
            msg = callback.get("message", {})
            sender_data = callback.get("from", {})
            chat_data = msg.get("chat", {})
            return ChannelEvent(
                event_id=f"tg_cb_{callback.get('id')}",
                platform="telegram",
                channel_id=str(chat_data.get("id")),
                is_group=chat_data.get("type") in ["group", "supergroup"],
                sender=ChannelUser(
                    id=str(sender_data.get("id")),
                    name=f"{sender_data.get('first_name', '')} {sender_data.get('last_name', '')}".strip() or "User",
                    handle=sender_data.get("username")
                ),
                text=callback.get("data", ""),
                is_bot_mentioned=True,
                raw_payload=payload
            )

        if not msg:
            return None

        chat = msg.get("chat", {})
        sender_data = msg.get("from", {})
        text = msg.get("text") or msg.get("caption") or ""
        
        # Check for photos
        media = None
        if "photo" in msg and len(msg["photo"]) > 0:
            # Pick highest resolution photo
            highest_res = msg["photo"][-1]
            media = ChannelMedia(
                type="photo",
                file_id=highest_res.get("file_id")
            )
        elif "location" in msg:
            loc = msg["location"]
            media = ChannelMedia(
                type="location",
                latitude=loc.get("latitude"),
                longitude=loc.get("longitude")
            )

        # Detect bot mention
        entities = msg.get("entities") or msg.get("caption_entities") or []
        is_mentioned = any(e.get("type") == "mention" or e.get("type") == "bot_command" for e in entities)

        return ChannelEvent(
            event_id=f"tg_msg_{msg.get('message_id')}",
            platform="telegram",
            channel_id=str(chat.get("id")),
            is_group=chat.get("type") in ["group", "supergroup"],
            sender=ChannelUser(
                id=str(sender_data.get("id")),
                name=f"{sender_data.get('first_name', '')} {sender_data.get('last_name', '')}".strip() or "User",
                handle=sender_data.get("username")
            ),
            text=text,
            media=media,
            reply_to_message_id=str(msg.get("reply_to_message", {}).get("message_id")) if msg.get("reply_to_message") else None,
            is_bot_mentioned=is_mentioned,
            raw_payload=payload
        )

    async def send_message(self, message: OutboundMessage) -> bool:
        if not self.base_url:
            return False

        reply_markup = None
        if message.buttons:
            inline_keyboard = []
            for row in message.buttons:
                btn_row = []
                for b in row:
                    if b.type == "url" and b.url:
                        btn_row.append({"text": b.label, "url": b.url})
                    else:
                        btn_row.append({"text": b.label, "callback_data": b.id})
                inline_keyboard.append(btn_row)
            reply_markup = {"inline_keyboard": inline_keyboard}

        async with httpx.AsyncClient(timeout=10.0) as client:
            if message.media_url:
                payload = {
                    "chat_id": message.channel_id,
                    "photo": message.media_url,
                    "caption": message.text,
                    "parse_mode": "Markdown"
                }
                if reply_markup:
                    payload["reply_markup"] = reply_markup
                resp = await client.post(f"{self.base_url}/sendPhoto", json=payload)
                return resp.status_code == 200
            else:
                payload = {
                    "chat_id": message.channel_id,
                    "text": message.text,
                    "parse_mode": "Markdown"
                }
                if reply_markup:
                    payload["reply_markup"] = reply_markup
                resp = await client.post(f"{self.base_url}/sendMessage", json=payload)
                return resp.status_code == 200

    async def send_typing(self, channel_id: str):
        if not self.base_url:
            return
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{self.base_url}/sendChatAction", json={
                "chat_id": channel_id,
                "action": "typing"
            })
