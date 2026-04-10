"""ElevenLabs voice cloning TTS provider.

Implements VoiceCloneProvider using the ElevenLabs API v1
for text-to-speech synthesis with voice cloning support.
Uses the shared httpx.AsyncClient from HttpProvider for connection pooling.
"""

from __future__ import annotations

import os

from core.logging import get_logger
from providers.tts.voice_cloning import VoiceCloneProvider

logger = get_logger(module="providers.tts.elevenlabs_clone")

_BASE_URL = "https://api.elevenlabs.io/v1"
_DEFAULT_MODEL = "eleven_multilingual_v2"
_DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
_TIMEOUT_SECONDS = 30
_CLONE_TIMEOUT_SECONDS = 120


def _get_api_key() -> str:
    """Resolve the ElevenLabs API key from env or OS keyring.

    Returns:
        API key string.

    Raises:
        RuntimeError: If no API key is found.
    """
    key = os.environ.get("ELEVENLABS_API_KEY")
    if key:
        return key

    try:
        import keyring  # type: ignore[import-untyped]

        key = keyring.get_password("voxagent", "elevenlabs_api_key")
    except ImportError:
        pass

    if not key:
        msg = (
            "ElevenLabs API key not found. "
            "Set ELEVENLABS_API_KEY env var or store in OS keyring."
        )
        raise RuntimeError(msg)

    return key


class ElevenLabsCloneProvider(VoiceCloneProvider):
    """ElevenLabs TTS provider with voice cloning capabilities."""

    async def synthesize(
        self,
        text: str,
        voice: str = "vi-female",
        speed: float = 1.0,
    ) -> bytes:
        """Synthesize text to audio using an ElevenLabs voice.

        Args:
            text: Text to convert to speech.
            voice: Voice ID or friendly name (defaults to Rachel).
            speed: Playback speed multiplier (1.0 = normal).

        Returns:
            Raw audio bytes in WAV format.

        Raises:
            RuntimeError: If the API call fails.
        """
        voice_id = voice if _looks_like_voice_id(voice) else _DEFAULT_VOICE_ID
        url = f"{_BASE_URL}/text-to-speech/{voice_id}"
        headers = _build_headers()
        payload = {
            "text": text,
            "model_id": _DEFAULT_MODEL,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": speed},
        }

        response = await self.http_client.post(url, headers=headers, json=payload)
        _raise_on_api_error(response)

        audio_bytes = response.content
        logger.debug(
            "synthesized via elevenlabs",
            text_len=len(text),
            audio_bytes=len(audio_bytes),
            voice=voice_id,
            speed=speed,
        )
        return audio_bytes

    async def clone_voice(self, audio_samples: list[bytes], voice_name: str) -> str:
        """Create a voice clone from audio samples via ElevenLabs API.

        Args:
            audio_samples: List of WAV audio byte samples for training.
            voice_name: Human-readable name for the cloned voice.

        Returns:
            Voice ID string for use in synthesize().

        Raises:
            RuntimeError: If the API call fails or no samples provided.
        """
        if not audio_samples:
            msg = "At least one audio sample is required for voice cloning."
            raise RuntimeError(msg)

        url = f"{_BASE_URL}/voices/add"
        headers = _build_headers(content_type=False)
        files = _build_sample_files(audio_samples)
        data = {"name": voice_name}

        response = await self.http_client.post(url, headers=headers, data=data, files=files)
        _raise_on_api_error(response)

        voice_id: str = response.json()["voice_id"]
        logger.info("cloned voice", voice_name=voice_name, voice_id=voice_id)
        return voice_id

    async def list_cloned_voices(self) -> list[str]:
        """List all available cloned voice IDs from ElevenLabs.

        Returns:
            List of voice ID strings.

        Raises:
            RuntimeError: If the API call fails.
        """
        url = f"{_BASE_URL}/voices"
        headers = _build_headers()

        response = await self.http_client.get(url, headers=headers)
        _raise_on_api_error(response)

        voices = response.json().get("voices", [])
        cloned = [v["voice_id"] for v in voices if v.get("category") == "cloned"]
        logger.debug("found cloned voices", count=len(cloned))
        return cloned

    async def delete_voice(self, voice_id: str) -> bool:
        """Delete a cloned voice from ElevenLabs.

        Args:
            voice_id: ID of the voice to delete.

        Returns:
            True if deletion succeeded.
        """
        url = f"{_BASE_URL}/voices/{voice_id}"
        headers = _build_headers()

        response = await self.http_client.delete(url, headers=headers)

        if response.status_code == 200:
            logger.info("deleted voice", voice_id=voice_id)
            return True

        logger.warning("failed to delete voice", voice_id=voice_id, status=response.status_code)
        return False

    async def health_check(self) -> bool:
        """Check if the ElevenLabs API is reachable.

        Returns:
            True if the API responds successfully.
        """
        try:
            headers = _build_headers()
            response = await self.http_client.get(f"{_BASE_URL}/voices", headers=headers)
            return response.status_code == 200
        except (RuntimeError, Exception):
            return False


def _build_headers(*, content_type: bool = True) -> dict[str, str]:
    """Build common request headers with API key.

    Args:
        content_type: Whether to include application/json content type.

    Returns:
        Headers dict.
    """
    headers: dict[str, str] = {"xi-api-key": _get_api_key()}
    if content_type:
        headers["Content-Type"] = "application/json"
    return headers


def _build_sample_files(audio_samples: list[bytes]) -> list[tuple[str, tuple[str, bytes, str]]]:
    """Build multipart file tuples for voice cloning upload.

    Args:
        audio_samples: List of WAV audio byte samples.

    Returns:
        List of file tuples for httpx multipart upload.
    """
    return [
        ("files", (f"sample_{i}.wav", sample, "audio/wav"))
        for i, sample in enumerate(audio_samples)
    ]


def _looks_like_voice_id(voice: str) -> bool:
    """Check if a string looks like an ElevenLabs voice ID.

    Args:
        voice: Voice identifier string.

    Returns:
        True if it appears to be a raw voice ID.
    """
    min_id_length = 12
    return len(voice) >= min_id_length and voice.isalnum()


def _raise_on_api_error(response: object) -> None:
    """Raise RuntimeError if the API response indicates failure.

    Args:
        response: httpx Response object.

    Raises:
        RuntimeError: With status code and error detail from the API.
    """
    import httpx

    if not isinstance(response, httpx.Response):
        msg = "Expected httpx.Response"
        raise TypeError(msg)

    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", {}).get("message", response.text)
        except (ValueError, AttributeError):
            detail = response.text
        msg = f"ElevenLabs API error {response.status_code}: {detail}"
        raise RuntimeError(msg)
