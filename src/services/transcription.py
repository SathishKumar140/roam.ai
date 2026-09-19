import logging
import os
from typing import Optional, Union
import httpx
from src.config import settings

logger = logging.getLogger("roam.transcription")

WHISPER_TRAVEL_PROMPT = (
    "RoamAI travel concierge and companion. "
    "Keywords and destinations: "
    "Bali, Denpasar, DPS, Indonesia, Singapore, SIN, Ha Giang, Hanoi, Vietnam, "
    "Bangkok, BKK, Thailand, Tokyo, Japan, London, UK, flight, airline, Scoot, Singapore Airlines, "
    "hotel, resort, villa, Airbnb, homestay, itinerary, budget, dates, "
    "end of November, November, October, December, January, next month, next week, "
    "expense, dinner, bill, split, paid SGD, owes, ledger, confirmation, count me in, I'm in."
)


async def transcribe_audio_async(
    audio_source: Union[bytes, str], mime_type: str = "audio/ogg", filename: str = "voice.oga"
) -> Optional[str]:
    """
    Transcribes audio bytes or audio from a URL/file path using OpenAI Whisper-1.
    Supports Telegram voice notes (.oga / .ogg Opus), audio files (.mp3, .m4a, .wav), and webm.
    Conditioned with a travel-domain prompt for flawless recognition of destinations, dates, and accents.
    """
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        logger.warning("⚠️ No OPENAI_API_KEY configured for Whisper transcription.")
        return None

    audio_bytes: Optional[bytes] = None

    # 1. Check if source is raw bytes
    if isinstance(audio_source, bytes):
        audio_bytes = audio_source

    # 2. Check if source is local file path
    elif isinstance(audio_source, str) and os.path.exists(audio_source) and os.path.isfile(audio_source):
        try:
            with open(audio_source, "rb") as f:
                audio_bytes = f.read()
            if audio_source.endswith(".mp3"):
                mime_type = "audio/mpeg"
                filename = "audio.mp3"
            elif audio_source.endswith(".wav"):
                mime_type = "audio/wav"
                filename = "audio.wav"
            elif audio_source.endswith(".webm") or audio_source.endswith(".img"):
                mime_type = "audio/webm"
                filename = "audio.webm"
        except Exception as e:
            logger.warning(f"⚠️ Failed reading audio file {audio_source}: {e}")

    # 3. Check if source is HTTP URL (e.g. Telegram CDN)
    elif isinstance(audio_source, str) and (audio_source.startswith("http://") or audio_source.startswith("https://")):
        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
                resp = await client.get(audio_source)
                if resp.status_code == 200:
                    audio_bytes = resp.content
                    content_type = resp.headers.get("content-type", "").split(";")[0]
                    if content_type:
                        mime_type = content_type
                    logger.info(f"🎙️ Downloaded audio from URL ({len(audio_bytes)} bytes, mime={mime_type})")
        except Exception as e:
            logger.warning(f"⚠️ Failed downloading audio from URL {audio_source}: {e}")

    if not audio_bytes or len(audio_bytes) < 32:
        logger.warning("⚠️ Audio payload is empty or too short for transcription.")
        return None

    # 4. Transcribe using OpenAI Whisper API or Gemini Multimodal Audio
    if settings.DEFAULT_LLM_PROVIDER != "gemini" and settings.OPENAI_API_KEY:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            transcription = await client.audio.transcriptions.create(
                model="whisper-1", file=(filename, audio_bytes, mime_type), prompt=WHISPER_TRAVEL_PROMPT, language="en"
            )
            text = transcription.text.strip()
            logger.info(f'🎙️ [Whisper Transcribed] "{text}"')
            return text
        except Exception as e:
            logger.warning(f"⚠️ OpenAI Whisper transcription failed ({e}), trying Gemini fallback...")

    if settings.GEMINI_API_KEY:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            res = await client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=[
                    types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                    "Generate a direct transcript of this speech. Return ONLY the transcribed text without quotes, formatting, or commentary.",
                ],
            )
            text = (res.text or "").strip()
            logger.info(f'🎙️ [Gemini Transcribed] "{text}"')
            return text
        except Exception as e:
            logger.error(f"❌ Gemini audio transcription failed: {e}")

    if settings.OPENAI_API_KEY:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            transcription = await client.audio.transcriptions.create(
                model="whisper-1", file=(filename, audio_bytes, mime_type), prompt=WHISPER_TRAVEL_PROMPT, language="en"
            )
            text = transcription.text.strip()
            logger.info(f'🎙️ [Whisper Transcribed] "{text}"')
            return text
        except Exception as e:
            logger.error(f"❌ OpenAI Whisper transcription failed: {e}")
            return None


def transcribe_audio(audio_source: Union[bytes, str], mime_type: str = "audio/ogg", filename: str = "voice.oga") -> Optional[str]:
    """Synchronous wrapper for transcribe_audio_async."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, transcribe_audio_async(audio_source, mime_type, filename)).result()
        return loop.run_until_complete(transcribe_audio_async(audio_source, mime_type, filename))
    except Exception:
        # Fallback to direct synchronous OpenAI client
        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            audio_bytes: Optional[bytes] = None
            if isinstance(audio_source, bytes):
                audio_bytes = audio_source
            elif isinstance(audio_source, str) and os.path.exists(audio_source):
                with open(audio_source, "rb") as f:
                    audio_bytes = f.read()
            elif isinstance(audio_source, str) and audio_source.startswith("http"):
                with httpx.Client(timeout=25.0) as cl:
                    resp = cl.get(audio_source)
                    if resp.status_code == 200:
                        audio_bytes = resp.content

            if not audio_bytes:
                return None

            res = client.audio.transcriptions.create(
                model="whisper-1", file=(filename, audio_bytes, mime_type), prompt=WHISPER_TRAVEL_PROMPT, language="en"
            )
            return res.text.strip()
        except Exception as ex:
            logger.error(f"❌ Sync Whisper transcription failed: {ex}")
            return None
