"""Voice cloning TTS interface.

Abstract base for voice cloning services (ElevenLabs, XTTS, etc.).
Concrete implementations should handle audio processing and API calls.
"""

from __future__ import annotations

from abc import abstractmethod

from providers.base import TTSProvider


class VoiceCloneProvider(TTSProvider):
    """Abstract interface for voice cloning TTS services.

    Extends TTSProvider with voice cloning capabilities.
    """

    @abstractmethod
    async def clone_voice(self, audio_samples: list[bytes], voice_name: str) -> str:
        """Create a voice clone from audio samples.

        Args:
            audio_samples: List of WAV audio byte samples for training.
            voice_name: Human-readable name for the cloned voice.

        Returns:
            Voice ID string for use in synthesize().
        """

    @abstractmethod
    async def list_cloned_voices(self) -> list[str]:
        """List all available cloned voice IDs.

        Returns:
            List of voice ID strings.
        """

    @abstractmethod
    async def delete_voice(self, voice_id: str) -> bool:
        """Delete a cloned voice.

        Args:
            voice_id: ID of the voice to delete.

        Returns:
            True if deletion succeeded.
        """
