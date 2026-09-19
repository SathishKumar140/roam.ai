import os
import hashlib
import hmac
import uuid

try:
    import truststore

    truststore.inject_into_ssl()
except Exception:
    pass

import logging
from fastapi import FastAPI, HTTPException, Request, Response, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("roam.ai")

from src.config import settings
from src.storage.roamai import RoamAIStore
from src.adapters.telegram import TelegramAdapter
from src.adapters.whatsapp import WhatsAppAdapter
from src.agents.listener import GroupListener
from src.agents.group_planner import GroupPlanner
from src.services.roamai import RoamAIService
from src.models.channel import ChannelEvent, ChannelUser

telegram_adapter = TelegramAdapter()
whatsapp_adapter = WhatsAppAdapter()
roamai_store = RoamAIStore(settings.SQLITE_DB_PATH)
roamai_service = RoamAIService(
    roamai_store,
    GroupListener(),
    GroupPlanner(),
    adapters={"telegram": telegram_adapter, "whatsapp": whatsapp_adapter},
    mode=settings.ROAMAI_LISTENER_MODE,
    cooldown=settings.ROAMAI_OFFER_COOLDOWN_SECONDS,
    debounce=settings.ROAMAI_DEBOUNCE_SECONDS,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting RoamAI listener and durable workers (single application process)")
    roamai_service.start()
    try:
        yield
    finally:
        await roamai_service.stop()


app = FastAPI(
    title="RoamAI",
    description="Omnichannel RoamAI AI Companion for WhatsApp & Telegram using LangChain DeepAgent & MCP",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def process_roamai_event(event: ChannelEvent):
    if event.is_group and not event.explicitly_addressed:
        allowed = {item.strip() for item in settings.ROAMAI_ALLOWED_GROUPS.split(",") if item.strip()}
        identity = f"{event.platform}:{event.connection_id}:{event.channel_id}"
        if event.platform != "mock" and (settings.ROAMAI_LISTENER_MODE == "off" or (identity not in allowed and "*" not in allowed)):
            return False
    try:
        return roamai_service.enqueue(event)
    except Exception as error:
        logger.error("Inbox persistence failed: %s", type(error).__name__)
        raise HTTPException(status_code=503, detail="Unable to persist event; retry delivery") from None


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "RoamAI",
        "framework": "LangChain DeepAgent & MCP",
        "supported_channels": ["telegram", "whatsapp"],
        "chat_ui": "/",
    }


@app.get("/ready")
async def readiness_check():
    result = roamai_service.readiness()
    return JSONResponse({key: value for key, value in result.items() if key != "queues"}, status_code=200 if result["ready"] else 503)


@app.get("/chat", response_class=HTMLResponse)
async def chat_page():
    react_index = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend/dist/index.html"))
    if os.path.exists(react_index):
        with open(react_index, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("<h2>Frontend not built. Please run: npm run build --prefix frontend</h2>", status_code=404)


class WebChatRequest(BaseModel):
    channel_id: str = Field(default="web_group_1", min_length=1, max_length=100)
    sender_name: str = Field(default="You", min_length=1, max_length=100)
    sender_id: str = Field(default="user_1", min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=10000)
    client_message_id: str = Field(default_factory=lambda: uuid.uuid4().hex, max_length=100)
    is_bot_mentioned: bool = True
    callback_data: str | None = Field(default=None, max_length=64)


def require_local_chat():
    if settings.ENVIRONMENT != "development":
        raise HTTPException(status_code=404)


@app.get("/api/runtime")
async def runtime_status():
    require_local_chat()
    return roamai_service.readiness()


@app.post("/api/chat", status_code=202)
async def api_chat(payload: WebChatRequest):
    require_local_chat()
    event = ChannelEvent(
        event_id="web_" + payload.client_message_id,
        platform="mock",
        connection_id="web",
        channel_id=payload.channel_id,
        sender=ChannelUser(id=payload.sender_id, name=payload.sender_name),
        text=payload.text,
        message_id=payload.client_message_id,
        is_bot_mentioned=payload.is_bot_mentioned or bool(payload.callback_data),
        callback_data=payload.callback_data,
    )
    await process_roamai_event(event)
    return {"queued": True, "request_id": event.event_id, "responded": False}


@app.get("/api/chat/messages")
async def web_messages(channel_id: str = Query(max_length=100), after: int = Query(default=0, ge=0)):
    require_local_chat()
    event = ChannelEvent(
        event_id="lookup", platform="mock", connection_id="web", channel_id=channel_id, sender=ChannelUser(id="lookup", name="lookup")
    )
    return {"messages": roamai_store.web_messages(event.conversation_id, after), "listener_mode": settings.ROAMAI_LISTENER_MODE}


# ------------------------------------------------------------------------------
# Telegram Webhook
# ------------------------------------------------------------------------------
@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    if not settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Telegram webhook secret is not configured")
    if not hmac.compare_digest(request.headers.get("X-Telegram-Bot-Api-Secret-Token", ""), settings.TELEGRAM_WEBHOOK_SECRET):
        raise HTTPException(status_code=403)
    payload = await request.json()
    event = await telegram_adapter.parse_webhook(payload)
    if event:
        await process_roamai_event(event)
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
async def whatsapp_webhook(request: Request):
    if not settings.WHATSAPP_APP_SECRET:
        raise HTTPException(status_code=503, detail="WhatsApp app secret is not configured")
    body = await request.body()
    expected = "sha256=" + hmac.new(settings.WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(request.headers.get("X-Hub-Signature-256", ""), expected):
        raise HTTPException(status_code=403)
    for event in await whatsapp_adapter.parse_events(await request.json()):
        if settings.WHATSAPP_PHONE_NUMBER_ID and event.connection_id != settings.WHATSAPP_PHONE_NUMBER_ID:
            raise HTTPException(status_code=403)
        await process_roamai_event(event)
    return Response(status_code=200, content="OK")


# ------------------------------------------------------------------------------
# Mount React + Vite Frontend (dist)
# ------------------------------------------------------------------------------
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "../frontend/dist"))
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
