from src.adapters.telegram import TelegramAdapter
from src.adapters.whatsapp import WhatsAppAdapter

async def test_telegram_message_normalization():
    adapter = TelegramAdapter()
    sample_payload = {
        "update_id": 1001,
        "message": {
            "message_id": 42,
            "from": {"id": 12345, "first_name": "Alice", "username": "alice_travel"},
            "chat": {"id": -987654, "type": "supergroup", "title": "Weekend Trip"},
            "text": "@companion_bot let's find a hotel in Bali under $100",
            "entities": [{"type": "mention", "offset": 0, "length": 14}]
        }
    }

    event = await adapter.parse_webhook(sample_payload)
    assert event is not None
    assert event.platform == "telegram"
    assert event.channel_id == "-987654"
    assert event.is_group is True
    assert event.sender.name == "Alice"
    assert event.sender.handle == "alice_travel"
    assert event.is_bot_mentioned is True
    assert "Bali" in event.text

async def test_telegram_photo_normalization():
    adapter = TelegramAdapter()
    sample_photo_payload = {
        "update_id": 1002,
        "message": {
            "message_id": 43,
            "from": {"id": 67890, "first_name": "Bob"},
            "chat": {"id": -987654, "type": "supergroup"},
            "caption": "Is this a good place to visit?",
            "photo": [
                {"file_id": "small_thumb", "width": 100, "height": 100},
                {"file_id": "high_res_photo_id", "width": 1280, "height": 720}
            ]
        }
    }

    event = await adapter.parse_webhook(sample_photo_payload)
    assert event is not None
    assert event.media is not None
    assert event.media.type == "photo"
    assert event.media.file_id == "high_res_photo_id"
    assert event.text == "Is this a good place to visit?"

async def test_whatsapp_message_normalization():
    adapter = WhatsAppAdapter()
    sample_payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"profile": {"name": "Charlie"}}],
                    "messages": [{
                        "id": "wamid.HBgL...",
                        "from": "15551234567",
                        "type": "text",
                        "text": {"body": "I paid $90 for lunch"}
                    }]
                }
            }]
        }]
    }

    event = await adapter.parse_webhook(sample_payload)
    assert event is not None
    assert event.platform == "whatsapp"
    assert event.sender.name == "Charlie"
    assert event.channel_id == "15551234567"
    assert event.text == "I paid $90 for lunch"

async def test_telegram_voice_normalization():
    adapter = TelegramAdapter()
    sample_voice_payload = {
        "update_id": 1003,
        "message": {
            "message_id": 44,
            "from": {"id": 11223, "first_name": "Dave"},
            "chat": {"id": -987654, "type": "supergroup"},
            "voice": {
                "file_id": "voice_file_abc123",
                "duration": 4,
                "mime_type": "audio/ogg"
            }
        }
    }

    event = await adapter.parse_webhook(sample_voice_payload)
    assert event is not None
    assert event.media is not None
    assert event.media.type == "voice"
    assert event.media.file_id == "voice_file_abc123"
    assert event.media.mime_type == "audio/ogg"
    assert event.text is not None
    assert "[Voice" in event.text or len(event.text) > 0

async def test_audio_transcription_service():
    import os
    from src.services.transcription import transcribe_audio_async
    test_audio = "/Users/sathish-mac/.gemini/antigravity-ide/brain/6aec9ee4-bb45-472f-88c4-5901d8232638/.user_uploaded/uploaded_media_1789663936530.img"
    if os.path.exists(test_audio):
        text = await transcribe_audio_async(test_audio, mime_type="audio/webm", filename="test.webm")
        assert text is not None
        assert len(text) > 10
        assert any(w in text.lower() for w in ["place", "venue", "expense", "confirmed", "consent"])

