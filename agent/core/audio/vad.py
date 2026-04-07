"""VoiceActivityDetector: Speech vs silence detection.

Single responsibility: determine if an audio chunk contains speech.
Uses Silero VAD (ONNX) with energy-based fallback.
"""

from __future__ import annotations

import logging

import numpy as np

from core.audio.recorder import SAMPLE_RATE

logger = logging.getLogger("voxagent.audio.vad")

# ── Named Constants ───────────────────────────────

SPEECH_THRESHOLD: float = 0.5  # Silero VAD confidence threshold
ENERGY_THRESHOLD: float = 500.0  # RMS energy threshold for fallback


class VoiceActivityDetector:
    """Detects speech in audio chunks using Silero VAD or energy fallback.

    Attempts to use the Silero VAD ONNX model for accurate detection.
    Falls back to simple RMS energy-based detection if Silero is
    unavailable or fails.

    Args:
        speech_threshold: Silero VAD confidence threshold.
        energy_threshold: RMS energy threshold for fallback.
    """

    def __init__(
        self,
        speech_threshold: float = SPEECH_THRESHOLD,
        energy_threshold: float = ENERGY_THRESHOLD,
    ) -> None:
        self._speech_threshold = speech_threshold
        self._energy_threshold = energy_threshold
        self._model: object = None

    def load(self) -> None:
        """Load the Silero VAD model via ONNX Runtime.

        Falls back gracefully if silero-vad is not installed.
        """
        try:
            # deps-lazy-load: heavy imports at use site
            from silero_vad import load_silero_vad

            self._model = load_silero_vad(onnx=True)
            logger.info("Silero VAD loaded (ONNX backend)")
        except ImportError:
            logger.warning("silero-vad not installed — using energy-based VAD fallback")
            self._model = None

    def unload(self) -> None:
        """Release the model from memory."""
        self._model = None

    @property
    def is_loaded(self) -> bool:
        """Whether the Silero VAD model is loaded."""
        return self._model is not None

    def detect_speech(self, audio_chunk: np.ndarray) -> bool:
        """Determine if an audio chunk contains speech.

        Args:
            audio_chunk: Audio frame (int16 numpy array).

        Returns:
            True if speech is detected in the chunk.
        """
        if self._model is not None:
            return self._silero_detect(audio_chunk)
        return self._energy_detect(audio_chunk)

    def _silero_detect(self, audio_chunk: np.ndarray) -> bool:
        """Run Silero VAD model on an audio chunk."""
        try:
            # deps-lazy-load: torch only needed for Silero VAD
            import torch

            model = self._model
            if model is None:
                return self._energy_detect(audio_chunk)

            audio_float = audio_chunk.flatten().astype(np.float32) / 32768.0
            audio_tensor = torch.from_numpy(audio_float)
            confidence: float = model(audio_tensor, SAMPLE_RATE).item()
            return confidence > self._speech_threshold
        except (RuntimeError, ValueError, OSError):
            logger.debug("VAD inference error — falling back to energy detection")
            return self._energy_detect(audio_chunk)

    def _energy_detect(self, audio_chunk: np.ndarray) -> bool:
        """Simple energy-based Voice Activity Detection fallback.

        Args:
            audio_chunk: Audio frame (int16 numpy array).

        Returns:
            True if RMS energy exceeds threshold.
        """
        rms = np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2))
        return float(rms) > self._energy_threshold
