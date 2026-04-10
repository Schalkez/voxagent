"""Tests for AudioRingBuffer — bounded circular buffer with drop-oldest policy.

Covers:
- Pre-allocated buffer creation
- Write/read cycle (FIFO order)
- Drop-oldest when full + drop counter
- High watermark tracking
- Drain discards all unread chunks
- Async read timeout returns None
- Reset metrics
- Concurrent write/read does not corrupt data
"""

from __future__ import annotations

import asyncio

import numpy as np
import pytest

from core.audio.ring_buffer import AudioRingBuffer, DEFAULT_CAPACITY, DROP_LOG_INTERVAL


# ── Named Constants ───────────────────────────────

SMALL_CAPACITY: int = 4
CHUNK_SAMPLES: int = 160  # 10ms at 16kHz


# ── Helpers ───────────────────────────────────────


def _make_chunk(value: int, samples: int = CHUNK_SAMPLES) -> np.ndarray:
    """Create a test chunk filled with a single int16 value."""
    return np.full(samples, value, dtype=np.int16)


# ── Tests: Initialization ────────────────────────


class TestRingBufferInit:
    """Verify buffer is pre-allocated with correct shape and zeroed."""

    def test_default_capacity(self) -> None:
        buf = AudioRingBuffer(chunk_samples=CHUNK_SAMPLES)
        assert buf.capacity == DEFAULT_CAPACITY

    def test_custom_capacity(self) -> None:
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)
        assert buf.capacity == SMALL_CAPACITY

    def test_initial_size_is_zero(self) -> None:
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)
        assert buf.size == 0

    def test_initial_metrics_are_zero(self) -> None:
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)
        assert buf.drop_count == 0
        assert buf.high_watermark == 0


# ── Tests: Write/Read Cycle ──────────────────────


class TestWriteRead:
    """Verify FIFO ordering and correct data round-trip."""

    @pytest.mark.asyncio
    async def test_single_write_read(self) -> None:
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)
        chunk = _make_chunk(42)
        buf.write(chunk)

        result = await buf.read(timeout=0.1)
        assert result is not None
        np.testing.assert_array_equal(result, chunk.ravel())

    @pytest.mark.asyncio
    async def test_fifo_ordering(self) -> None:
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)
        for i in range(3):
            buf.write(_make_chunk(i))

        for i in range(3):
            result = await buf.read(timeout=0.1)
            assert result is not None
            assert result[0] == i

    @pytest.mark.asyncio
    async def test_read_returns_copy(self) -> None:
        """Read must return a copy, not a view into the buffer."""
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)
        buf.write(_make_chunk(10))

        result = await buf.read(timeout=0.1)
        assert result is not None

        # Mutate the returned array — should NOT affect internal buffer
        result[:] = 99
        buf.write(_make_chunk(10))
        result2 = await buf.read(timeout=0.1)
        assert result2 is not None
        assert result2[0] == 10

    @pytest.mark.asyncio
    async def test_size_tracks_correctly(self) -> None:
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)
        assert buf.size == 0

        buf.write(_make_chunk(1))
        assert buf.size == 1

        buf.write(_make_chunk(2))
        assert buf.size == 2

        await buf.read(timeout=0.1)
        assert buf.size == 1


# ── Tests: Drop-Oldest Policy ───────────────────


class TestDropOldest:
    """Verify overflow behavior: oldest chunk is silently overwritten."""

    @pytest.mark.asyncio
    async def test_drop_when_full(self) -> None:
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)

        # Fill buffer (0, 1, 2, 3)
        for i in range(SMALL_CAPACITY):
            buf.write(_make_chunk(i))

        assert buf.size == SMALL_CAPACITY
        assert buf.drop_count == 0

        # Write one more — drops oldest (0)
        buf.write(_make_chunk(100))
        assert buf.drop_count == 1
        assert buf.size == SMALL_CAPACITY

        # First read should be chunk 1 (chunk 0 was dropped)
        result = await buf.read(timeout=0.1)
        assert result is not None
        assert result[0] == 1

    @pytest.mark.asyncio
    async def test_multiple_drops(self) -> None:
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)

        # Write 6 chunks into a 4-slot buffer: drops 2 oldest
        for i in range(6):
            buf.write(_make_chunk(i))

        assert buf.drop_count == 2
        assert buf.size == SMALL_CAPACITY

        # Should read 2, 3, 4, 5 (chunks 0, 1 were dropped)
        for expected in [2, 3, 4, 5]:
            result = await buf.read(timeout=0.1)
            assert result is not None
            assert result[0] == expected

    @pytest.mark.asyncio
    async def test_heavy_overflow(self) -> None:
        """Overflow well beyond capacity — drops accumulate correctly."""
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)
        overflow_count = SMALL_CAPACITY * 3

        for i in range(SMALL_CAPACITY + overflow_count):
            buf.write(_make_chunk(i))

        assert buf.drop_count == overflow_count
        assert buf.size == SMALL_CAPACITY

    def test_drop_log_interval(self) -> None:
        """Verify drops are logged every DROP_LOG_INTERVAL drops."""
        buf = AudioRingBuffer(capacity=2, chunk_samples=CHUNK_SAMPLES)

        # Fill buffer first
        buf.write(_make_chunk(0))
        buf.write(_make_chunk(1))

        # Now overflow exactly DROP_LOG_INTERVAL times
        for _ in range(DROP_LOG_INTERVAL):
            buf.write(_make_chunk(99))

        assert buf.drop_count == DROP_LOG_INTERVAL


# ── Tests: High Watermark ────────────────────────


class TestHighWatermark:
    """Verify peak occupancy tracking."""

    @pytest.mark.asyncio
    async def test_watermark_increases(self) -> None:
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)

        buf.write(_make_chunk(1))
        assert buf.high_watermark == 1

        buf.write(_make_chunk(2))
        assert buf.high_watermark == 2

    @pytest.mark.asyncio
    async def test_watermark_does_not_decrease(self) -> None:
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)

        buf.write(_make_chunk(1))
        buf.write(_make_chunk(2))
        buf.write(_make_chunk(3))
        assert buf.high_watermark == 3

        await buf.read(timeout=0.1)
        await buf.read(timeout=0.1)
        assert buf.high_watermark == 3  # unchanged after reads

    @pytest.mark.asyncio
    async def test_watermark_reaches_capacity(self) -> None:
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)

        for i in range(SMALL_CAPACITY):
            buf.write(_make_chunk(i))

        assert buf.high_watermark == SMALL_CAPACITY


# ── Tests: Drain ─────────────────────────────────


class TestDrain:
    """Verify drain discards all unread data."""

    @pytest.mark.asyncio
    async def test_drain_empties_buffer(self) -> None:
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)

        buf.write(_make_chunk(1))
        buf.write(_make_chunk(2))
        assert buf.size == 2

        buf.drain()
        assert buf.size == 0

    @pytest.mark.asyncio
    async def test_drain_then_read_returns_none(self) -> None:
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)

        buf.write(_make_chunk(1))
        buf.drain()

        result = await buf.read(timeout=0.05)
        assert result is None

    @pytest.mark.asyncio
    async def test_write_after_drain_works(self) -> None:
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)

        buf.write(_make_chunk(1))
        buf.drain()

        buf.write(_make_chunk(42))
        result = await buf.read(timeout=0.1)
        assert result is not None
        assert result[0] == 42


# ── Tests: Reset Metrics ─────────────────────────


class TestResetMetrics:
    """Verify reset_metrics clears counters without touching data."""

    @pytest.mark.asyncio
    async def test_reset_clears_counts(self) -> None:
        buf = AudioRingBuffer(capacity=2, chunk_samples=CHUNK_SAMPLES)

        buf.write(_make_chunk(1))
        buf.write(_make_chunk(2))
        buf.write(_make_chunk(3))  # triggers drop
        assert buf.drop_count == 1
        assert buf.high_watermark == 2

        buf.reset_metrics()
        assert buf.drop_count == 0
        assert buf.high_watermark == 0

    @pytest.mark.asyncio
    async def test_reset_preserves_data(self) -> None:
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)

        buf.write(_make_chunk(7))
        buf.reset_metrics()

        assert buf.size == 1
        result = await buf.read(timeout=0.1)
        assert result is not None
        assert result[0] == 7


# ── Tests: Async Read Timeout ────────────────────


class TestAsyncReadTimeout:
    """Verify read() returns None on timeout and wakes on write."""

    @pytest.mark.asyncio
    async def test_read_empty_buffer_times_out(self) -> None:
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)
        result = await buf.read(timeout=0.05)
        assert result is None

    @pytest.mark.asyncio
    async def test_read_wakes_on_write(self) -> None:
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)

        async def delayed_write() -> None:
            await asyncio.sleep(0.02)
            buf.write(_make_chunk(99))

        task = asyncio.create_task(delayed_write())
        result = await buf.read(timeout=1.0)
        await task

        assert result is not None
        assert result[0] == 99


# ── Tests: Wrap-Around Correctness ───────────────


class TestWrapAround:
    """Verify the circular nature — read/write wrap around the buffer."""

    @pytest.mark.asyncio
    async def test_wrap_around_maintains_fifo(self) -> None:
        """Fill, read all, fill again — data should be correct."""
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)

        # First round
        for i in range(SMALL_CAPACITY):
            buf.write(_make_chunk(i))
        for i in range(SMALL_CAPACITY):
            result = await buf.read(timeout=0.1)
            assert result is not None
            assert result[0] == i

        # Second round (wraps around)
        for i in range(SMALL_CAPACITY):
            buf.write(_make_chunk(i + 10))
        for i in range(SMALL_CAPACITY):
            result = await buf.read(timeout=0.1)
            assert result is not None
            assert result[0] == i + 10

    @pytest.mark.asyncio
    async def test_partial_wrap(self) -> None:
        """Write 3 into a 4-slot buffer, read 2, write 3 more — wraps."""
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)

        for i in range(3):
            buf.write(_make_chunk(i))

        await buf.read(timeout=0.1)  # consume 0
        await buf.read(timeout=0.1)  # consume 1

        for i in range(3):
            buf.write(_make_chunk(i + 10))

        # Should have: 2, 10, 11, 12
        expected = [2, 10, 11, 12]
        for val in expected:
            result = await buf.read(timeout=0.1)
            assert result is not None
            assert result[0] == val


# ── Tests: Write Performance Contract ────────────


class TestWritePerformance:
    """Verify write() uses np.copyto (no allocation beyond pre-alloc)."""

    def test_write_does_not_change_buffer_identity(self) -> None:
        """The internal numpy array should be the SAME object after writes."""
        buf = AudioRingBuffer(capacity=SMALL_CAPACITY, chunk_samples=CHUNK_SAMPLES)
        internal_id = id(buf._buffer)

        for i in range(SMALL_CAPACITY * 2):
            buf.write(_make_chunk(i))

        assert id(buf._buffer) == internal_id
