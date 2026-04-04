"""AudioConverter: Audio frame → WAV byte conversion.

Single responsibility: convert raw int16 numpy frames to WAV bytes.
"""

from __future__ import annotations

import io
import wave

import numpy as np

from core.audio.recorder import CHANNELS, SAMPLE_RATE


class AudioConverter:
    """Converts raw audio frames to WAV byte format.

    Stateless utility class. All methods are static.
    """

    @staticmethod
    def frames_to_wav(
        frames: list[np.ndarray],
        channels: int = CHANNELS,
        sample_rate: int = SAMPLE_RATE,
    ) -> bytes:
        """Convert a list of audio frames to WAV bytes.

        Args:
            frames: List of int16 numpy arrays.
            channels: Number of audio channels.
            sample_rate: Audio sample rate in Hz.

        Returns:
            WAV file content as bytes.
        """
        audio = np.concatenate(frames, axis=0).flatten()
        buffer = io.BytesIO()

        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)  # 16-bit = 2 bytes
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio.tobytes())

        return buffer.getvalue()
