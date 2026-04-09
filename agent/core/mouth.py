"""MOUTH module: Text-to-speech output with Vietnamese templates.

Integrates with TTSProvider to synthesize speech and plays audio
through the system speakers using sounddevice.
"""

from __future__ import annotations

import asyncio
import io
import logging
import wave
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from core.errors import AudioError

if TYPE_CHECKING:
    from providers.base import TTSProvider

logger = logging.getLogger("voxagent.mouth")


@dataclass(frozen=True)
class SpeechConfig:
    """Configuration for TTS synthesis.

    Attributes:
        voice: Voice identifier (e.g., 'vi-female', 'en-male').
        speed: Playback speed multiplier (1.0 = normal).
        volume: Volume level from 0.0 to 1.0.
    """

    voice: str = "vi-female"
    speed: float = 1.0
    volume: float = 1.0


RESPONSE_TEMPLATES: dict[str, str] = {
    "success": "Đã {action} rồi nha",
    "report": "Hiện tại {state}. {detail}",
    "error": "Không {action} được vì {reason}",
    "confirm": "Ý anh là {option_a} hay {option_b}?",
    "thinking": "Để tôi xem...",
    "dangerous": "Hành động {action} có thể nguy hiểm. Anh có chắc không?",
    "cancelled": "Đã hủy thao tác.",
}

_DEFAULT_CONFIG = SpeechConfig()


class Mouth:
    """Manages TTS output with Vietnamese response templates.

    Supports multiple TTS providers (Edge TTS, Piper, OpenAI, ElevenLabs)
    and provides a template system for consistent Vietnamese responses.
    """

    def __init__(self, tts_provider: TTSProvider | None = None) -> None:
        """Initialize the Mouth module.

        Args:
            tts_provider: TTS provider for speech synthesis. If None, speak() is a no-op.
        """
        self._tts = tts_provider

    async def speak(self, text: str, config: SpeechConfig | None = None) -> None:
        """Synthesize text to speech and play through speakers.

        Args:
            text: Text to speak.
            config: Optional speech configuration overrides.
        """
        if not text:
            return

        if self._tts is None:
            logger.warning("No TTS provider configured — skipping speech: %s", text[:50])
            return

        cfg = config or _DEFAULT_CONFIG

        try:
            wav_data = await self._tts.synthesize(text, voice=cfg.voice, speed=cfg.speed)
            await _play_wav(wav_data, volume=cfg.volume)
            logger.debug("Spoke: '%s' (voice=%s)", text[:50], cfg.voice)
        except (AudioError, RuntimeError, OSError):
            logger.exception("Failed to speak: '%s'", text[:50])

    async def play_earcon(self, sound: str) -> None:
        """Play a short notification sound.

        Used for feedback sounds like confirmation beeps,
        error tones, and thinking indicators.

        Args:
            sound: Sound identifier (e.g., 'beep', 'ding', 'error').
        """
        # TODO(Phase 2): Implement earcon playback with bundled WAV files
        logger.debug("Earcon requested: %s (not yet implemented)", sound)

    def format_response(self, template_name: str, **kwargs: str) -> str:
        """Format a response using Vietnamese templates.

        Args:
            template_name: Key in RESPONSE_TEMPLATES.
            **kwargs: Values to interpolate into the template.

        Returns:
            Formatted response string.

        Raises:
            KeyError: If template_name is not found.
        """
        template = RESPONSE_TEMPLATES[template_name]
        return template.format(**kwargs)


async def _play_wav(wav_data: bytes, volume: float = 1.0) -> None:
    """Play WAV audio bytes through the default speaker.

    Uses asyncio.to_thread to avoid blocking the event loop
    during sounddevice playback.

    Args:
        wav_data: Raw audio data in WAV format.
        volume: Volume level from 0.0 to 1.0.
    """
    try:
        import sounddevice as sd  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("sounddevice not installed — cannot play audio")
        return

    def _play_blocking() -> None:
        with wave.open(io.BytesIO(wav_data), "rb") as wf:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            raw_frames = wf.readframes(wf.getnframes())
            audio = np.frombuffer(raw_frames, dtype=np.int16)

        audio_out = audio.reshape(-1, channels) if channels > 1 else audio

        if volume < 1.0:
            audio_out = (audio_out.astype(np.float32) * volume).astype(np.int16)

        sd.play(audio_out, samplerate=sample_rate)
        sd.wait()

    try:
        await asyncio.to_thread(_play_blocking)
    except (OSError, ValueError, wave.Error) as e:
        raise AudioError(
            f"Audio playback failed: {e}",
            user_message="Khong the phat am thanh.",
        ) from e
