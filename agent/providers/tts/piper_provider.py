"""Piper TTS provider — local neural text-to-speech engine.

Piper is a fast, local neural TTS system that runs entirely on-device.
Supports many languages including Vietnamese. No API key or network required.

See: https://github.com/rhasspy/piper
"""

from __future__ import annotations

import asyncio
import io
import logging
import shutil
import wave
from pathlib import Path

from providers.base import TTSProvider

logger = logging.getLogger("voxagent.providers.tts.piper")

_DEFAULT_MODEL = "vi_VN-vais1000-medium"
_DEFAULT_SPEAKER_ID = 0

_VOICE_MODEL_MAP: dict[str, str] = {
    "vi-female": "vi_VN-vais1000-medium",
    "vi-male": "vi_VN-vais1000-medium",
    "en-female": "en_US-amy-medium",
    "en-male": "en_US-ryan-medium",
    "ja-female": "ja_JP-tsukuyomi-medium",
}


class PiperTTSProvider(TTSProvider):
    """Local neural TTS using the Piper engine.

    Calls the ``piper`` CLI binary via subprocess. Audio is generated
    locally with zero network latency and no API key requirement.
    """

    def __init__(
        self,
        piper_binary: str | None = None,
        models_dir: str | None = None,
        default_model: str = _DEFAULT_MODEL,
    ) -> None:
        """Initialize the Piper TTS provider.

        Args:
            piper_binary: Path to the ``piper`` executable. Auto-detected
                from PATH if not specified.
            models_dir: Directory containing Piper ONNX model files.
                Defaults to ``~/.local/share/piper/models``.
            default_model: Default voice model name.
        """
        self._piper_binary = piper_binary or shutil.which("piper")
        self._models_dir = Path(
            models_dir or Path.home() / ".local" / "share" / "piper" / "models"
        )
        self._default_model = default_model

    async def synthesize(
        self, text: str, voice: str = "vi-female", speed: float = 1.0
    ) -> bytes:
        """Synthesize text to WAV audio bytes using Piper.

        Args:
            text: Text to convert to speech.
            voice: Voice identifier (e.g., 'vi-female', 'en-male')
                or a direct Piper model name.
            speed: Playback speed multiplier (1.0 = normal).

        Returns:
            Raw audio bytes in WAV format (16kHz, mono, 16-bit).

        Raises:
            RuntimeError: If the Piper binary is not found or synthesis fails.
        """
        if self._piper_binary is None:
            msg = (
                "Piper binary not found. Install Piper: "
                "pip install piper-tts  or download from "
                "https://github.com/rhasspy/piper/releases"
            )
            raise RuntimeError(msg)

        model_name = _VOICE_MODEL_MAP.get(voice, voice)
        model_path = self._resolve_model_path(model_name)

        cmd = [
            self._piper_binary,
            "--model", str(model_path),
            "--output-raw",
            "--length-scale", str(1.0 / speed),
            "--speaker", str(_DEFAULT_SPEAKER_ID),
        ]

        logger.debug("Running Piper: %s", " ".join(cmd))

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate(input=text.encode("utf-8"))

        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace").strip()
            msg = f"Piper synthesis failed (exit {process.returncode}): {error_msg}"
            raise RuntimeError(msg)

        # Piper --output-raw produces raw PCM (16kHz, 16-bit, mono)
        wav_data = _raw_pcm_to_wav(stdout)

        logger.debug(
            "Synthesized %d chars → %d bytes WAV (model=%s, speed=%.1f)",
            len(text),
            len(wav_data),
            model_name,
            speed,
        )

        return wav_data

    async def health_check(self) -> bool:
        """Check if Piper binary is available.

        Returns:
            True if the piper binary is found in the system.
        """
        if self._piper_binary is None:
            return False

        try:
            process = await asyncio.create_subprocess_exec(
                self._piper_binary, "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            return process.returncode == 0
        except (OSError, FileNotFoundError):
            return False

    def _resolve_model_path(self, model_name: str) -> Path:
        """Resolve a model name to its ONNX file path.

        Supports both absolute paths and model names that are resolved
        relative to the models directory.

        Args:
            model_name: Model name or absolute path.

        Returns:
            Path to the ONNX model file.

        Raises:
            FileNotFoundError: If the model file cannot be found.
        """
        # If it's already a full path
        candidate = Path(model_name)
        if candidate.is_absolute() and candidate.exists():
            return candidate

        # Try models directory
        onnx_path = self._models_dir / f"{model_name}.onnx"
        if onnx_path.exists():
            return onnx_path

        # Try with nested directory structure: model_name/model_name.onnx
        nested = self._models_dir / model_name / f"{model_name}.onnx"
        if nested.exists():
            return nested

        # Return the direct path — Piper will error with a clear message
        return onnx_path


def _raw_pcm_to_wav(
    pcm_data: bytes,
    sample_rate: int = 22050,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Wrap raw PCM bytes in a WAV header.

    Args:
        pcm_data: Raw PCM audio data.
        sample_rate: Audio sample rate in Hz (Piper default: 22050).
        channels: Number of audio channels (1 = mono).
        sample_width: Bytes per sample (2 = 16-bit).

    Returns:
        Complete WAV file as bytes.
    """
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return wav_buffer.getvalue()
