import io

import openai


class WhisperTranscriber:
    def __init__(self, api_key: str) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key)

    async def transcribe(self, audio_bytes: bytes, filename: str = "voice.ogg") -> str:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename

        transcript = await self._client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text",
        )
        return str(transcript)
