"""Whisper local STT provider using faster-whisper (CTranslate2 backend).

Runs entirely on-device — no API key needed. Supports Vietnamese
and 90+ other languages with configurable model sizes.
"""

from __future__ import annotations

import io
import logging
import time
from typing import Any

from providers.base import STTProvider, TranscribeResult

logger = logging.getLogger("voxagent.providers.stt.whisper_local")

_DEFAULT_MODEL_SIZE = "base"
_SUPPORTED_SIZES = ("tiny", "base", "small", "medium", "large-v3")


class WhisperLocalProvider(STTProvider):
    """Local Whisper STT provider using faster-whisper."""

    def __init__(
        self,
        model_size: str = _DEFAULT_MODEL_SIZE,
        device: str = "auto",
        compute_type: str = "default",
    ) -> None:
        """Initialize the Whisper provider.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v3).
            device: Device to run on ('cpu', 'cuda', or 'auto').
            compute_type: Quantization type ('default', 'int8', 'float16').
        """
        self._model_size = model_size if model_size in _SUPPORTED_SIZES else _DEFAULT_MODEL_SIZE
        self._device = device
        self._compute_type = compute_type
        self._model: Any = None

    def _ensure_model(self) -> None:
        """Lazy-load the Whisper model on first use."""
        if self._model is not None:
            return

        try:
            from faster_whisper import WhisperModel  # type: ignore[import-untyped]
        except ImportError as err:
            msg = "faster-whisper not installed. Run: pip install faster-whisper"
            raise RuntimeError(msg) from err

        logger.info("Loading Whisper model: %s (device=%s)", self._model_size, self._device)
        self._model = WhisperModel(
            self._model_size,
            device=self._device,
            compute_type=self._compute_type,
        )
        logger.info("Whisper model loaded successfully")

    async def transcribe(self, audio: bytes, language: str = "vi") -> TranscribeResult:
        """Transcribe WAV audio bytes to text.

        Args:
            audio: Raw audio data in WAV format.
            language: Target language code for transcription.

        Returns:
            TranscribeResult with transcribed text and metadata.
        """
        self._ensure_model()

        start_ms = time.monotonic()

        audio_file = io.BytesIO(audio)
        segments, info = self._model.transcribe(
            audio_file,
            language=language,
            beam_size=5,
            vad_filter=True,
        )

        text_parts = [segment.text.strip() for segment in segments]
        text = " ".join(text_parts)
        duration_ms = int((time.monotonic() - start_ms) * 1000)

        confidence = getattr(info, "language_probability", 0.0)

        logger.debug(
            "Transcribed %d bytes → '%s' (lang=%s, conf=%.2f, %dms)",
            len(audio),
            text[:50],
            info.language,
            confidence,
            duration_ms,
        )

        return TranscribeResult(
            text=text,
            confidence=float(confidence),
            language=info.language,
            duration_ms=duration_ms,
        )

    async def health_check(self) -> bool:
        """Check if the Whisper model can be loaded."""
        try:
            self._ensure_model()
            return True
        except (RuntimeError, OSError):
            return False
