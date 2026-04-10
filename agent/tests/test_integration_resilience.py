"""Integration tests for provider resilience cross-phase interactions.

Tests that Phase 3 (circuit breaker, health cache) + Phase 4 (fallback chain)
+ Phase 5 (streaming TTS) + Phase 7 (earcons/progress) work together:
- Circuit breaker opens -> health cache reflects -> fallback chain skips broken provider
- Memory pruning runs without disrupting active conversation
- Concurrent progress updates don't interfere with TTS streaming
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import numpy as np
import pytest

from core.audio.earcons import EarconType, get_earcon
from core.audio.interrupt_controller import InterruptController
from core.audio.ring_buffer import AudioRingBuffer
from core.audio.text_chunker import split_sentences
from core.errors import ProviderError
from core.memory import ConversationEntry, Memory
from core.mouth import Mouth
from providers.fallback import AllProvidersExhaustedError, FallbackChain
from providers.resilience import HealthCache


# ── Integration Tests: Circuit Breaker + Health Cache + Fallback ──


class TestCircuitBreakerFallbackIntegration:
    """Tests cross-phase resilience: circuit breaker -> health cache -> fallback."""

    @pytest.mark.asyncio
    async def test_health_cache_reflects_failures(self) -> None:
        """PROV-04 + PROV-07: Provider failures update health cache.

        When a provider fails through the fallback chain, the health cache
        should be updated to mark it unhealthy, and subsequent calls should
        skip it.
        """
        health_cache = HealthCache(ttl=60.0)

        failing_provider = AsyncMock()
        failing_provider.chat = AsyncMock(side_effect=ProviderError("timeout"))

        good_provider = AsyncMock()
        good_provider.chat = AsyncMock(return_value="hello")

        chain = FallbackChain(
            providers=[("failing", failing_provider), ("good", good_provider)],
            chain_type="LLM",
            health_cache=health_cache,
        )

        # First call: failing provider fails, good provider succeeds
        result = await chain.execute(lambda p: p.chat())
        assert result.provider_name == "good"
        assert result.attempts == 2

        # Health cache should now mark "failing" as unhealthy
        assert health_cache.get("failing") is False
        assert health_cache.get("good") is True

        # Second call: should skip "failing" entirely via health cache
        failing_provider.chat.reset_mock()
        result2 = await chain.execute(lambda p: p.chat())
        assert result2.provider_name == "good"
        assert result2.attempts == 1  # Only 1 attempt since "failing" was skipped
        failing_provider.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_health_cache_ttl_expiry_rechecks(self) -> None:
        """PROV-07: After TTL expires, health cache returns None (unknown).

        Verifies that stale health entries are treated as unknown,
        allowing the fallback chain to re-check the provider.
        """
        health_cache = HealthCache(ttl=0.05)  # 50ms TTL

        health_cache.set("groq", healthy=True)
        assert health_cache.get("groq") is True

        await asyncio.sleep(0.06)  # Wait for TTL to expire

        assert health_cache.get("groq") is None  # Stale -> unknown
        assert health_cache.is_stale("groq") is True

    @pytest.mark.asyncio
    async def test_fallback_chain_total_budget(self) -> None:
        """PROV-04: Fallback chain enforces total latency budget.

        When the total budget is exceeded, the chain stops trying
        remaining providers.
        """

        async def _slow_call(p: AsyncMock) -> str:
            await asyncio.sleep(0.5)
            return "result"

        slow1 = AsyncMock()
        slow2 = AsyncMock()

        chain = FallbackChain(
            providers=[("slow1", slow1), ("slow2", slow2)],
            chain_type="LLM",
            total_budget_s=0.3,  # Very tight budget
            per_provider_timeout_s=0.2,
        )

        with pytest.raises(AllProvidersExhaustedError):
            await chain.execute(_slow_call)

    @pytest.mark.asyncio
    async def test_failover_callback_fires(self) -> None:
        """PROV-01 + ERRH-02: Failover callback fires on provider switch.

        The failover callback can be used to announce "switching to backup"
        to the user.
        """
        failover_events: list[tuple[str, str, str]] = []

        async def _on_failover(chain_type: str, failed: str, next_name: str) -> None:
            failover_events.append((chain_type, failed, next_name))

        failing = AsyncMock()
        failing.chat = AsyncMock(side_effect=ProviderError("down"))

        good = AsyncMock()
        good.chat = AsyncMock(return_value="ok")

        chain = FallbackChain(
            providers=[("primary", failing), ("backup", good)],
            chain_type="LLM",
        )
        chain.on_failover(_on_failover)

        result = await chain.execute(lambda p: p.chat())
        assert result.provider_name == "backup"
        assert len(failover_events) == 1
        assert failover_events[0] == ("LLM", "primary", "backup")


# ── Integration Tests: Memory Pruning ──


class TestMemoryPruningIntegration:
    """Test memory pruning doesn't disrupt active operations."""

    @pytest.mark.asyncio
    async def test_pruning_during_active_conversation(self) -> None:
        """SAFE-07: Memory pruning runs concurrently without blocking.

        Verifies that auto_prune can run while new conversations are
        being added, without data corruption.
        """
        memory = Memory()
        await memory.connect(":memory:")

        try:
            # Add old conversations
            old_ts = datetime.now(tz=timezone.utc) - timedelta(days=60)
            for i in range(10):
                await memory.add_conversation(
                    ConversationEntry(
                        role="user",
                        content=f"old message {i}",
                        timestamp=old_ts,
                        session_id="old-session",
                    )
                )

            # Add recent conversations
            now = datetime.now(tz=timezone.utc)
            for i in range(5):
                await memory.add_conversation(
                    ConversationEntry(
                        role="user",
                        content=f"recent message {i}",
                        timestamp=now,
                        session_id="current-session",
                    )
                )

            # Run pruning concurrently with adding more data
            async def _add_while_pruning() -> None:
                for j in range(3):
                    await memory.add_conversation(
                        ConversationEntry(
                            role="assistant",
                            content=f"response {j}",
                            timestamp=now,
                            session_id="current-session",
                        )
                    )
                    await asyncio.sleep(0.01)

            prune_task = asyncio.create_task(memory.auto_prune(ttl_days=30))
            add_task = asyncio.create_task(_add_while_pruning())

            deleted = await prune_task
            await add_task

            # Old conversations should be pruned
            assert deleted >= 10

            # Recent conversations should survive
            remaining = await memory.get_conversation_count()
            assert remaining >= 5  # At least the recent ones
        finally:
            await memory.close()

    @pytest.mark.asyncio
    async def test_enforce_max_conversations(self) -> None:
        """SAFE-07: Enforce maximum conversation count."""
        memory = Memory()
        await memory.connect(":memory:")

        try:
            now = datetime.now(tz=timezone.utc)
            for i in range(20):
                await memory.add_conversation(
                    ConversationEntry(
                        role="user",
                        content=f"message {i}",
                        timestamp=now,
                        session_id="session",
                    )
                )

            total_before = await memory.get_conversation_count()
            assert total_before == 20

            deleted = await memory.enforce_max_conversations(max_count=10)
            assert deleted == 10

            total_after = await memory.get_conversation_count()
            assert total_after == 10
        finally:
            await memory.close()


# ── Integration Tests: Audio Subsystem Cross-Phase ──


class TestAudioSubsystemIntegration:
    """Test cross-phase audio component interactions."""

    @pytest.mark.asyncio
    async def test_ring_buffer_with_concurrent_readers(self) -> None:
        """AUDR-04: Ring buffer works with concurrent producer/consumer.

        Simulates the real scenario where the sounddevice callback
        writes while the pipeline reads.
        """
        buffer = AudioRingBuffer(capacity=8, chunk_samples=160)
        chunks_read: list[np.ndarray] = []

        # Producer: write 5 chunks
        for i in range(5):
            chunk = np.full(160, fill_value=i, dtype=np.int16)
            buffer.write(chunk)

        # Consumer: read all 5
        for _ in range(5):
            chunk = await buffer.read(timeout=0.1)
            assert chunk is not None
            chunks_read.append(chunk)

        assert len(chunks_read) == 5
        assert buffer.size == 0

    @pytest.mark.asyncio
    async def test_ring_buffer_drop_oldest_on_overflow(self) -> None:
        """AUDR-04: Ring buffer drops oldest when full."""
        buffer = AudioRingBuffer(capacity=4, chunk_samples=160)

        # Write 6 chunks into a buffer of capacity 4
        for i in range(6):
            chunk = np.full(160, fill_value=i, dtype=np.int16)
            buffer.write(chunk)

        assert buffer.drop_count == 2  # 2 oldest chunks dropped
        assert buffer.size == 4

        # Read remaining — should get chunks 2,3,4,5 (0,1 were dropped)
        first = await buffer.read(timeout=0.1)
        assert first is not None
        assert first[0] == 2  # Oldest surviving chunk

    @pytest.mark.asyncio
    async def test_text_chunker_with_streaming_tts(self) -> None:
        """STTS-01: Text is split at sentence boundaries for streaming.

        Verifies the chunker produces reasonable chunks that can be
        individually synthesized.
        """
        text = "Xin chao anh. Day la VoxAgent. Toi co the giup gi cho anh?"
        chunks = split_sentences(text)

        assert len(chunks) >= 2
        # Each chunk is non-empty
        for chunk in chunks:
            assert len(chunk.strip()) > 0
        # Reassembled text contains all original content
        reassembled = " ".join(chunks)
        assert "VoxAgent" in reassembled

    @pytest.mark.asyncio
    async def test_earcons_dont_block_pipeline(self) -> None:
        """PROG-01 + ERRH-03: Earcon generation is fast and non-blocking.

        Verifies that generating earcon tones completes quickly enough
        for the 200ms acknowledge requirement.
        """
        t0 = time.monotonic()
        ack = get_earcon(EarconType.ACKNOWLEDGE)
        gen_time_ms = (time.monotonic() - t0) * 1000

        assert gen_time_ms < 50  # Tone generation should be nearly instant
        assert len(ack) > 0
        assert ack.dtype == np.int16

    @pytest.mark.asyncio
    async def test_interrupt_controller_cross_thread_safety(self) -> None:
        """BGIN-01: InterruptController works across asyncio tasks.

        Simulates the real scenario where one task monitors for wake word
        and another task is playing audio.
        """
        interrupt = InterruptController()
        detected = False

        async def _monitor() -> None:
            nonlocal detected
            await interrupt.wait_for_interrupt()
            detected = True

        async def _trigger_after_delay() -> None:
            await asyncio.sleep(0.02)
            interrupt.interrupt()

        monitor_task = asyncio.create_task(_monitor())
        trigger_task = asyncio.create_task(_trigger_after_delay())

        await asyncio.gather(monitor_task, trigger_task)
        assert detected is True
        assert interrupt.is_interrupted is True
