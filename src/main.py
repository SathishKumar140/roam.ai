import os
import sys
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import asyncio
import logging
from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("roam.ai")

from src.config import settings
from src.storage.database import db
from src.adapters.telegram import TelegramAdapter
from src.adapters.whatsapp import WhatsAppAdapter
from src.scheduler.temporal import start_scheduler
from src.agents.deep_companion import ambient_companion
from src.models.channel import ChannelEvent, ChannelUser, OutboundMessage

telegram_adapter = TelegramAdapter()
whatsapp_adapter = WhatsAppAdapter()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start SQLite and APScheduler
    logger.info("🚀 Starting RoamAI services (Scheduler & SQLite)...")
    start_scheduler()
    yield
    logger.info("🛑 Shutting down RoamAI services...")

app = FastAPI(
    title="RoamAI",
    description="Omnichannel Ambient AI Companion for WhatsApp & Telegram using LangChain DeepAgent & MCP",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        logger.debug(f"🤫 [Sentry] Channel {event.channel_id} message ignored (silent sentry).")
        return

    logger.info(f"⚡ [Event Triggered] Channel: {event.channel_id} | Sender: {event.sender.name} | Text: \"{event.text}\"")

    # 3. Retrieve preceding 30 messages for multi-party group arbitration
    history = db.get_recent_group_messages(event.channel_id, limit=30)

    # 4. Invoke LangChain DeepAgent
    adapter = telegram_adapter if event.platform == "telegram" else whatsapp_adapter
    await adapter.send_typing(event.channel_id)

    res = await ambient_companion.ainvoke(
        {
            "channel_id": event.channel_id,
            "platform": event.platform,
            "sender_name": event.sender.name,
            "sender_id": event.sender.id,
            "text": event.text or "",
            "media": event.media.dict() if event.media else None,
            "history": history
        },
        config={"configurable": {"thread_id": event.channel_id}}
    )

    output_text = res.get("output", "I'm on it!")
    buttons = res.get("buttons")

    logger.info(f"📤 [Outbound Reply] Sending reply to {event.channel_id} ({len(output_text)} chars)")
    outbound = OutboundMessage(
        platform=event.platform,
        channel_id=event.channel_id,
        reply_to_message_id=event.reply_to_message_id,
        text=output_text,
        buttons=buttons
    )
    await adapter.send_message(outbound)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "RoamAI",
        "framework": "LangChain DeepAgent & MCP",
        "supported_channels": ["telegram", "whatsapp"],
        "chat_ui": "/"
    }

@app.get("/chat", response_class=HTMLResponse)
async def chat_page():
    react_index = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend/dist/index.html"))
    if os.path.exists(react_index):
        with open(react_index, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("<h2>Frontend not built. Please run: npm run build --prefix frontend</h2>", status_code=404)

@app.post("/api/chat")
async def api_chat(payload: dict):
    channel_id = payload.get("channel_id", "web_group_1")
    sender_name = payload.get("sender_name", "You")
    sender_id = payload.get("sender_id", "user_1")
    text = payload.get("text", "")
    
    logger.info(f"📩 [/api/chat] User '{sender_name}' in channel '{channel_id}' sent: \"{text}\"")

    event = ChannelEvent(
        event_id=f"web_{asyncio.get_event_loop().time()}",
        platform="telegram",
        channel_id=channel_id,
        is_group=True,
        sender=ChannelUser(id=sender_id, name=sender_name),
        text=text,
        is_bot_mentioned=True
    )
    db.buffer_message(event)
    history = db.get_recent_group_messages(channel_id, limit=30)
    
    logger.info(f"🧠 [/api/chat] Invoking ambient DeepAgent companion...")
    res = await ambient_companion.ainvoke(
        {
            "channel_id": channel_id,
            "platform": "telegram",
            "sender_name": sender_name,
            "sender_id": sender_id,
            "text": text,
            "media": None,
            "history": history
        },
        config={"configurable": {"thread_id": channel_id}}
    )
    output = res.get("output", "")
    logger.info(f"🤖 [/api/chat] Agent response generated ({len(output)} chars). First 100 chars: {output[:100].strip()}...")
    return {
        "responded": True,
        "output": output,
        "buttons": res.get("buttons")
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

# ------------------------------------------------------------------------------
# Mount React + Vite Frontend (dist)
# ------------------------------------------------------------------------------
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend/dist"))
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

