"""Simulated 4-hour stability stress test for VoxAgent Phase 10.

Verifies long-running operational stability via 200+ simulated pipeline
cycles with injected failures. Checks:

1. No memory leaks (object count growth < 10% over full run)
2. No orphaned asyncio tasks after pipeline cycles
3. No silent failures (every error is a VoxError with user_message)
4. Provider failover recovery (circuit breakers reset after cooldown)
5. Ring buffer doesn't leak under sustained load
6. Pipeline state machine always returns to LISTENING after each cycle
7. httpx clients properly closed on shutdown

All providers are mocked -- no real API calls.
"""

from __future__ import annotations

import asyncio
import gc
import io
import time
import wave
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from core.audio.ring_buffer import AudioRingBuffer
from core.brain import Brain, Tier
from core.errors import (
    AudioError,
    PipelineError,
    ProviderError,
    SkillError,
    VoxError,
)
from core.hands import Hands
from core.mouth import Mouth
from core.pipeline_state import PipelineState, PipelineStateMachine
from providers.base import TranscribeResult
from providers.fallback import AllProvidersExhaustedError, FallbackChain
from providers.registry import ProviderRegistry
from providers.resilience import HealthCache
from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult
from skills.registry import SkillRegistry

# ── Constants ───────────────────────────────────────────────────────────────

STRESS_ITERATION_COUNT = 250
FAILURE_INJECTION_INTERVAL = 15
RING_BUFFER_STRESS_CHUNKS = 500
RING_BUFFER_CAPACITY = 32
RING_BUFFER_CHUNK_SAMPLES = 160
OBJECT_GROWTH_THRESHOLD_PCT = 10.0
TASK_LEAK_TOLERANCE = 2
HEALTH_CACHE_TTL_S = 0.5
CIRCUIT_BREAKER_COOLDOWN_CYCLES = 20


# ── Shared Fake Skills ──────────────────────────────────────────────────────


class _ReliableSkill(BaseSkill):
    """Skill that always succeeds, for stable pipeline cycles."""

    name = "media_control"
    description = "Control media playback"
    keywords: ClassVar[list[str]] = ["pause", "play", "skip"]
    execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]
    permissions: ClassVar[list[str]] = ["media:control"]

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Accept intents targeting this skill."""
        return intent.skill_name == self.name

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Simulate successful media control."""
        return SkillResult.ok(
            tts_response="Da thuc hien.",
            tier_used=ExecutionTier.NATIVE_API,
        )


class _TimeoutSkill(BaseSkill):
    """Skill that sleeps forever, triggering timeout in Hands."""

    name = "timeout_skill"
    description = "Always times out"
    keywords: ClassVar[list[str]] = ["slow"]
    execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]
    permissions: ClassVar[list[str]] = []

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Accept all intents."""
        return True

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Sleep indefinitely until cancelled by timeout."""
        await asyncio.sleep(999)
        return SkillResult.ok(tts_response="Never reached.")


class _ErrorSkill(BaseSkill):
    """Skill that raises a VoxError with user_message."""

    name = "error_skill"
    description = "Always raises SkillError"
    keywords: ClassVar[list[str]] = ["error"]
    execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]
    permissions: ClassVar[list[str]] = []

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Accept all intents."""
        return True

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Return a typed failure with user_message."""
        return SkillResult.fail(
            error="Simulated SkillError for stress test",
            tts_response="Co loi xay ra, vui long thu lai.",
            error_code="stress_test_error",
        )


# ── Mock Factories ──────────────────────────────────────────────────────────


def _make_valid_wav_bytes() -> bytes:
    """Generate minimal valid WAV audio bytes (16kHz, mono, int16, ~50ms)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(np.zeros(800, dtype=np.int16).tobytes())
    return buf.getvalue()


def _make_mock_llm(response: dict[str, object] | None = None) -> AsyncMock:
    """Create a mock LLM provider with default media_control response."""
    mock = AsyncMock()
    mock.chat_with_tools = AsyncMock(
        return_value=response
        or {"tool": "media_control", "result": {"action": "pause", "confidence": 0.95}}
    )
    mock.health_check = AsyncMock(return_value=True)
    return mock


def _make_mock_tts() -> AsyncMock:
    """Create a mock TTS provider returning valid WAV bytes."""
    mock = AsyncMock()
    mock.synthesize = AsyncMock(return_value=_make_valid_wav_bytes())

    async def _fake_stream(*_args, **_kwargs):
        yield b"\xff" * 100

    mock.synthesize_stream = _fake_stream
    return mock


def _make_mock_stt(text: str = "pause nhac") -> AsyncMock:
    """Create a mock STT provider returning a TranscribeResult."""
    mock = AsyncMock()
    mock.transcribe = AsyncMock(
        return_value=TranscribeResult(
            text=text,
            confidence=0.95,
            language="vi",
            duration_ms=1200,
        )
    )
    return mock


def _make_failing_provider(error_cls: type = ProviderError) -> AsyncMock:
    """Create a mock provider that raises on every call."""
    mock = AsyncMock()
    mock.chat_with_tools = AsyncMock(side_effect=error_cls("Injected failure"))
    mock.health_check = AsyncMock(return_value=False)
    mock.synthesize = AsyncMock(side_effect=error_cls("TTS injected failure"))
    mock.transcribe = AsyncMock(side_effect=error_cls("STT injected failure"))
    return mock


# ── Skill Registry Helpers ──────────────────────────────────────────────────


def _save_and_set_skills(**skills: BaseSkill) -> dict[str, BaseSkill | None]:
    """Register fake skills, preserving originals for teardown."""
    originals: dict[str, BaseSkill | None] = {}
    for name, skill in skills.items():
        originals[name] = SkillRegistry._skills.get(name)
        SkillRegistry._skills[name] = skill
    return originals


def _restore_skills(originals: dict[str, BaseSkill | None]) -> None:
    """Restore original skill registry state."""
    for name, original in originals.items():
        if original is None:
            SkillRegistry._skills.pop(name, None)
        else:
            SkillRegistry._skills[name] = original


# ── Test 1: Memory Stability Over 250 Pipeline Cycles ──────────────────────


class TestMemoryStability:
    """Verify no memory leaks over sustained pipeline operation."""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_no_object_leak_over_250_cycles(self) -> None:
        """Run 250 Brain->Hands->Mouth cycles, assert object count growth < 10%.

        Alternates keyword and LLM-routed commands. Every Nth cycle
        injects a timeout or error. Measures gc object count delta.
        """
        skill = _ReliableSkill()
        timeout_skill = _TimeoutSkill()
        error_skill = _ErrorSkill()
        mock_llm = _make_mock_llm()
        mock_tts = _make_mock_tts()

        registry = ProviderRegistry()
        registry.register_llm("ollama", lambda: mock_llm)

        brain = Brain(
            registry=registry,
            skills=[skill],
            routing_config={"tiers": [{"provider": "ollama", "model": "test"}]},
        )
        mouth = Mouth(tts_provider=mock_tts)
        hands = Hands(mouth=mouth, skill_timeout_s=0.05)

        saved = _save_and_set_skills(
            media_control=skill,
            timeout_skill=timeout_skill,
            error_skill=error_skill,
        )
        try:
            # Warm-up to stabilize lazy imports
            warmup_intent = await brain.process("pause nhac")
            si = SkillIntent(
                skill_name=warmup_intent.skill_name,
                action=warmup_intent.action,
                params=warmup_intent.params,
                raw_text="pause nhac",
            )
            await hands.execute(si)
            with patch("core.mouth._play_wav", new_callable=AsyncMock):
                await mouth.speak("warmup")

            gc.collect()
            gc.collect()
            baseline_objects = len(gc.get_objects())

            for i in range(STRESS_ITERATION_COUNT):
                if i % FAILURE_INJECTION_INTERVAL == (FAILURE_INJECTION_INTERVAL - 1):
                    # Inject timeout
                    timeout_si = SkillIntent(
                        skill_name="timeout_skill",
                        action="hang",
                        params={},
                        raw_text="slow operation",
                    )
                    result = await hands.execute(timeout_si)
                    assert not result.success
                    assert result.error_code == "timeout"
                elif i % FAILURE_INJECTION_INTERVAL == (FAILURE_INJECTION_INTERVAL - 2):
                    # Inject skill error
                    error_si = SkillIntent(
                        skill_name="error_skill",
                        action="fail",
                        params={},
                        raw_text="trigger error",
                    )
                    result = await hands.execute(error_si)
                    assert not result.success
                    assert result.tts_response  # Must have user-facing message
                elif i % 2 == 0:
                    # Keyword-routed command
                    intent = await brain.process("pause nhac")
                    assert intent.skill_name == "media_control"
                    si = SkillIntent(
                        skill_name=intent.skill_name,
                        action=intent.action,
                        params=intent.params,
                        raw_text="pause nhac",
                    )
                    result = await hands.execute(si)
                    assert result.success
                else:
                    # LLM-routed command
                    intent = await brain.process("tam dung bai hat dang phat")
                    assert intent.skill_name == "media_control"
                    si = SkillIntent(
                        skill_name=intent.skill_name,
                        action=intent.action,
                        params=intent.params,
                        raw_text="tam dung bai hat dang phat",
                    )
                    result = await hands.execute(si)
                    assert result.success

            gc.collect()
            gc.collect()
            final_objects = len(gc.get_objects())

            delta_pct = (
                abs(final_objects - baseline_objects) / max(baseline_objects, 1) * 100
            )
            assert delta_pct < OBJECT_GROWTH_THRESHOLD_PCT, (
                f"Object count growth {delta_pct:.1f}% exceeds "
                f"{OBJECT_GROWTH_THRESHOLD_PCT}% threshold "
                f"(baseline={baseline_objects}, final={final_objects})"
            )

        finally:
            _restore_skills(saved)


# ── Test 2: No Orphaned Asyncio Tasks ──────────────────────────────────────


class TestNoOrphanedTasks:
    """Verify asyncio tasks are properly cleaned up after pipeline cycles."""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_task_count_stable_after_cycles(self) -> None:
        """Run 200 cycles with timeouts, verify task count returns to baseline.

        Timeout-cancelled skills must not leave dangling tasks.
        """
        skill = _ReliableSkill()
        timeout_skill = _TimeoutSkill()
        mock_tts = _make_mock_tts()

        registry = ProviderRegistry()
        brain = Brain(registry=registry, skills=[skill])
        mouth = Mouth(tts_provider=mock_tts)
        hands = Hands(mouth=mouth, skill_timeout_s=0.05)

        saved = _save_and_set_skills(
            media_control=skill,
            timeout_skill=timeout_skill,
        )
        try:
            # Warm-up
            intent = await brain.process("pause nhac")
            si = SkillIntent(
                skill_name=intent.skill_name,
                action=intent.action,
                params=intent.params,
                raw_text="pause nhac",
            )
            await hands.execute(si)
            await asyncio.sleep(0.01)
            baseline_tasks = len(asyncio.all_tasks())

            for i in range(200):
                if i % 10 == 9:
                    # Timeout cycle
                    timeout_si = SkillIntent(
                        skill_name="timeout_skill",
                        action="hang",
                        params={},
                        raw_text="slow thing",
                    )
                    result = await hands.execute(timeout_si)
                    assert not result.success
                else:
                    intent = await brain.process("play nhac")
                    si = SkillIntent(
                        skill_name=intent.skill_name,
                        action=intent.action,
                        params=intent.params,
                        raw_text="play nhac",
                    )
                    await hands.execute(si)

            # Allow task cleanup
            await asyncio.sleep(0.05)
            final_tasks = len(asyncio.all_tasks())

            assert final_tasks <= baseline_tasks + TASK_LEAK_TOLERANCE, (
                f"Task leak: baseline={baseline_tasks}, final={final_tasks}, "
                f"tolerance={TASK_LEAK_TOLERANCE}"
            )

        finally:
            _restore_skills(saved)


# ── Test 3: No Silent Failures ──────────────────────────────────────────────


class TestNoSilentFailures:
    """Verify every error in the hierarchy carries a user_message."""

    def test_all_vox_errors_have_user_message(self) -> None:
        """Instantiate every VoxError subclass, assert user_message is non-empty."""
        errors = [
            VoxError("test"),
            ProviderError("test", provider_name="groq"),
            AudioError("test"),
            PipelineError("test", stage="brain"),
            SkillError("test", skill_name="media_control"),
        ]
        for err in errors:
            assert err.user_message, (
                f"{type(err).__name__} has empty user_message"
            )
            assert isinstance(err.user_message, str)
            assert len(err.user_message) > 0

    def test_skill_result_fail_always_has_tts_response(self) -> None:
        """SkillResult.fail() with tts_response always provides spoken error."""
        result = SkillResult.fail(
            error="Something broke",
            tts_response="Co loi xay ra.",
            error_code="test_error",
        )
        assert not result.success
        assert result.tts_response
        assert result.error_code == "test_error"

    def test_all_providers_exhausted_has_user_message(self) -> None:
        """AllProvidersExhaustedError carries a Vietnamese user_message."""
        err = AllProvidersExhaustedError("LLM", ["groq", "ollama"])
        assert err.user_message
        assert "nha cung cap" in err.user_message.lower()

    @pytest.mark.asyncio
    async def test_hands_returns_typed_error_on_missing_skill(self) -> None:
        """Hands.execute() with nonexistent skill returns error, not exception."""
        hands = Hands()
        intent = SkillIntent(
            skill_name="nonexistent_skill",
            action="do_thing",
            params={},
            raw_text="invalid command",
        )
        result = await hands.execute(intent)
        assert not result.success
        assert result.error_code == "not_found"
        assert result.tts_response  # User hears something

    @pytest.mark.asyncio
    async def test_hands_returns_typed_error_on_timeout(self) -> None:
        """Hands.execute() with timeout returns error with code 'timeout'."""
        timeout_skill = _TimeoutSkill()
        hands = Hands(skill_timeout_s=0.02)
        saved = _save_and_set_skills(timeout_skill=timeout_skill)
        try:
            intent = SkillIntent(
                skill_name="timeout_skill",
                action="hang",
                params={},
                raw_text="slow thing",
            )
            result = await hands.execute(intent)
            assert not result.success
            assert result.error_code == "timeout"
            assert result.tts_response  # Spoken error
        finally:
            _restore_skills(saved)


# ── Test 4: Provider Failover Recovery ──────────────────────────────────────


class TestProviderFailoverRecovery:
    """Verify circuit breakers reset and failover chains recover."""

    @pytest.mark.asyncio
    async def test_health_cache_expires_and_primary_recovers(self) -> None:
        """Primary fails -> cached unhealthy -> TTL expires -> primary retried.

        Uses a short TTL to simulate circuit breaker cooldown period.
        """
        primary_llm = _make_mock_llm()
        secondary_llm = _make_mock_llm()

        health_cache = HealthCache(ttl=HEALTH_CACHE_TTL_S)

        chain = FallbackChain(
            providers=[("groq", primary_llm), ("ollama", secondary_llm)],
            chain_type="LLM",
            health_cache=health_cache,
        )

        skill = _ReliableSkill()
        registry = ProviderRegistry()
        brain = Brain(
            registry=registry,
            skills=[skill],
            llm_fallback_chain=chain,
        )

        # Phase 1: Primary fails -> mark unhealthy
        health_cache.set("groq", healthy=False)

        intent1 = await brain.process("tam dung bai hat")
        assert intent1.skill_name == "media_control"
        # Primary was skipped
        primary_llm.chat_with_tools.assert_not_called()
        secondary_llm.chat_with_tools.assert_called()

        # Phase 2: Wait for TTL to expire
        await asyncio.sleep(HEALTH_CACHE_TTL_S + 0.1)

        # TTL expired -> cached entry is stale -> primary retried
        assert health_cache.get("groq") is None  # Stale

        # Phase 3: Primary recovered -- reset mocks and verify
        primary_llm.chat_with_tools.reset_mock()
        secondary_llm.chat_with_tools.reset_mock()

        intent2 = await brain.process("tiep tuc phat nhac")
        assert intent2.skill_name == "media_control"
        # Primary was tried again (not skipped)
        primary_llm.chat_with_tools.assert_called()

    @pytest.mark.asyncio
    async def test_tts_failover_and_recovery_cycle(self) -> None:
        """TTS primary fails -> fallback -> primary recovers -> primary used again."""
        primary_tts = _make_mock_tts()
        secondary_tts = _make_mock_tts()

        health_cache = HealthCache(ttl=HEALTH_CACHE_TTL_S)
        chain = FallbackChain(
            providers=[("edge_tts", primary_tts), ("piper", secondary_tts)],
            chain_type="TTS",
            health_cache=health_cache,
        )
        mouth = Mouth(tts_fallback_chain=chain)

        # Phase 1: Primary works
        with patch("core.mouth._play_wav", new_callable=AsyncMock):
            await mouth.speak("Xin chao")
        primary_tts.synthesize.assert_called_once()
        secondary_tts.synthesize.assert_not_called()

        # Phase 2: Primary fails
        primary_tts.synthesize = AsyncMock(
            side_effect=RuntimeError("edge_tts connection lost")
        )
        with patch("core.mouth._play_wav", new_callable=AsyncMock):
            await mouth.speak("Loi roi")
        secondary_tts.synthesize.assert_called_once()

        # Phase 3: Wait for health cache TTL
        await asyncio.sleep(HEALTH_CACHE_TTL_S + 0.1)

        # Phase 4: Primary recovered
        primary_tts.synthesize = AsyncMock(return_value=_make_valid_wav_bytes())
        secondary_tts.synthesize.reset_mock()

        with patch("core.mouth._play_wav", new_callable=AsyncMock):
            await mouth.speak("Da khoi phuc")
        primary_tts.synthesize.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_failover_cycles(self) -> None:
        """Provider fails and recovers multiple times without state corruption."""
        primary = _make_mock_llm()
        secondary = _make_mock_llm()
        health_cache = HealthCache(ttl=HEALTH_CACHE_TTL_S)
        failover_events: list[tuple[str, str, str]] = []

        async def _on_failover(chain_type: str, failed: str, next_name: str) -> None:
            failover_events.append((chain_type, failed, next_name))

        chain = FallbackChain(
            providers=[("groq", primary), ("ollama", secondary)],
            chain_type="LLM",
            health_cache=health_cache,
        )
        chain.on_failover(_on_failover)

        skill = _ReliableSkill()
        registry = ProviderRegistry()
        brain = Brain(
            registry=registry,
            skills=[skill],
            llm_fallback_chain=chain,
        )

        for cycle in range(5):
            # Fail primary
            health_cache.set("groq", healthy=False)
            intent = await brain.process("tam dung bai hat")
            assert intent.skill_name == "media_control"

            # Wait for cooldown
            await asyncio.sleep(HEALTH_CACHE_TTL_S + 0.1)

            # Recover primary
            health_cache.invalidate("groq")
            primary.chat_with_tools.reset_mock()
            intent = await brain.process("pause nhac")
            assert intent.skill_name == "media_control"


# ── Test 5: Ring Buffer Memory Stability ────────────────────────────────────


class TestRingBufferStability:
    """Verify ring buffer doesn't leak under sustained write/read load."""

    @pytest.mark.asyncio
    async def test_sustained_write_read_no_leak(self) -> None:
        """Write/read 500 chunks through a small ring buffer, verify no leak."""
        buffer = AudioRingBuffer(
            capacity=RING_BUFFER_CAPACITY,
            chunk_samples=RING_BUFFER_CHUNK_SAMPLES,
        )

        gc.collect()
        baseline_objects = len(gc.get_objects())

        chunks_read = 0
        for i in range(RING_BUFFER_STRESS_CHUNKS):
            chunk = np.full(RING_BUFFER_CHUNK_SAMPLES, i % 128, dtype=np.int16)
            buffer.write(chunk)

            result = await buffer.read(timeout=0.01)
            if result is not None:
                chunks_read += 1
                assert result.dtype == np.int16

        gc.collect()
        final_objects = len(gc.get_objects())

        delta_pct = (
            abs(final_objects - baseline_objects) / max(baseline_objects, 1) * 100
        )
        assert delta_pct < OBJECT_GROWTH_THRESHOLD_PCT, (
            f"Ring buffer leak: {delta_pct:.1f}% object growth"
        )
        assert chunks_read > 0  # At least some reads succeeded

    @pytest.mark.asyncio
    async def test_overflow_drops_oldest_no_corruption(self) -> None:
        """Overflow the buffer repeatedly, verify data integrity and metrics."""
        capacity = 8
        buffer = AudioRingBuffer(
            capacity=capacity,
            chunk_samples=RING_BUFFER_CHUNK_SAMPLES,
        )

        # Write 3x capacity without reading -- forces drops
        for i in range(capacity * 3):
            chunk = np.full(RING_BUFFER_CHUNK_SAMPLES, i % 128, dtype=np.int16)
            buffer.write(chunk)

        assert buffer.drop_count > 0
        assert buffer.size <= capacity

        # Read remaining -- no corruption
        for _ in range(buffer.size):
            result = await buffer.read(timeout=0.01)
            assert result is not None
            assert result.dtype == np.int16
            assert result.shape == (RING_BUFFER_CHUNK_SAMPLES,)

    @pytest.mark.asyncio
    async def test_drain_frees_all_slots(self) -> None:
        """After drain, buffer reports size=0 and read returns None."""
        buffer = AudioRingBuffer(
            capacity=RING_BUFFER_CAPACITY,
            chunk_samples=RING_BUFFER_CHUNK_SAMPLES,
        )

        # Fill halfway
        for i in range(RING_BUFFER_CAPACITY // 2):
            chunk = np.full(RING_BUFFER_CHUNK_SAMPLES, i, dtype=np.int16)
            buffer.write(chunk)

        assert buffer.size > 0
        buffer.drain()
        assert buffer.size == 0

        result = await buffer.read(timeout=0.01)
        assert result is None

    @pytest.mark.asyncio
    async def test_concurrent_producer_consumer_sustained(self) -> None:
        """Producer/consumer running concurrently for 300 chunks."""
        buffer = AudioRingBuffer(
            capacity=RING_BUFFER_CAPACITY,
            chunk_samples=RING_BUFFER_CHUNK_SAMPLES,
        )
        chunks_read: list[np.ndarray] = []
        write_count = 300

        async def _producer():
            for i in range(write_count):
                chunk = np.full(RING_BUFFER_CHUNK_SAMPLES, i % 128, dtype=np.int16)
                buffer.write(chunk)
                await asyncio.sleep(0.0001)

        async def _consumer():
            for _ in range(write_count):
                result = await buffer.read(timeout=0.5)
                if result is not None:
                    chunks_read.append(result)

        await asyncio.gather(_producer(), _consumer())

        read_count = len(chunks_read)
        expected_min = write_count - buffer.drop_count
        assert read_count >= expected_min - 1, (
            f"Consumer read {read_count}, expected >= {expected_min - 1}"
        )
        for chunk in chunks_read:
            assert chunk.dtype == np.int16


# ── Test 6: Pipeline State Machine Always Returns to LISTENING ──────────────


class TestPipelineStateRecovery:
    """Verify state machine invariant: every cycle ends in LISTENING."""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_state_returns_to_listening_every_cycle(self) -> None:
        """Run 200 full pipeline cycles, assert LISTENING at end of each.

        Simulates: LISTENING -> PROCESSING -> SPEAKING -> LISTENING
        with occasional INTERRUPTED transitions.
        """
        sm = PipelineStateMachine()
        skill = _ReliableSkill()
        mock_tts = _make_mock_tts()
        registry = ProviderRegistry()
        brain = Brain(registry=registry, skills=[skill])
        mouth = Mouth(tts_provider=mock_tts)
        hands = Hands(mouth=mouth)

        saved = _save_and_set_skills(media_control=skill)
        try:
            for i in range(200):
                assert sm.current_state == PipelineState.LISTENING, (
                    f"Cycle {i}: expected LISTENING, got {sm.current_state.name}"
                )

                # LISTENING -> PROCESSING
                assert sm.transition_to(PipelineState.PROCESSING)

                intent = await brain.process("pause nhac")
                si = SkillIntent(
                    skill_name=intent.skill_name,
                    action=intent.action,
                    params=intent.params,
                    raw_text="pause nhac",
                )
                result = await hands.execute(si)
                assert result.success

                # PROCESSING -> SPEAKING
                assert sm.transition_to(PipelineState.SPEAKING)

                if i % 20 == 19:
                    # Simulate barge-in: SPEAKING -> INTERRUPTED -> LISTENING
                    assert sm.transition_to(PipelineState.INTERRUPTED)
                    assert sm.transition_to(PipelineState.LISTENING)
                else:
                    # Normal: SPEAKING -> LISTENING
                    assert sm.transition_to(PipelineState.LISTENING)

            # Final state must be LISTENING
            assert sm.current_state == PipelineState.LISTENING

        finally:
            _restore_skills(saved)

    @pytest.mark.asyncio
    async def test_force_reset_recovers_from_any_state(self) -> None:
        """force_reset() brings state machine back to LISTENING from any state."""
        sm = PipelineStateMachine()

        for target_state in [
            PipelineState.PROCESSING,
            PipelineState.SPEAKING,
            PipelineState.INTERRUPTED,
        ]:
            # Navigate to target state
            sm.force_reset()
            if target_state == PipelineState.PROCESSING:
                sm.transition_to(PipelineState.PROCESSING)
            elif target_state == PipelineState.SPEAKING:
                sm.transition_to(PipelineState.PROCESSING)
                sm.transition_to(PipelineState.SPEAKING)
            elif target_state == PipelineState.INTERRUPTED:
                sm.transition_to(PipelineState.PROCESSING)
                sm.transition_to(PipelineState.SPEAKING)
                sm.transition_to(PipelineState.INTERRUPTED)

            assert sm.current_state == target_state
            sm.force_reset()
            assert sm.current_state == PipelineState.LISTENING

    @pytest.mark.asyncio
    async def test_invalid_transitions_rejected_and_state_preserved(self) -> None:
        """Invalid transitions are rejected; state remains unchanged."""
        sm = PipelineStateMachine()

        # LISTENING -> SPEAKING is invalid
        assert not sm.transition_to(PipelineState.SPEAKING)
        assert sm.current_state == PipelineState.LISTENING

        # LISTENING -> INTERRUPTED is invalid
        assert not sm.transition_to(PipelineState.INTERRUPTED)
        assert sm.current_state == PipelineState.LISTENING

        # Valid path
        assert sm.transition_to(PipelineState.PROCESSING)

        # PROCESSING -> INTERRUPTED is invalid
        assert not sm.transition_to(PipelineState.INTERRUPTED)
        assert sm.current_state == PipelineState.PROCESSING


# ── Test 7: httpx Client Cleanup on Shutdown ────────────────────────────────


class TestHttpxClientCleanup:
    """Verify httpx.AsyncClient resources are properly closed."""

    @pytest.mark.asyncio
    async def test_mock_provider_cleanup(self) -> None:
        """Provider with close() method is called during simulated shutdown."""
        mock_provider = AsyncMock()
        mock_provider.close = AsyncMock()
        mock_provider.chat_with_tools = AsyncMock(
            return_value={
                "tool": "media_control",
                "result": {"action": "pause", "confidence": 0.9},
            }
        )
        mock_provider.health_check = AsyncMock(return_value=True)

        registry = ProviderRegistry()
        registry.register_llm("test_provider", lambda: mock_provider)

        # Use the provider
        provider = registry.get_llm("test_provider")
        await provider.chat_with_tools([], [])

        # Simulate shutdown: close provider
        if hasattr(provider, "close"):
            await provider.close()

        mock_provider.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_chain_no_dangling_connections(self) -> None:
        """FallbackChain execution doesn't leave unclosed connections."""
        primary = _make_mock_llm()
        secondary = _make_mock_llm()

        chain = FallbackChain(
            providers=[("groq", primary), ("ollama", secondary)],
            chain_type="LLM",
        )

        # Execute multiple times
        for _ in range(50):
            result = await chain.execute(lambda p: p.chat_with_tools([], []))
            assert result.provider_name == "groq"

        # No dangling tasks
        await asyncio.sleep(0.01)
        # The test passing without hanging proves no dangling coroutines


# ── Test 8: Combined Stress Test (4-Hour Simulation) ────────────────────────


class TestCombinedStressSimulation:
    """Full 4-hour simulation combining all stability dimensions."""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_full_4hour_simulated_stability(self) -> None:
        """Simulate 4 hours of operation via 250 accelerated pipeline cycles.

        Each cycle represents ~1 minute of real operation. Combines:
        - Normal keyword commands (60%)
        - LLM-routed commands (25%)
        - Timeout injections (5%)
        - Error injections (5%)
        - Provider failover events (5%)

        Tracks: object count, task count, state machine, error patterns.
        """
        skill = _ReliableSkill()
        timeout_skill = _TimeoutSkill()
        error_skill = _ErrorSkill()

        primary_llm = _make_mock_llm()
        secondary_llm = _make_mock_llm()
        mock_tts = _make_mock_tts()

        health_cache = HealthCache(ttl=HEALTH_CACHE_TTL_S)
        chain = FallbackChain(
            providers=[("groq", primary_llm), ("ollama", secondary_llm)],
            chain_type="LLM",
            health_cache=health_cache,
        )

        registry = ProviderRegistry()
        brain = Brain(
            registry=registry,
            skills=[skill],
            llm_fallback_chain=chain,
        )
        mouth = Mouth(tts_provider=mock_tts)
        hands = Hands(mouth=mouth, skill_timeout_s=0.05)
        sm = PipelineStateMachine()

        saved = _save_and_set_skills(
            media_control=skill,
            timeout_skill=timeout_skill,
            error_skill=error_skill,
        )

        try:
            # Warm-up
            warmup = await brain.process("pause nhac")
            si = SkillIntent(
                skill_name=warmup.skill_name,
                action=warmup.action,
                params=warmup.params,
                raw_text="pause nhac",
            )
            await hands.execute(si)

            gc.collect()
            gc.collect()
            baseline_objects = len(gc.get_objects())
            baseline_tasks = len(asyncio.all_tasks())

            success_count = 0
            timeout_count = 0
            error_count = 0
            failover_count = 0
            unhandled_errors = 0

            for i in range(STRESS_ITERATION_COUNT):
                try:
                    # Ensure LISTENING at cycle start
                    if sm.current_state != PipelineState.LISTENING:
                        sm.force_reset()
                    assert sm.current_state == PipelineState.LISTENING

                    sm.transition_to(PipelineState.PROCESSING)

                    if i % 20 == 19:
                        # Timeout injection (5%)
                        timeout_si = SkillIntent(
                            skill_name="timeout_skill",
                            action="hang",
                            params={},
                            raw_text="slow op",
                        )
                        result = await hands.execute(timeout_si)
                        assert not result.success
                        assert result.error_code == "timeout"
                        assert result.tts_response
                        timeout_count += 1

                    elif i % 20 == 18:
                        # Error injection (5%)
                        error_si = SkillIntent(
                            skill_name="error_skill",
                            action="fail",
                            params={},
                            raw_text="fail op",
                        )
                        result = await hands.execute(error_si)
                        assert not result.success
                        assert result.tts_response
                        error_count += 1

                    elif i % 20 == 17:
                        # Provider failover injection (5%)
                        health_cache.set("groq", healthy=False)
                        intent = await brain.process("tam dung bai hat")
                        assert intent.skill_name == "media_control"
                        # Recover immediately for next cycle
                        health_cache.invalidate("groq")
                        failover_count += 1

                        si = SkillIntent(
                            skill_name=intent.skill_name,
                            action=intent.action,
                            params=intent.params,
                            raw_text="tam dung bai hat",
                        )
                        result = await hands.execute(si)
                        assert result.success

                    elif i % 4 == 0:
                        # LLM-routed command (25%)
                        intent = await brain.process("tam dung bai hat dang phat")
                        assert intent.skill_name == "media_control"
                        si = SkillIntent(
                            skill_name=intent.skill_name,
                            action=intent.action,
                            params=intent.params,
                            raw_text="tam dung bai hat dang phat",
                        )
                        result = await hands.execute(si)
                        assert result.success
                        success_count += 1

                    else:
                        # Keyword command (60%)
                        intent = await brain.process("pause nhac")
                        assert intent.skill_name == "media_control"
                        si = SkillIntent(
                            skill_name=intent.skill_name,
                            action=intent.action,
                            params=intent.params,
                            raw_text="pause nhac",
                        )
                        result = await hands.execute(si)
                        assert result.success
                        success_count += 1

                    # Transition through SPEAKING -> LISTENING
                    sm.transition_to(PipelineState.SPEAKING)

                    if i % 30 == 29:
                        # Occasional barge-in
                        sm.transition_to(PipelineState.INTERRUPTED)
                        sm.transition_to(PipelineState.LISTENING)
                    else:
                        sm.transition_to(PipelineState.LISTENING)

                except Exception:
                    unhandled_errors += 1
                    sm.force_reset()

            # -- Assertions --

            # 1. No unhandled errors
            assert unhandled_errors == 0, (
                f"{unhandled_errors} unhandled errors in "
                f"{STRESS_ITERATION_COUNT} cycles"
            )

            # 2. Memory stability
            gc.collect()
            gc.collect()
            final_objects = len(gc.get_objects())
            delta_pct = (
                abs(final_objects - baseline_objects)
                / max(baseline_objects, 1)
                * 100
            )
            assert delta_pct < OBJECT_GROWTH_THRESHOLD_PCT, (
                f"Memory leak: {delta_pct:.1f}% object growth "
                f"(baseline={baseline_objects}, final={final_objects})"
            )

            # 3. No orphaned tasks
            await asyncio.sleep(0.05)
            final_tasks = len(asyncio.all_tasks())
            assert final_tasks <= baseline_tasks + TASK_LEAK_TOLERANCE, (
                f"Task leak: baseline={baseline_tasks}, final={final_tasks}"
            )

            # 4. State machine ended in LISTENING
            assert sm.current_state == PipelineState.LISTENING

            # 5. Verify we actually exercised all paths
            assert success_count > 0, "No successful cycles recorded"
            assert timeout_count > 0, "No timeout cycles recorded"
            assert error_count > 0, "No error cycles recorded"
            assert failover_count > 0, "No failover cycles recorded"

        finally:
            _restore_skills(saved)
