import logging
import httpx
from typing import Optional, Dict, Any, List
from src.config import settings
from src.adapters.base import ChannelAdapter
from src.models.channel import ChannelEvent, ChannelUser, ChannelMedia, OutboundMessage, PlatformType

logger = logging.getLogger("roam.telegram")

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

        async with httpx.AsyncClient(timeout=15.0) as client:
            if message.media_url:
                caption = message.text or ""
                # Telegram photo caption limit is 1024 chars
                if len(caption) > 1024:
                    caption = caption[:1020] + "..."
                payload = {
                    "chat_id": message.channel_id,
                    "photo": message.media_url,
                    "caption": caption,
                    "parse_mode": "Markdown"
                }
                if reply_markup:
                    payload["reply_markup"] = reply_markup
                resp = await client.post(f"{self.base_url}/sendPhoto", json=payload)
                if resp.status_code != 200:
                    logger.warning(f"⚠️ [Telegram] sendPhoto failed ({resp.status_code}): {resp.text}. Retrying without parse_mode...")
                    payload.pop("parse_mode", None)
                    resp = await client.post(f"{self.base_url}/sendPhoto", json=payload)
                return resp.status_code == 200
            else:
                full_text = message.text or ""
                # Telegram message text limit is 4096 chars; chunk if necessary
                chunk_size = 4000
                chunks = [full_text[i:i + chunk_size] for i in range(0, max(1, len(full_text)), chunk_size)]
                
                success = True
                for idx, chunk in enumerate(chunks):
                    payload = {
                        "chat_id": message.channel_id,
                        "text": chunk,
                        "parse_mode": "Markdown"
                    }
                    # Attach buttons only to the final chunk
                    if idx == len(chunks) - 1 and reply_markup:
                        payload["reply_markup"] = reply_markup

                    resp = await client.post(f"{self.base_url}/sendMessage", json=payload)
                    if resp.status_code != 200:
                        logger.warning(f"⚠️ [Telegram] sendMessage failed ({resp.status_code}): {resp.text}. Retrying without parse_mode...")
                        payload.pop("parse_mode", None)
                        resp = await client.post(f"{self.base_url}/sendMessage", json=payload)
                    if resp.status_code != 200:
                        logger.error(f"❌ [Telegram] sendMessage retry also failed ({resp.status_code}): {resp.text}")
                        success = False
                return success

    async def send_typing(self, channel_id: str):
        if not self.base_url:
            return
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                await client.post(f"{self.base_url}/sendChatAction", json={
                    "chat_id": channel_id,
                    "action": "typing"
                })
            except Exception as e:
                logger.warning(f"⚠️ [Telegram] Failed to send typing indicator: {e}")
