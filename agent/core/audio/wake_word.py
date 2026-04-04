"""WakeWordDetector: Wake word detection using OpenWakeWord.

Single responsibility: detect wake word in audio stream.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger("voxagent.audio.wake_word")

# ── Named Constants ───────────────────────────────

DEFAULT_SENSITIVITY: float = 0.7


class WakeWordDetector:
    """Detects wake words in audio using OpenWakeWord (ONNX backend).

    Wraps the openwakeword.Model and provides a clean interface
    for feeding audio and checking detection scores.

    Args:
        sensitivity: Minimum confidence to trigger detection.
    """

    def __init__(self, sensitivity: float = DEFAULT_SENSITIVITY) -> None:
        self._sensitivity = sensitivity
        self._model: object | None = None

    def load(self) -> None:
        """Load the OpenWakeWord model.

        deps-lazy-load: openwakeword imported at use site.
        """
        from openwakeword.model import Model as OpenWakeWordModel

        self._model = OpenWakeWordModel(inference_framework="onnx")
        logger.info("OpenWakeWord model loaded (ONNX backend)")

    def unload(self) -> None:
        """Release the model from memory."""
        self._model = None

    def detect(self, audio_chunk: np.ndarray) -> bool:
        """Feed an audio chunk and check for wake word detection.

        Args:
            audio_chunk: Raw int16 audio data.

        Returns:
            True if wake word detected above sensitivity threshold.

        Raises:
            RuntimeError: If model is not loaded.
        """
        if self._model is None:
            raise RuntimeError("WakeWordDetector not loaded. Call load() first.")

        audio_flat = audio_chunk.flatten()
        self._model.predict(audio_flat)

        for model_name, score in self._model.prediction_buffer.items():
            latest_score = score[-1] if score else 0.0
            if latest_score >= self._sensitivity:
                logger.info(
                    "Wake word '%s' detected (score=%.3f, threshold=%.2f)",
                    model_name,
                    latest_score,
                    self._sensitivity,
                )
                self._model.reset()
                return True

        return False
