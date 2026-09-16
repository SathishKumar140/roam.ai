import asyncio
from fastapi import FastAPI, Request, Response, BackgroundTasks
from contextlib import asynccontextmanager

from src.config import settings
from src.storage.database import db
from src.adapters.telegram import TelegramAdapter
from src.adapters.whatsapp import WhatsAppAdapter
from src.scheduler.temporal import start_scheduler
from src.agents.deep_companion import ambient_companion
from src.models.channel import ChannelEvent, OutboundMessage

telegram_adapter = TelegramAdapter()
whatsapp_adapter = WhatsAppAdapter()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start SQLite and APScheduler
    start_scheduler()
    yield

app = FastAPI(
    title="RoamAI",
    description="Omnichannel Ambient AI Companion for WhatsApp & Telegram using LangChain DeepAgent & MCP",
    version="1.0.0",
    lifespan=lifespan
)

async def process_ambient_event(event: ChannelEvent):
    """
    Core ambient processing loop:
    1. Buffer message into short-term SQLite memory.
    2. If summoned or actionable intent detected, run LangChain DeepAgent and reply.
    """
    # 1. Silently buffer into SQLite sliding window
    db.buffer_message(event)

    # 2. Check if agent should speak (explicit summon, media, or direct question)
    should_respond = (
        event.is_bot_mentioned or 
        not event.is_group or 
        (event.media is not None) or
        any(trigger in (event.text or "").lower() for trigger in [
            "trip", "flight", "hotel", "itinerary", "spent", "paid", "bill", "split", "owe", "settle", "confirm", "roamai", "roam"
        ])
    )

    if not should_respond:
        # Remain silent sentry
        return

    # 3. Retrieve preceding 30 messages for multi-party group arbitration
    history = db.get_recent_group_messages(event.channel_id, limit=30)

    # 4. Invoke LangChain DeepAgent
    adapter = telegram_adapter if event.platform == "telegram" else whatsapp_adapter
    await adapter.send_typing(event.channel_id)

    res = await ambient_companion.ainvoke({
        "channel_id": event.channel_id,
        "platform": event.platform,
        "sender_name": event.sender.name,
        "sender_id": event.sender.id,
        "text": event.text or "",
        "media": event.media.dict() if event.media else None,
        "history": history
    })

    output_text = res.get("output", "I'm on it!")
    buttons = res.get("buttons")

    outbound = OutboundMessage(
        platform=event.platform,
        channel_id=event.channel_id,
        reply_to_message_id=event.reply_to_message_id,
        text=output_text,
        buttons=buttons
    )
    await adapter.send_message(outbound)


@app.get("/")
async def health_check():
    return {
        "status": "healthy",
        "service": "RoamAI",
        "framework": "LangChain DeepAgent & MCP",
        "supported_channels": ["telegram", "whatsapp"]
    }

# ------------------------------------------------------------------------------
# Telegram Webhook
# ------------------------------------------------------------------------------
@app.post("/webhook/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    event = await telegram_adapter.parse_webhook(payload)
    if event:
        background_tasks.add_task(process_ambient_event, event)
    return Response(status_code=200, content="OK")

# ------------------------------------------------------------------------------
# WhatsApp Cloud API Webhook
# ------------------------------------------------------------------------------
@app.get("/webhook/whatsapp")
async def whatsapp_verify(request: Request):
    """WhatsApp Cloud API webhook verification challenge."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=403, content="Verification failed")

@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    event = await whatsapp_adapter.parse_webhook(payload)
    if event:
        background_tasks.add_task(process_ambient_event, event)
    return Response(status_code=200, content="OK")
