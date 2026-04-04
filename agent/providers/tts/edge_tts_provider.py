"""Edge TTS provider using Microsoft Edge's free text-to-speech service.

No API key required. Excellent Vietnamese voice support.
"""

from __future__ import annotations

import io
import logging

from providers.base import TTSProvider

logger = logging.getLogger("voxagent.providers.tts.edge_tts")

_DEFAULT_VOICE = "vi-VN-HoaiMyNeural"
_VOICE_MAP: dict[str, str] = {
    "vi-female": "vi-VN-HoaiMyNeural",
    "vi-male": "vi-VN-NamMinhNeural",
    "en-female": "en-US-JennyNeural",
    "en-male": "en-US-GuyNeural",
}


class EdgeTTSProvider(TTSProvider):
    """Microsoft Edge TTS provider — free, no API key needed."""

    async def synthesize(self, text: str, voice: str = "vi-female", speed: float = 1.0) -> bytes:
        """Synthesize text to WAV audio bytes.

        Args:
            text: Text to convert to speech.
            voice: Voice identifier (e.g., 'vi-female', 'en-male').
            speed: Playback speed multiplier (1.0 = normal).

        Returns:
            Raw audio bytes in WAV format.
        """
        try:
            import edge_tts  # type: ignore[import-untyped]
        except ImportError as err:
            msg = "edge-tts not installed. Run: pip install edge-tts"
            raise RuntimeError(msg) from err

        voice_id = _VOICE_MAP.get(voice, voice)

        rate_str = _speed_to_rate(speed)

        communicate = edge_tts.Communicate(text=text, voice=voice_id, rate=rate_str)

        audio_chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        mp3_data = b"".join(audio_chunks)

        wav_data = await _mp3_to_wav(mp3_data)

        logger.debug(
            "Synthesized %d chars → %d bytes WAV (voice=%s, speed=%.1f)",
            len(text),
            len(wav_data),
            voice_id,
            speed,
        )

        return wav_data

    async def health_check(self) -> bool:
        """Check if Edge TTS is available."""
        try:
            import edge_tts  # type: ignore[import-untyped]

            voices = await edge_tts.list_voices()
            return len(voices) > 0
        except Exception:
            return False


def _speed_to_rate(speed: float) -> str:
    """Convert speed multiplier to Edge TTS rate string.

    Args:
        speed: Speed multiplier (1.0 = normal).

    Returns:
        Rate string like '+0%', '+50%', '-25%'.
    """
    percent = int((speed - 1.0) * 100)
    if percent >= 0:
        return f"+{percent}%"
    return f"{percent}%"


async def _mp3_to_wav(mp3_data: bytes) -> bytes:
    """Convert MP3 bytes to WAV format.

    Args:
        mp3_data: Raw MP3 audio bytes.

    Returns:
        WAV-formatted audio bytes.
    """
    try:
        from pydub import AudioSegment  # type: ignore[import-untyped]

        audio = AudioSegment.from_mp3(io.BytesIO(mp3_data))
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        wav_buffer = io.BytesIO()
        audio.export(wav_buffer, format="wav")
        return wav_buffer.getvalue()
    except ImportError:
        logger.warning("pydub not installed — returning raw MP3. Install pydub for WAV output.")
        return mp3_data
