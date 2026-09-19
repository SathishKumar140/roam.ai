import logging
import httpx
from typing import Optional, Dict, Any
from src.config import settings
from src.adapters.base import ChannelAdapter
from src.models.channel import ChannelEvent, ChannelUser, ChannelMedia, DeliveryResult, OutboundMessage, PlatformType

logger = logging.getLogger("roam.telegram")


class TelegramAdapter(ChannelAdapter):
    def __init__(self, bot_token: Optional[str] = None, bot_username: Optional[str] = None):
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.bot_id = self.bot_token.split(":", 1)[0] if self.bot_token else "default"
        self.bot_username = (bot_username or settings.TELEGRAM_BOT_USERNAME).lstrip("@").lower()
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None

    @property
    def platform(self) -> PlatformType:
        return "telegram"

    async def get_file_url(self, file_id: str) -> Optional[str]:
        """Resolves a Telegram file_id into a full downloadable CDN URL."""
        if not self.base_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/getFile", params={"file_id": file_id})
                if resp.status_code == 200:
                    file_path = resp.json().get("result", {}).get("file_path")
                    if file_path:
                        return f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
        except Exception as e:
            logger.warning(f"⚠️ [Telegram] Failed to get file URL for {file_id}: {e}")
        return None

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
                connection_id=self.bot_id,
                channel_id=str(chat_data.get("id")),
                message_id=str(msg.get("message_id")),
                reply_to_message_id=str(msg.get("message_id")),
                callback_data=callback.get("data", ""),
                is_group=chat_data.get("type") in ["group", "supergroup"],
                sender=ChannelUser(
                    id=str(sender_data.get("id")),
                    name=f"{sender_data.get('first_name', '')} {sender_data.get('last_name', '')}".strip() or "User",
                    handle=sender_data.get("username"),
                ),
                text=callback.get("data", ""),
                is_bot_mentioned=True,
                raw_payload=payload,
            )

        if not msg:
            return None

        chat = msg.get("chat", {})
        sender_data = msg.get("from", {})
        if sender_data.get("is_bot") or not sender_data.get("id"):
            return None
        text = msg.get("text") or msg.get("caption") or ""

        # Check for photos, voice notes, audio files, or locations
        media = None
        if "photo" in msg and len(msg["photo"]) > 0:
            # Pick highest resolution photo
            highest_res = msg["photo"][-1]
            file_id = highest_res.get("file_id")
            media = ChannelMedia(
                type="photo",
                file_id=file_id,
            )
        elif "voice" in msg or "audio" in msg or "video_note" in msg:
            audio_obj = msg.get("voice") or msg.get("audio") or msg.get("video_note") or {}
            file_id = audio_obj.get("file_id")
            mime_type = audio_obj.get("mime_type") or "audio/ogg"
            media = ChannelMedia(type="voice", file_id=file_id, mime_type=mime_type)
            if not text:
                text = "[Voice message]"
        elif "location" in msg:
            loc = msg["location"]
            media = ChannelMedia(type="location", latitude=loc.get("latitude"), longitude=loc.get("longitude"))

        # Detect bot mention
        entities = msg.get("entities") or msg.get("caption_entities") or []
        is_mentioned = False
        encoded = text.encode("utf-16-le")
        for entity in entities:
            start = entity.get("offset", 0) * 2
            end = start + entity.get("length", 0) * 2
            label = encoded[start:end].decode("utf-16-le", errors="replace").lower()
            if entity.get("type") == "mention" and self.bot_username and label == "@" + self.bot_username:
                is_mentioned = True
            if entity.get("type") == "text_mention" and str(entity.get("user", {}).get("id")) == self.bot_id:
                is_mentioned = True
            if entity.get("type") == "bot_command" and ("@" not in label or label.endswith("@" + self.bot_username)):
                is_mentioned = True
        reply = msg.get("reply_to_message", {})

        return ChannelEvent(
            event_id=f"tg_update_{payload['update_id']}" if "update_id" in payload else f"tg_msg_{chat.get('id')}_{msg.get('message_id')}",
            platform="telegram",
            connection_id=self.bot_id,
            channel_id=str(chat.get("id")),
            message_id=str(msg.get("message_id")),
            is_reply_to_bot=str(reply.get("from", {}).get("id")) == self.bot_id,
            is_group=chat.get("type") in ["group", "supergroup"],
            sender=ChannelUser(
                id=str(sender_data.get("id")),
                name=f"{sender_data.get('first_name', '')} {sender_data.get('last_name', '')}".strip() or "User",
                handle=sender_data.get("username"),
            ),
            text=text,
            media=media,
            reply_to_message_id=str(msg.get("reply_to_message", {}).get("message_id")) if msg.get("reply_to_message") else None,
            is_bot_mentioned=is_mentioned,
            raw_payload=payload,
        )

    async def deliver(self, message: OutboundMessage) -> DeliveryResult:
        if not self.base_url:
            return DeliveryResult(success=False, permanent=True, error="Telegram credentials are not configured")
        payload = {"chat_id": message.channel_id, "text": message.text}
        if message.reply_to_message_id:
            payload["reply_parameters"] = {"message_id": int(message.reply_to_message_id), "allow_sending_without_reply": True}
        if message.buttons:
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [
                        {"text": button.label, "url": button.url}
                        if button.type == "url"
                        else {"text": button.label, "callback_data": button.id}
                        for button in row
                    ]
                    for row in message.buttons
                ]
            }
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(f"{self.base_url}/sendMessage", json=payload)
        data = response.json()
        success = response.status_code == 200 and data.get("ok", False)
        return DeliveryResult(
            success=success,
            provider_ids=[str(data["result"]["message_id"])] if success else [],
            retry_after=data.get("parameters", {}).get("retry_after"),
            permanent=400 <= response.status_code < 500 and response.status_code not in {408, 429},
            error="" if success else f"Telegram HTTP {response.status_code}",
        )

    async def media_bytes(self, media: ChannelMedia):
        url = await self.get_file_url(media.file_id) if media.file_id else None
        if not url:
            raise ValueError("Media could not be resolved")
        async with httpx.AsyncClient(timeout=20) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > 8 * 1024 * 1024:
                        raise ValueError("Media exceeds the 8 MB processing limit")
                mime = response.headers.get("content-type", media.mime_type or "application/octet-stream").split(";")[0]
                return bytes(content), mime

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
                payload = {"chat_id": message.channel_id, "photo": message.media_url, "caption": caption, "parse_mode": "Markdown"}
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
                chunks = [full_text[i : i + chunk_size] for i in range(0, max(1, len(full_text)), chunk_size)]

                success = True
                for idx, chunk in enumerate(chunks):
                    payload = {"chat_id": message.channel_id, "text": chunk, "parse_mode": "Markdown"}
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
                await client.post(f"{self.base_url}/sendChatAction", json={"chat_id": channel_id, "action": "typing"})
            except Exception as e:
                logger.warning(f"⚠️ [Telegram] Failed to send typing indicator: {e}")
