"""AudioRecorder: Microphone stream management.

Single responsibility: open/close audio stream, write raw chunks
into a pre-allocated ring buffer. The sounddevice callback never
allocates memory or blocks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from core.audio.normalizer import AudioNormalizer
from core.audio.ring_buffer import AudioRingBuffer, DEFAULT_CAPACITY
from core.errors import AudioError
from core.logging import get_logger

if TYPE_CHECKING:
    import numpy.typing as npt

logger = get_logger(module="recorder")

# ── Named Constants ───────────────────────────────

SAMPLE_RATE: int = 16_000
CHANNELS: int = 1
CHUNK_DURATION_MS: int = 80
CHUNK_SAMPLES: int = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)
AUDIO_QUEUE_TIMEOUT_S: float = 0.5


class AudioRecorder:
    """Manages microphone input stream and audio ring buffer.

    Opens a sounddevice InputStream and writes raw int16 chunks
    into an AudioRingBuffer for downstream consumers. The capture
    callback is allocation-free: it copies into pre-allocated slots.

    Audio is normalized to int16/16kHz/mono at the capture point.

    Args:
        sample_rate: Audio sample rate in Hz.
        channels: Number of audio channels.
        chunk_samples: Samples per chunk.
        buffer_capacity: Number of ring buffer slots.
    """

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        chunk_samples: int = CHUNK_SAMPLES,
        buffer_capacity: int = DEFAULT_CAPACITY,
    ) -> None:
        self._sample_rate = sample_rate
        self._channels = channels
        self._chunk_samples = chunk_samples
        self._stream: object = None
        self._ring_buffer = AudioRingBuffer(
            capacity=buffer_capacity,
            chunk_samples=chunk_samples,
            channels=1,  # always mono after normalization
        )
        self._normalizer = AudioNormalizer(
            target_sample_rate=sample_rate,
            target_channels=1,
        )

    @property
    def is_active(self) -> bool:
        """Whether the audio stream is currently open."""
        return self._stream is not None

    @property
    def ring_buffer(self) -> AudioRingBuffer:
        """Direct access to the ring buffer for metric inspection."""
        return self._ring_buffer

    async def start(self) -> None:
        """Open the microphone stream.

        Raises:
            AudioError: If microphone is unavailable.
        """
        # deps-lazy-load: heavy import at use site
        import sounddevice as sd

        self._ring_buffer.drain()
        self._ring_buffer.reset_metrics()

        try:
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="int16",
                blocksize=self._chunk_samples,
                callback=self._on_audio_chunk,
            )
            self._stream.start()
            logger.info("microphone stream opened", rate=self._sample_rate)
        except (OSError, Exception) as exc:
            raise AudioError(
                f"Failed to open microphone: {exc}",
                user_message="Khong the khoi dong micro.",
            ) from exc

    async def stop(self) -> None:
        """Close the microphone stream. Safe to call multiple times."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except OSError:
                logger.exception("error closing audio stream")
            finally:
                self._stream = None
                logger.info(
                    "microphone stream closed",
                    drop_count=self._ring_buffer.drop_count,
                    high_watermark=self._ring_buffer.high_watermark,
                )

    async def read_chunk(self) -> npt.NDArray[np.int16] | None:
        """Read one audio chunk from the ring buffer with timeout.

        Returns:
            Audio chunk (int16 ndarray) or None if timed out.
        """
        return await self._ring_buffer.read(timeout=AUDIO_QUEUE_TIMEOUT_S)

    def _on_audio_chunk(
        self,
        indata: npt.NDArray[np.int16],
        _frames: int,
        _time_info: object,
        status: object,
    ) -> None:
        """Callback invoked by sounddevice for each audio chunk.

        Runs on PortAudio's C thread. MUST NOT allocate, block, or raise.
        Normalizes to int16/mono and writes into the pre-allocated ring
        buffer slot via ``np.copyto``.
        """
        try:
            if status:
                logger.warning("audio stream status: %s", status)

            # Normalize at capture point (handles dtype/channel/rate)
            normalized = self._normalizer.normalize(
                indata,
                source_rate=self._sample_rate,
                source_channels=self._channels,
            )
            self._ring_buffer.write(normalized)
        except Exception:
            # Callback must NEVER raise — PortAudio would kill the stream
            pass
