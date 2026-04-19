import structlog

from llm.interface import TranscriptionClient

logger = structlog.get_logger()


async def transcribe_voice(
    transcriber: TranscriptionClient,
    audio_bytes: bytes,
    user_id: int,
) -> str | None:
    """Transcribe a Telegram voice message (OGG) to text."""
    try:
        text = await transcriber.transcribe(audio_bytes, filename="voice.ogg")
        logger.info("audio.transcribed", user_id=user_id, length=len(text))
        return text.strip() or None
    except Exception:
        logger.exception("audio.transcription_failed", user_id=user_id)
        return None
