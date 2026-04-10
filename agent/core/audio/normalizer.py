"""AudioNormalizer: Validate and convert audio to canonical format.

Single responsibility: ensure all audio reaching downstream consumers
is int16 / 16 kHz / mono — regardless of hardware capture format.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from core.errors import AudioError
from core.logging import get_logger

if TYPE_CHECKING:
    import numpy.typing as npt

logger = get_logger(module="normalizer")

# ── Canonical Format Constants ────────────────────

TARGET_SAMPLE_RATE: int = 16_000
TARGET_CHANNELS: int = 1
TARGET_DTYPE = np.int16

MAX_INT16: int = 32_767
MIN_INT16: int = -32_768


class AudioNormalizer:
    """Validates and converts audio chunks to int16/16kHz/mono.

    Stateless utility. Call ``normalize`` on each chunk at the capture
    point so all downstream consumers receive a consistent format.

    Args:
        target_sample_rate: Desired output sample rate in Hz.
        target_channels: Desired number of channels (1 = mono).
    """

    def __init__(
        self,
        target_sample_rate: int = TARGET_SAMPLE_RATE,
        target_channels: int = TARGET_CHANNELS,
    ) -> None:
        self._target_rate = target_sample_rate
        self._target_channels = target_channels

    def normalize(
        self,
        chunk: npt.NDArray[np.int16 | np.float32 | np.float64],
        source_rate: int = TARGET_SAMPLE_RATE,
        source_channels: int = TARGET_CHANNELS,
    ) -> npt.NDArray[np.int16]:
        """Normalize an audio chunk to canonical int16/16kHz/mono format.

        Processing order: dtype → channels → sample rate.

        Args:
            chunk: Raw audio samples from capture device.
            source_rate: Sample rate of the input chunk.
            source_channels: Number of channels in the input chunk.

        Returns:
            Normalized int16 mono audio at target sample rate.

        Raises:
            AudioError: If the chunk is empty or has an unsupported shape.
        """
        if chunk.size == 0:
            raise AudioError("Empty audio chunk received", user_message="Khong co du lieu am thanh.")

        result = self._to_int16(chunk)
        result = self._to_mono(result, source_channels)
        result = self._resample(result, source_rate)
        return result

    def _to_int16(self, chunk: npt.NDArray[np.number]) -> npt.NDArray[np.int16]:
        """Convert any numeric dtype to int16.

        Args:
            chunk: Audio samples in any numeric dtype.

        Returns:
            Audio samples as int16.
        """
        if chunk.dtype == np.int16:
            return chunk

        if np.issubdtype(chunk.dtype, np.floating):
            scaled = np.clip(chunk * MAX_INT16, MIN_INT16, MAX_INT16)
            return scaled.astype(np.int16)

        if np.issubdtype(chunk.dtype, np.integer):
            return chunk.astype(np.int16)

        raise AudioError(
            f"Unsupported audio dtype: {chunk.dtype}",
            user_message="Dinh dang am thanh khong ho tro.",
        )

    def _to_mono(
        self,
        chunk: npt.NDArray[np.int16],
        source_channels: int,
    ) -> npt.NDArray[np.int16]:
        """Mix multi-channel audio down to mono.

        Args:
            chunk: Audio samples (possibly multi-channel).
            source_channels: Number of channels in the input.

        Returns:
            Mono audio as a flat int16 array.
        """
        if source_channels <= self._target_channels:
            return chunk.ravel()

        # Reshape to (samples, channels) then average
        samples = chunk.ravel()
        n_samples = len(samples) // source_channels
        reshaped = samples[: n_samples * source_channels].reshape(n_samples, source_channels)
        mono = reshaped.mean(axis=1).astype(np.int16)
        return mono

    def _resample(
        self,
        chunk: npt.NDArray[np.int16],
        source_rate: int,
    ) -> npt.NDArray[np.int16]:
        """Resample audio to the target sample rate using linear interpolation.

        Args:
            chunk: Mono int16 audio samples.
            source_rate: Source sample rate in Hz.

        Returns:
            Resampled int16 audio at target rate.
        """
        if source_rate == self._target_rate:
            return chunk

        ratio = self._target_rate / source_rate
        target_length = int(len(chunk) * ratio)

        if target_length == 0:
            return np.array([], dtype=np.int16)

        indices = np.linspace(0, len(chunk) - 1, target_length)
        resampled = np.interp(indices, np.arange(len(chunk)), chunk.astype(np.float64))
        return resampled.astype(np.int16)
