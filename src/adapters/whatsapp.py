import httpx
from typing import Optional, Dict, Any, List
from src.config import settings
from src.adapters.base import ChannelAdapter
from src.models.channel import ChannelEvent, ChannelUser, ChannelMedia, OutboundMessage, PlatformType

class WhatsAppAdapter(ChannelAdapter):
    def __init__(
        self,
        api_token: Optional[str] = None,
        phone_number_id: Optional[str] = None
    ):
        self.api_token = api_token or settings.WHATSAPP_API_TOKEN
        self.phone_number_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
        self.base_url = f"https://graph.facebook.com/v20.0/{self.phone_number_id}/messages" if self.phone_number_id else None

    @property
    def platform(self) -> PlatformType:
        return "whatsapp"

    async def parse_webhook(self, payload: Dict[str, Any]) -> Optional[ChannelEvent]:
        """Normalizes Meta WhatsApp Cloud API Webhook payload into unified ChannelEvent."""
        try:
            entry = payload.get("entry", [])[0]
            change = entry.get("changes", [])[0]
            value = change.get("value", {})
            messages = value.get("messages", [])
            contacts = value.get("contacts", [])

            if not messages:
                return None

            msg = messages[0]
            contact = contacts[0] if contacts else {}
            sender_id = msg.get("from")
            sender_name = contact.get("profile", {}).get("name", "WhatsApp User")

            msg_type = msg.get("type")
            text = ""
            media = None

            if msg_type == "text":
                text = msg.get("text", {}).get("body", "")
            elif msg_type == "interactive":
                # Button reply
                interactive = msg.get("interactive", {})
                btn_reply = interactive.get("button_reply", {})
                text = btn_reply.get("id") or btn_reply.get("title", "")
            elif msg_type == "image":
                img = msg.get("image", {})
                text = img.get("caption", "")
                media = ChannelMedia(
                    type="photo",
                    file_id=img.get("id"),
                    mime_type=img.get("mime_type")
                )
            elif msg_type == "location":
                loc = msg.get("location", {})
                media = ChannelMedia(
                    type="location",
                    latitude=loc.get("latitude"),
                    longitude=loc.get("longitude")
                )

            # In WhatsApp, group messages have group JID or sender_id
            return ChannelEvent(
                event_id=f"wa_{msg.get('id')}",
                platform="whatsapp",
                channel_id=sender_id, # Or group JID
                is_group=False,       # Can be determined by JID format (e.g. @g.us)
                sender=ChannelUser(
                    id=sender_id,
                    name=sender_name
                ),
                text=text,
                media=media,
                is_bot_mentioned=True, # Direct chats or when tagged
                raw_payload=payload
            )
        except Exception:
            return None

    async def send_message(self, message: OutboundMessage) -> bool:
        if not self.base_url or not self.api_token:
            return False

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            if message.buttons and len(message.buttons) > 0:
                # Format WhatsApp Interactive Button message (up to 3 quick-reply buttons)
                flat_buttons = [btn for row in message.buttons for btn in row][:3]
                buttons_payload = [
                    {
                        "type": "reply",
                        "reply": {"id": b.id, "title": b.label[:20]} # WhatsApp max 20 chars
                    }
                    for b in flat_buttons
                ]
                payload = {
                    "messaging_product": "whatsapp",
                    "to": message.channel_id,
                    "type": "interactive",
                    "interactive": {
                        "type": "button",
                        "body": {"text": message.text},
                        "action": {"buttons": buttons_payload}
                    }
                }
            else:
                payload = {
                    "messaging_product": "whatsapp",
                    "to": message.channel_id,
                    "type": "text",
                    "text": {"body": message.text}
                }

            resp = await client.post(self.base_url, headers=headers, json=payload)
            return resp.status_code in [200, 201]

    async def send_typing(self, channel_id: str):
        pass # WhatsApp doesn't have an open direct typing API for cloud without template
