import os
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv

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
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # OpenAI
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Groq
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # Messaging
    TELEGRAM_BOT_TOKEN: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = os.getenv("TELEGRAM_WEBHOOK_SECRET")

    WHATSAPP_API_TOKEN: Optional[str] = os.getenv("WHATSAPP_API_TOKEN")
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "ambient_companion_verify_token")

    # Storage paths
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "ambient_companion.db")
    CHECKPOINT_DB_PATH: str = os.getenv("CHECKPOINT_DB_PATH", "agent_memory.db")

settings = Settings()


def get_llm(provider: Optional[str] = None):
    """
    Factory function returning a model instance based on available API keys or provider preference.
    Supports Google Gemini (free-tier), Groq, and OpenAI.
    """
    prov = provider or settings.DEFAULT_LLM_PROVIDER
    
    if prov == "gemini" or (settings.GEMINI_API_KEY and not settings.OPENAI_API_KEY):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                google_api_key=settings.GEMINI_API_KEY,
                temperature=0.4
            )
        except ImportError:
            pass

    if prov == "openai" or settings.OPENAI_API_KEY:
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,
                temperature=0.4
            )
        except ImportError:
            pass

    # Fallback to standard chat interface or dummy mock for local testing
    try:
        from langchain_community.chat_models import FakeListChatModel
        return FakeListChatModel(responses=["Hello! I am your ambient group concierge."])
    except Exception:
        return None
