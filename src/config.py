import os
from typing import Literal, Optional
from pydantic import BaseModel
from dotenv import load_dotenv

try:
    import truststore

    truststore.inject_into_ssl()
except Exception:
    pass

# Load environment variables
load_dotenv()


class Settings(BaseModel):
    # Server
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # LLM Settings
    DEFAULT_LLM_PROVIDER: str = os.getenv("DEFAULT_LLM_PROVIDER", "gemini")

    # Gemini
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

    # OpenAI
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Groq
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # Messaging
    TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    TELEGRAM_BOT_USERNAME: str = os.getenv("TELEGRAM_BOT_USERNAME", "")

    WHATSAPP_API_TOKEN: Optional[str] = os.getenv("WHATSAPP_API_TOKEN")
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "roamai_companion_verify_token")
    WHATSAPP_APP_SECRET: Optional[str] = os.getenv("WHATSAPP_APP_SECRET")
    ROAMAI_LISTENER_MODE: Literal["off", "shadow", "live"] = os.getenv("ROAMAI_LISTENER_MODE", "shadow")
    ROAMAI_ALLOWED_GROUPS: str = os.getenv("ROAMAI_ALLOWED_GROUPS", "")
    ROAMAI_DEBOUNCE_SECONDS: float = float(os.getenv("ROAMAI_DEBOUNCE_SECONDS", "10"))
    ROAMAI_OFFER_COOLDOWN_SECONDS: float = float(os.getenv("ROAMAI_OFFER_COOLDOWN_SECONDS", "300"))

    # Storage paths
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "roamai_companion.db")
    CHECKPOINT_DB_PATH: str = os.getenv("CHECKPOINT_DB_PATH", "agent_memory.db")

    # Langfuse Tracing & Observability
    LANGFUSE_PUBLIC_KEY: Optional[str] = os.getenv("LANGFUSE_PUBLIC_KEY")
    LANGFUSE_SECRET_KEY: Optional[str] = os.getenv("LANGFUSE_SECRET_KEY")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

    # Search & Live APIs (Google Flights, Hotels & Events via SerpApi)
    SERPAPI_KEY: Optional[str] = os.getenv("SERPAPI_KEY") or os.getenv("SERP_API_KEY")


settings = Settings()


def get_llm(provider: Optional[str] = None, *, allow_fake: bool = True):
    """
    Factory function returning a model instance based on available API keys or provider preference.
    Supports Google Gemini (free-tier), Groq, and OpenAI.
    """
    prov = provider or settings.DEFAULT_LLM_PROVIDER

    if settings.GEMINI_API_KEY and (prov == "gemini" or not settings.OPENAI_API_KEY):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(model=settings.GEMINI_MODEL, google_api_key=settings.GEMINI_API_KEY, temperature=0.4)
        except Exception:
            pass

    if settings.OPENAI_API_KEY and (prov == "openai" or not settings.GEMINI_API_KEY):
        try:
            from langchain_openai import ChatOpenAI

            model_name = settings.OPENAI_MODEL
            kwargs = {"model": model_name, "api_key": settings.OPENAI_API_KEY}
            if not any(model_name.startswith(p) for p in ("gpt-6", "o1", "o3", "o4")):
                kwargs["temperature"] = 0.4
            return ChatOpenAI(**kwargs)
        except Exception:
            pass

    if not allow_fake:
        raise RuntimeError("No live model could be initialized; check provider configuration and connectivity")

    # Fallback to standard chat interface or dummy mock for local testing
    try:
        from langchain_community.chat_models import FakeListChatModel

        return FakeListChatModel(responses=["Hello! I am your buddy to plan and assist you in travel and stay or outing."])
    except Exception:
        return None
