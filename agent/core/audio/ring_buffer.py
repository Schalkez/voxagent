"""AudioRingBuffer: Bounded circular buffer for audio chunks.

Single responsibility: store audio chunks in a pre-allocated ring buffer
with drop-oldest policy. Never blocks, never allocates in write path.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import numpy as np

from core.logging import get_logger

if TYPE_CHECKING:
    import numpy.typing as npt

logger = get_logger(module="ring_buffer")

# ── Named Constants ───────────────────────────────

DEFAULT_CAPACITY: int = 128  # ~10s at 80ms chunks
DROP_LOG_INTERVAL: int = 50  # log every N drops to avoid log spam


class AudioRingBuffer:
    """Bounded circular buffer for int16 audio chunks.

    Pre-allocates all memory at init. The write path (called from the
    real-time sounddevice callback) does zero allocation — only
    ``np.copyto`` into a pre-existing slot and pointer arithmetic.

    Uses drop-oldest policy: when full, the oldest unread chunk is
    silently overwritten, and ``drop_count`` is incremented.

    Thread safety: single-producer (sounddevice callback) /
    single-consumer (asyncio reader) — no locks required.

    Args:
        capacity: Number of chunk slots to pre-allocate.
        chunk_samples: Number of samples per chunk.
        channels: Number of audio channels.
    """

    def __init__(
        self,
        capacity: int = DEFAULT_CAPACITY,
        chunk_samples: int = 1280,
        channels: int = 1,
    ) -> None:
        self._capacity = capacity
        self._buffer: npt.NDArray[np.int16] = np.zeros(
            (capacity, chunk_samples * channels),
            dtype=np.int16,
        )
        self._write_idx: int = 0
        self._read_idx: int = 0
        self._count: int = 0

        # Metrics
        self.drop_count: int = 0
        self.high_watermark: int = 0

        # Notification event for async consumer
        self._data_ready = asyncio.Event()

    @property
    def capacity(self) -> int:
        """Total number of slots in the buffer."""
        return self._capacity

    @property
    def size(self) -> int:
        """Number of unread chunks currently in the buffer."""
        return self._count

    def write(self, chunk: npt.NDArray[np.int16]) -> None:
        """Write a chunk into the next slot. No allocation, no blocking.

        If the buffer is full, the oldest unread chunk is overwritten
        and ``drop_count`` is incremented.

        Args:
            chunk: Flattened int16 audio samples to store.
        """
        if self._count >= self._capacity:
            # Drop oldest: advance read pointer
            self._read_idx = (self._read_idx + 1) % self._capacity
            self._count -= 1
            self.drop_count += 1
            if self.drop_count % DROP_LOG_INTERVAL == 0:
                logger.warning(
                    "audio chunks dropped",
                    total_drops=self.drop_count,
                    capacity=self._capacity,
                )

        np.copyto(self._buffer[self._write_idx], chunk.ravel())
        self._write_idx = (self._write_idx + 1) % self._capacity
        self._count += 1

        # Track high watermark
        if self._count > self.high_watermark:
            self.high_watermark = self._count

        # Signal consumer
        self._data_ready.set()

    async def read(self, timeout: float = 0.5) -> npt.NDArray[np.int16] | None:
        """Read the oldest unread chunk, waiting up to ``timeout`` seconds.

        Returns:
            Copy of the oldest unread chunk, or None on timeout.
        """
        if self._count == 0:
            self._data_ready.clear()
            try:
                await asyncio.wait_for(self._data_ready.wait(), timeout=timeout)
            except TimeoutError:
                return None
            # Re-check after wakeup — may have been cleared by drain
            if self._count == 0:
                return None

        slot = self._buffer[self._read_idx].copy()
        self._read_idx = (self._read_idx + 1) % self._capacity
        self._count -= 1
        return slot

    def drain(self) -> None:
        """Discard all unread chunks. Resets pointers but keeps allocation."""
        self._read_idx = self._write_idx
        self._count = 0
        self._data_ready.clear()

    def reset_metrics(self) -> None:
        """Reset drop_count and high_watermark to zero."""
        self.drop_count = 0
        self.high_watermark = 0
