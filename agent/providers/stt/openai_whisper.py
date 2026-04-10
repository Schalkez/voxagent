"""OpenAI Whisper API STT provider.

Cloud-based speech-to-text using OpenAI's Whisper API.
Requires an OpenAI API key stored in the OS keyring.
Uses the shared httpx.AsyncClient from HttpProvider for connection pooling.
"""

from __future__ import annotations

import time

from core.keyring_manager import get_key
from core.logging import get_logger
from providers.base import STTProvider, TranscribeResult

logger = get_logger(module="providers.stt.openai_whisper")

_API_URL = "https://api.openai.com/v1/audio/transcriptions"
_DEFAULT_MODEL = "whisper-1"


class OpenAIWhisperProvider(STTProvider):
    """OpenAI Whisper API STT provider."""

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        """Initialize the OpenAI Whisper provider.

        Args:
            model: Model to use (currently only 'whisper-1' available).
        """
        self._model = model
        self._api_key = get_key("openai") or ""

    async def transcribe(self, audio: bytes, language: str = "vi") -> TranscribeResult:
        """Transcribe WAV audio bytes via OpenAI Whisper API.

        Args:
            audio: Raw audio data in WAV format.
            language: Target language code for transcription.

        Returns:
            TranscribeResult with transcribed text and metadata.
        """
        if not self._api_key:
            return TranscribeResult(text="", confidence=0.0, language=language, duration_ms=0)

        start_ms = time.monotonic()

        headers = {"Authorization": f"Bearer {self._api_key}"}
        files = {"file": ("audio.wav", audio, "audio/wav")}
        data = {
            "model": self._model,
            "language": language,
            "response_format": "verbose_json",
        }

        resp = await self.http_client.post(_API_URL, headers=headers, files=files, data=data)
        resp.raise_for_status()
        result = resp.json()

        text = result.get("text", "").strip()
        detected_lang = result.get("language", language)
        audio_duration = result.get("duration", 0.0)
        duration_ms = int((time.monotonic() - start_ms) * 1000)

        logger.debug(
            "transcribed via openai",
            text=text[:50],
            language=detected_lang,
            audio_duration_s=audio_duration,
            api_latency_ms=duration_ms,
        )

        return TranscribeResult(
            text=text,
            confidence=0.95,  # OpenAI API doesn't return confidence -- using fixed estimate
            language=detected_lang,
            duration_ms=duration_ms,
        )

    async def health_check(self) -> bool:
        """Check if OpenAI API key is available and valid."""
        if not self._api_key:
            return False
        try:
            resp = await self.http_client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            return resp.status_code == 200
        except Exception:
            return False
