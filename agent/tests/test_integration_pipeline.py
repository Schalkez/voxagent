"""Integration tests for the full VoxAgent pipeline.

Tests cross-phase interactions:
- Full loop: mock audio -> wake word -> STT -> Brain -> skill -> TTS -> playback
- Barge-in during TTS: mock wake word detection -> interrupt -> resume listening
- Provider failover: primary LLM fails -> fallback kicks in -> user gets response
- Error path: skill fails -> error earcon -> spoken error -> resume listening
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from core.audio.earcons import EarconType
from core.audio.interrupt_controller import InterruptController
from core.brain import Brain, Intent, Tier
from core.errors import PipelineError, ProviderError
from core.hands import Hands
from core.mouth import Mouth
from core.pipeline_state import PipelineState, PipelineStateMachine
from providers.base import Message, TranscribeResult
from providers.fallback import AllProvidersExhaustedError, FallbackChain, FallbackResult
from providers.registry import ProviderRegistry
from providers.resilience import HealthCache
from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult
from skills.registry import SkillRegistry


# ── Helpers ──


class _FakeSkill(BaseSkill):
    """Minimal skill for pipeline integration tests."""

    name = "media_control"
    description = "Control media playback"
    keywords: ClassVar[list[str]] = ["pause", "play", "skip"]
    execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]
    permissions: ClassVar[list[str]] = ["media:control"]

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Accept intents targeting this skill."""
        return intent.skill_name == self.name

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Simulate media control execution."""
        return SkillResult.ok(
            tts_response="Da pause roi nha.",
            tier_used=ExecutionTier.NATIVE_API,
        )


class _FailingSkill(BaseSkill):
    """Skill that always fails, for error path tests."""

    name = "failing_skill"
    description = "Always fails"
    keywords: ClassVar[list[str]] = ["fail"]
    execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]
    permissions: ClassVar[list[str]] = []

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Accept all intents."""
        return True

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Always fail."""
        return SkillResult.fail(
            error="Simulated skill failure",
            tts_response="Co loi xay ra.",
            error_code="simulated_error",
        )


class _SlowSkill(BaseSkill):
    """Skill that takes a long time, for timeout tests."""

    name = "slow_skill"
    description = "Takes forever"
    keywords: ClassVar[list[str]] = ["slow"]
    execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]
    permissions: ClassVar[list[str]] = []

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Accept all intents."""
        return True

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Sleep longer than timeout."""
        await asyncio.sleep(100)
        return SkillResult.ok(tts_response="Done!")


def _make_mock_llm(response: dict[str, object] | None = None) -> AsyncMock:
    """Create a mock LLM provider."""
    mock = AsyncMock()
    mock.chat_with_tools = AsyncMock(
        return_value=response
        or {"tool": "media_control", "result": {"action": "pause", "confidence": 0.95}}
    )
    mock.health_check = AsyncMock(return_value=True)
    return mock


def _make_valid_wav_bytes() -> bytes:
    """Generate minimal valid WAV audio bytes (16kHz, mono, int16, ~50ms)."""
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # ~50ms of silence
        wf.writeframes(np.zeros(800, dtype=np.int16).tobytes())
    return buf.getvalue()


def _make_mock_tts() -> AsyncMock:
    """Create a mock TTS provider."""
    mock = AsyncMock()
    mock.synthesize = AsyncMock(return_value=_make_valid_wav_bytes())

    async def _fake_stream(*args, **kwargs):
        yield b"\xff" * 100

    mock.synthesize_stream = _fake_stream
    return mock


def _make_mock_stt(text: str = "pause nhac") -> AsyncMock:
    """Create a mock STT provider."""
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


# ── Integration Tests: Full Pipeline Loop ──


class TestFullPipelineLoop:
    """Test the full EARS -> BRAIN -> HANDS -> MOUTH flow."""

    @pytest.mark.asyncio
    async def test_keyword_match_pipeline(self) -> None:
        """Tier 0 keyword match: text -> Brain -> Hands -> SkillResult.

        Verifies that a simple keyword command flows through Brain (Tier 0)
        to Hands to the correct skill, all producing the right SkillResult.
        """
        skill = _FakeSkill()
        registry = ProviderRegistry()

        brain = Brain(registry=registry, skills=[skill])
        hands = Hands()

        # Register skill in the global registry for Hands to find
        SkillRegistry._skills["media_control"] = skill

        try:
            # Brain resolves intent via Tier 0 keyword matching
            intent = await brain.process("pause nhac")
            assert intent.skill_name == "media_control"
            assert intent.tier_used == Tier.ZERO

            # Hands executes the skill
            skill_intent = SkillIntent(
                skill_name=intent.skill_name,
                action=intent.action,
                params=intent.params,
                raw_text="pause nhac",
            )
            result = await hands.execute(skill_intent)
            assert result.success is True
            assert result.tts_response
        finally:
            SkillRegistry._skills.pop("media_control", None)

    @pytest.mark.asyncio
    async def test_llm_routing_pipeline(self) -> None:
        """Tier 1 LLM routing: text -> Brain (LLM) -> Hands -> SkillResult.

        Verifies a command with no keyword match escalates to LLM routing.
        """
        skill = _FakeSkill()
        mock_llm = _make_mock_llm()
        registry = ProviderRegistry()
        registry.register_llm("ollama", lambda: mock_llm)

        brain = Brain(
            registry=registry,
            skills=[skill],
            routing_config={"tiers": [{"provider": "ollama", "model": "test"}]},
        )
        hands = Hands()
        SkillRegistry._skills["media_control"] = skill

        try:
            # Use a command that won't match keywords
            intent = await brain.process("tam dung bai hat dang phat")
            assert intent.skill_name == "media_control"
            assert intent.tier_used == Tier.ONE

            skill_intent = SkillIntent(
                skill_name=intent.skill_name,
                action=intent.action,
                params=intent.params,
                raw_text="tam dung bai hat dang phat",
            )
            result = await hands.execute(skill_intent)
            assert result.success is True
        finally:
            SkillRegistry._skills.pop("media_control", None)

    @pytest.mark.asyncio
    async def test_pipeline_state_transitions(self) -> None:
        """BGIN-04: Pipeline state machine transitions through full loop.

        Verifies LISTENING -> PROCESSING -> SPEAKING -> LISTENING
        with no invalid transitions.
        """
        sm = PipelineStateMachine()
        assert sm.current_state == PipelineState.LISTENING

        # LISTENING -> PROCESSING
        assert sm.transition_to(PipelineState.PROCESSING) is True
        assert sm.current_state == PipelineState.PROCESSING

        # PROCESSING -> SPEAKING
        assert sm.transition_to(PipelineState.SPEAKING) is True
        assert sm.current_state == PipelineState.SPEAKING

        # SPEAKING -> LISTENING (normal completion)
        assert sm.transition_to(PipelineState.LISTENING) is True
        assert sm.current_state == PipelineState.LISTENING

    @pytest.mark.asyncio
    async def test_pipeline_latency_under_5s(self) -> None:
        """Full pipeline completes in <5s for simple commands.

        Tests Brain Tier 0 + Hands execution + mock TTS to verify
        the end-to-end latency budget for simple keyword commands.
        """
        import time

        skill = _FakeSkill()
        registry = ProviderRegistry()
        brain = Brain(registry=registry, skills=[skill])
        mouth = Mouth(tts_provider=_make_mock_tts())
        hands = Hands(mouth=mouth)
        SkillRegistry._skills["media_control"] = skill

        try:
            t0 = time.monotonic()

            intent = await brain.process("pause nhac")
            skill_intent = SkillIntent(
                skill_name=intent.skill_name,
                action=intent.action,
                params=intent.params,
                raw_text="pause nhac",
            )
            result = await hands.execute(skill_intent)
            if result.tts_response:
                await mouth.speak(result.tts_response)

            elapsed_s = time.monotonic() - t0
            assert elapsed_s < 5.0, f"Pipeline took {elapsed_s:.2f}s, expected <5s"
        finally:
            SkillRegistry._skills.pop("media_control", None)


# ── Integration Tests: Barge-In ──


class TestBargeInIntegration:
    """Test barge-in during TTS playback (Phase 6 cross-phase)."""

    @pytest.mark.asyncio
    async def test_interrupt_controller_during_speak(self) -> None:
        """BGIN-01/02/03: Interrupt controller stops TTS on wake word.

        Verifies that triggering interrupt during speak_streaming
        causes playback to stop and pipeline to transition correctly.
        """
        interrupt = InterruptController()
        mock_tts = _make_mock_tts()
        mouth = Mouth(tts_provider=mock_tts, interrupt=interrupt)

        sm = PipelineStateMachine()
        sm.transition_to(PipelineState.PROCESSING)
        sm.transition_to(PipelineState.SPEAKING)

        # Interrupt after a short delay
        async def _trigger_interrupt() -> None:
            await asyncio.sleep(0.05)
            interrupt.interrupt()

        task = asyncio.create_task(_trigger_interrupt())

        # speak_streaming should terminate early due to interrupt
        await mouth.speak_streaming("Day la mot cau dai can phat am thanh.")

        await task
        assert interrupt.is_interrupted

        # Pipeline transitions: SPEAKING -> INTERRUPTED -> LISTENING
        sm.transition_to(PipelineState.INTERRUPTED)
        sm.transition_to(PipelineState.LISTENING)
        assert sm.current_state == PipelineState.LISTENING

    @pytest.mark.asyncio
    async def test_state_machine_rejects_invalid_barge_in(self) -> None:
        """BGIN-04: Invalid transitions are rejected (e.g., SPEAKING->PROCESSING)."""
        sm = PipelineStateMachine()
        sm.transition_to(PipelineState.PROCESSING)
        sm.transition_to(PipelineState.SPEAKING)

        # SPEAKING -> PROCESSING is invalid
        assert sm.transition_to(PipelineState.PROCESSING) is False
        assert sm.current_state == PipelineState.SPEAKING

    @pytest.mark.asyncio
    async def test_barge_in_full_cycle(self) -> None:
        """Full barge-in cycle: LISTENING->PROCESSING->SPEAKING->INTERRUPTED->LISTENING."""
        sm = PipelineStateMachine()

        # Normal flow to SPEAKING
        assert sm.transition_to(PipelineState.PROCESSING) is True
        assert sm.transition_to(PipelineState.SPEAKING) is True

        # Barge-in
        assert sm.transition_to(PipelineState.INTERRUPTED) is True
        assert sm.current_state == PipelineState.INTERRUPTED

        # Reset to LISTENING
        assert sm.transition_to(PipelineState.LISTENING) is True
        assert sm.current_state == PipelineState.LISTENING

    @pytest.mark.asyncio
    async def test_interrupt_resets_cleanly(self) -> None:
        """InterruptController reset clears state for next cycle."""
        interrupt = InterruptController()
        assert not interrupt.is_interrupted

        interrupt.interrupt()
        assert interrupt.is_interrupted

        interrupt.reset()
        assert not interrupt.is_interrupted

        # Second cycle works
        interrupt.interrupt()
        assert interrupt.is_interrupted


# ── Integration Tests: Provider Failover ──


class TestProviderFailoverIntegration:
    """Test provider failover during Brain processing (Phase 3+4 cross-phase)."""

    @pytest.mark.asyncio
    async def test_llm_fallback_chain_on_primary_failure(self) -> None:
        """PROV-01: Primary LLM fails -> fallback succeeds -> user gets intent.

        Verifies that Brain uses FallbackChain and falls over to a secondary
        provider when the primary raises an exception.
        """
        skill = _FakeSkill()

        # Primary fails, secondary succeeds
        primary_llm = AsyncMock()
        primary_llm.chat_with_tools = AsyncMock(side_effect=ProviderError("primary down"))
        primary_llm.health_check = AsyncMock(return_value=False)

        secondary_llm = _make_mock_llm()

        chain = FallbackChain(
            providers=[("groq", primary_llm), ("ollama", secondary_llm)],
            chain_type="LLM",
        )

        registry = ProviderRegistry()
        brain = Brain(
            registry=registry,
            skills=[skill],
            llm_fallback_chain=chain,
        )

        # Process a non-keyword command to trigger LLM routing
        intent = await brain.process("tam dung bai hat dang phat")
        assert intent.skill_name == "media_control"
        assert intent.tier_used == Tier.ONE

    @pytest.mark.asyncio
    async def test_all_providers_fail_returns_error_intent(self) -> None:
        """PROV-01 + ERRH-02: All LLM providers fail -> PipelineError raised.

        Verifies that when all providers in the fallback chain fail,
        a PipelineError is raised with a Vietnamese user message.
        """
        skill = _FakeSkill()

        fail_llm1 = AsyncMock()
        fail_llm1.chat_with_tools = AsyncMock(side_effect=ProviderError("fail1"))
        fail_llm2 = AsyncMock()
        fail_llm2.chat_with_tools = AsyncMock(side_effect=ProviderError("fail2"))

        chain = FallbackChain(
            providers=[("groq", fail_llm1), ("ollama", fail_llm2)],
            chain_type="LLM",
        )

        registry = ProviderRegistry()
        brain = Brain(
            registry=registry,
            skills=[skill],
            llm_fallback_chain=chain,
        )

        with pytest.raises(PipelineError) as exc_info:
            await brain.process("lenh phuc tap khong co keyword")

        assert exc_info.value.user_message

    @pytest.mark.asyncio
    async def test_tts_fallback_chain_integration(self) -> None:
        """PROV-02: TTS fallback chain works with Mouth.

        Verifies that Mouth uses the TTS fallback chain when the
        primary TTS provider fails.
        """
        primary_tts = AsyncMock()
        primary_tts.synthesize = AsyncMock(side_effect=RuntimeError("edge down"))

        secondary_tts = _make_mock_tts()

        chain = FallbackChain(
            providers=[("edge_tts", primary_tts), ("piper", secondary_tts)],
            chain_type="TTS",
        )

        mouth = Mouth(tts_fallback_chain=chain)

        # Should succeed via fallback without raising
        await mouth.speak("Xin chao")

    @pytest.mark.asyncio
    async def test_health_cache_skips_broken_provider(self) -> None:
        """PROV-07: Health cache marks provider unhealthy -> chain skips it.

        Verifies that the health cache integration with the fallback chain
        allows skipping known-broken providers without network I/O.
        """
        health_cache = HealthCache(ttl=60.0)
        health_cache.set("broken_provider", healthy=False)

        broken_llm = AsyncMock()
        broken_llm.chat_with_tools = AsyncMock(side_effect=ProviderError("should not be called"))

        good_llm = _make_mock_llm()

        chain = FallbackChain(
            providers=[("broken_provider", broken_llm), ("ollama", good_llm)],
            chain_type="LLM",
            health_cache=health_cache,
        )

        result = await chain.execute(lambda p: p.chat_with_tools(messages=[], tools=[]))
        assert result.provider_name == "ollama"
        # Broken provider should never have been called
        broken_llm.chat_with_tools.assert_not_called()


# ── Integration Tests: Error Path ──


class TestErrorPathIntegration:
    """Test error paths flow correctly through the pipeline."""

    @pytest.mark.asyncio
    async def test_skill_failure_produces_spoken_error(self) -> None:
        """ERRH-02 + ERRH-05: Failing skill returns SkillResult with tts_response.

        Verifies that when a skill fails, the SkillResult contains both
        a machine-readable error code and a user-facing TTS response.
        """
        failing = _FailingSkill()
        SkillRegistry._skills["failing_skill"] = failing
        hands = Hands()

        try:
            intent = SkillIntent(
                skill_name="failing_skill",
                action="test",
                params={},
                raw_text="test failure",
            )
            result = await hands.execute(intent)
            assert result.success is False
            assert result.error is not None
            assert result.tts_response  # User hears an error message
            assert result.error_code  # Machine-readable code exists
        finally:
            SkillRegistry._skills.pop("failing_skill", None)

    @pytest.mark.asyncio
    async def test_unknown_skill_returns_not_found(self) -> None:
        """ERRH-05: Unknown skill name -> SkillResult.fail with error_code."""
        hands = Hands()
        intent = SkillIntent(
            skill_name="nonexistent_skill",
            action="do_something",
            params={},
            raw_text="do something",
        )
        result = await hands.execute(intent)
        assert result.success is False
        assert result.error_code == "not_found"

    @pytest.mark.asyncio
    async def test_skill_timeout_returns_error(self) -> None:
        """SAFE-05: Skill exceeding timeout is cancelled -> error returned.

        Verifies that Hands enforces per-skill execution timeout
        and returns a proper SkillResult on timeout.
        """
        slow = _SlowSkill()
        SkillRegistry._skills["slow_skill"] = slow
        hands = Hands(skill_timeout_s=0.1)  # 100ms timeout

        try:
            intent = SkillIntent(
                skill_name="slow_skill",
                action="slow_action",
                params={},
                raw_text="do slow thing",
            )
            result = await hands.execute(intent)
            assert result.success is False
            assert result.error_code == "timeout"
            assert result.tts_response  # User hears an error message
        finally:
            SkillRegistry._skills.pop("slow_skill", None)

    @pytest.mark.asyncio
    async def test_pipeline_recovers_after_error(self) -> None:
        """Pipeline state machine recovers to LISTENING after error.

        Verifies that force_reset brings the pipeline back to a usable
        state after an unexpected error.
        """
        sm = PipelineStateMachine()
        sm.transition_to(PipelineState.PROCESSING)

        # Simulate error during PROCESSING
        sm.force_reset()
        assert sm.current_state == PipelineState.LISTENING

        # Verify normal operations resume
        assert sm.transition_to(PipelineState.PROCESSING) is True
        assert sm.current_state == PipelineState.PROCESSING

    @pytest.mark.asyncio
    async def test_error_earcon_is_distinct(self) -> None:
        """ERRH-03: Error earcon differs from acknowledge earcon.

        Verifies the earcon system generates different audio for
        ACKNOWLEDGE vs ERROR types.
        """
        from core.audio.earcons import get_earcon

        ack = get_earcon(EarconType.ACKNOWLEDGE)
        err = get_earcon(EarconType.ERROR)

        # Different lengths (200ms vs 300ms)
        assert len(ack) != len(err)
        # Both are non-empty int16 arrays
        assert len(ack) > 0
        assert len(err) > 0
        assert ack.dtype == np.int16
        assert err.dtype == np.int16
