"""AudioRecorder: Microphone stream management.

Single responsibility: open/close audio stream, enqueue raw chunks.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger("voxagent.audio.recorder")

# ── Named Constants ───────────────────────────────

SAMPLE_RATE: int = 16_000
CHANNELS: int = 1
CHUNK_DURATION_MS: int = 80
CHUNK_SAMPLES: int = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)
AUDIO_QUEUE_TIMEOUT_S: float = 0.5


class AudioRecorder:
    """Manages microphone input stream and audio chunk queue.

    Opens a sounddevice InputStream and pushes raw int16 chunks
    into an asyncio.Queue for downstream consumers.

    Args:
        sample_rate: Audio sample rate in Hz.
        channels: Number of audio channels.
        chunk_samples: Samples per chunk.
    """

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        chunk_samples: int = CHUNK_SAMPLES,
    ) -> None:
        self._sample_rate = sample_rate
        self._channels = channels
        self._chunk_samples = chunk_samples
        self._stream: Any | None = None
        self._audio_queue: asyncio.Queue[np.ndarray] = asyncio.Queue()

    @property
    def is_active(self) -> bool:
        """Whether the audio stream is currently open."""
        return self._stream is not None

    async def start(self) -> None:
        """Open the microphone stream.

        Raises:
            RuntimeError: If microphone is unavailable.
        """
        # deps-lazy-load: heavy import at use site
        import sounddevice as sd

        self._drain_queue()

        try:
            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="int16",
                blocksize=self._chunk_samples,
                callback=self._on_audio_chunk,
            )
            self._stream.start()
            logger.info("Microphone stream opened (rate=%d)", self._sample_rate)
        except (OSError, sd.PortAudioError) as exc:
            raise RuntimeError(f"Failed to open microphone: {exc}") from exc

    async def stop(self) -> None:
        """Close the microphone stream. Safe to call multiple times."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except OSError:
                logger.exception("Error closing audio stream")
            finally:
                self._stream = None
                logger.info("Microphone stream closed")

    async def read_chunk(self) -> np.ndarray | None:
        """Read one audio chunk from the queue with timeout.

        Returns:
            Audio chunk (int16 ndarray) or None if timed out.
        """
        try:
            return await asyncio.wait_for(
                self._audio_queue.get(),
                timeout=AUDIO_QUEUE_TIMEOUT_S,
            )
        except TimeoutError:
            return None

    def _on_audio_chunk(
        self,
        indata: npt.NDArray[np.int16],
        frames: int,
        time_info: object,
        status: object,
    ) -> None:
        """Callback invoked by sounddevice for each audio chunk."""
        import contextlib
        if status:
            logger.warning("Audio stream status: %s", status)
        with contextlib.suppress(asyncio.QueueFull):
            self._audio_queue.put_nowait(indata.copy())

    def _drain_queue(self) -> None:
        """Clear any stale audio from the queue."""
        while not self._audio_queue.empty():
            self._audio_queue.get_nowait()
