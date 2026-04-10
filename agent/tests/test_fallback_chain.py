"""Tests for the generic FallbackChain[T] and provider fallback wiring.

Covers PROV-01 (LLM fallback), PROV-02 (TTS fallback), PROV-03 (STT fallback),
and ERRH-02 (spoken error messages instead of silent failures).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from providers.base import (
    LLMProvider,
    Message,
    ModelInfo,
    STTProvider,
    TranscribeResult,
    TTSProvider,
)
from providers.fallback import (
    AllProvidersExhaustedError,
    FallbackChain,
    FallbackResult,
)
from providers.registry import ProviderRegistry
from providers.resilience import HealthCache


# ── Mock Providers ──────────────────────────────────────────────────────────


class MockHealthyLLM(LLMProvider):
    """Mock LLM that always succeeds."""

    def __init__(self, name: str = "healthy") -> None:
        self.name = name
        self.call_count = 0

    async def chat(self, messages: list[Message], **kwargs: object) -> str:
        self.call_count += 1
        return f"response from {self.name}"

    async def chat_with_tools(
        self, messages: list[Message], tools: list[dict[str, object]], **kwargs: object
    ) -> dict[str, object]:
        self.call_count += 1
        return {"tool": "media_control", "result": {"action": "play", "confidence": 0.95}}

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(name=self.name, provider="mock")

    async def health_check(self) -> bool:
        return True


class MockFailingLLM(LLMProvider):
    """Mock LLM that always raises an error."""

    def __init__(self, name: str = "failing") -> None:
        self.name = name
        self.call_count = 0

    async def chat(self, messages: list[Message], **kwargs: object) -> str:
        self.call_count += 1
        raise ConnectionError(f"{self.name} connection failed")

    async def chat_with_tools(
        self, messages: list[Message], tools: list[dict[str, object]], **kwargs: object
    ) -> dict[str, object]:
        self.call_count += 1
        raise ConnectionError(f"{self.name} connection failed")

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(name=self.name, provider="mock")

    async def health_check(self) -> bool:
        return False


class MockSlowLLM(LLMProvider):
    """Mock LLM that takes too long (triggers timeout)."""

    async def chat(self, messages: list[Message], **kwargs: object) -> str:
        await asyncio.sleep(100)
        return "never reaches here"

    async def chat_with_tools(
        self, messages: list[Message], tools: list[dict[str, object]], **kwargs: object
    ) -> dict[str, object]:
        await asyncio.sleep(100)
        return {}

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(name="slow", provider="mock")

    async def health_check(self) -> bool:
        return True


class MockHealthySTT(STTProvider):
    """Mock STT that always returns transcribed text."""

    def __init__(self, text: str = "hello world") -> None:
        self._text = text
        self.call_count = 0

    async def transcribe(
        self, audio: bytes, language: str = "vi", task: str = "transcribe"
    ) -> TranscribeResult:
        self.call_count += 1
        return TranscribeResult(text=self._text, confidence=0.95, language=language, duration_ms=500)


class MockFailingSTT(STTProvider):
    """Mock STT that always fails."""

    def __init__(self) -> None:
        self.call_count = 0

    async def transcribe(
        self, audio: bytes, language: str = "vi", task: str = "transcribe"
    ) -> TranscribeResult:
        self.call_count += 1
        raise ConnectionError("STT API unreachable")


class MockHealthyTTS(TTSProvider):
    """Mock TTS that returns WAV data."""

    def __init__(self, name: str = "healthy_tts") -> None:
        self.name = name
        self.call_count = 0

    async def synthesize(
        self, text: str, voice: str = "vi-female", speed: float = 1.0
    ) -> bytes:
        self.call_count += 1
        return b"RIFF" + b"\x00" * 100  # Fake WAV header


class MockFailingTTS(TTSProvider):
    """Mock TTS that always fails."""

    def __init__(self) -> None:
        self.call_count = 0

    async def synthesize(
        self, text: str, voice: str = "vi-female", speed: float = 1.0
    ) -> bytes:
        self.call_count += 1
        raise ConnectionError("TTS API unreachable")


# ── FallbackChain Core Tests ───────────────────────────────────────────────


class TestFallbackChainBasic:
    """Test FallbackChain core behavior."""

    @pytest.mark.asyncio
    async def test_first_provider_succeeds(self) -> None:
        """Should return result from first provider without trying others."""
        p1 = MockHealthyLLM("primary")
        p2 = MockHealthyLLM("secondary")

        chain = FallbackChain(
            providers=[("primary", p1), ("secondary", p2)],
            chain_type="LLM",
        )

        result = await chain.execute(lambda llm: llm.chat([]))
        assert result.provider_name == "primary"
        assert result.attempts == 1
        assert "response from primary" in result.value
        assert p1.call_count == 1
        assert p2.call_count == 0

    @pytest.mark.asyncio
    async def test_failover_to_second_provider(self) -> None:
        """Should fail over to second provider when first fails."""
        p1 = MockFailingLLM("failing")
        p2 = MockHealthyLLM("backup")

        chain = FallbackChain(
            providers=[("failing", p1), ("backup", p2)],
            chain_type="LLM",
        )

        result = await chain.execute(lambda llm: llm.chat([]))
        assert result.provider_name == "backup"
        assert result.attempts == 2
        assert "response from backup" in result.value

    @pytest.mark.asyncio
    async def test_all_providers_fail_raises(self) -> None:
        """Should raise AllProvidersExhaustedError when all fail."""
        p1 = MockFailingLLM("fail1")
        p2 = MockFailingLLM("fail2")

        chain = FallbackChain(
            providers=[("fail1", p1), ("fail2", p2)],
            chain_type="LLM",
        )

        with pytest.raises(AllProvidersExhaustedError) as exc_info:
            await chain.execute(lambda llm: llm.chat([]))
        assert "fail1" in exc_info.value.providers_tried
        assert "fail2" in exc_info.value.providers_tried

    @pytest.mark.asyncio
    async def test_empty_chain_raises(self) -> None:
        """Should raise when chain has no providers."""
        chain: FallbackChain[LLMProvider] = FallbackChain(
            providers=[],
            chain_type="LLM",
        )

        with pytest.raises(AllProvidersExhaustedError):
            await chain.execute(lambda llm: llm.chat([]))

    @pytest.mark.asyncio
    async def test_result_includes_latency(self) -> None:
        """Should include total latency measurement."""
        p1 = MockHealthyLLM()
        chain = FallbackChain(
            providers=[("p1", p1)],
            chain_type="LLM",
        )

        result = await chain.execute(lambda llm: llm.chat([]))
        assert isinstance(result.total_latency_ms, int)
        assert result.total_latency_ms >= 0

    @pytest.mark.asyncio
    async def test_provider_names_property(self) -> None:
        """Should return ordered provider names."""
        chain = FallbackChain[LLMProvider](
            providers=[
                ("groq", MockHealthyLLM()),
                ("ollama", MockHealthyLLM()),
            ],
            chain_type="LLM",
        )
        assert chain.provider_names == ["groq", "ollama"]


# ── Health Cache Integration ───────────────────────────────────────────────


class TestFallbackChainHealthCache:
    """Test FallbackChain integration with HealthCache."""

    @pytest.mark.asyncio
    async def test_skips_cached_unhealthy_provider(self) -> None:
        """Should skip providers marked unhealthy in health cache."""
        cache = HealthCache(ttl=60.0)
        cache.set("cloud_provider", healthy=False)

        p1 = MockHealthyLLM("cloud_provider")
        p2 = MockHealthyLLM("local_provider")

        chain = FallbackChain(
            providers=[("cloud_provider", p1), ("local_provider", p2)],
            chain_type="LLM",
            health_cache=cache,
        )

        result = await chain.execute(lambda llm: llm.chat([]))
        assert result.provider_name == "local_provider"
        assert p1.call_count == 0  # Skipped entirely
        assert p2.call_count == 1

    @pytest.mark.asyncio
    async def test_marks_provider_unhealthy_on_failure(self) -> None:
        """Should update health cache when a provider fails."""
        cache = HealthCache(ttl=60.0)
        p1 = MockFailingLLM("cloud")
        p2 = MockHealthyLLM("local")

        chain = FallbackChain(
            providers=[("cloud", p1), ("local", p2)],
            chain_type="LLM",
            health_cache=cache,
        )

        await chain.execute(lambda llm: llm.chat([]))
        assert cache.get("cloud") is False
        assert cache.get("local") is True

    @pytest.mark.asyncio
    async def test_marks_provider_healthy_on_success(self) -> None:
        """Should mark provider healthy in cache after success."""
        cache = HealthCache(ttl=60.0)
        p1 = MockHealthyLLM()

        chain = FallbackChain(
            providers=[("p1", p1)],
            chain_type="LLM",
            health_cache=cache,
        )

        await chain.execute(lambda llm: llm.chat([]))
        assert cache.get("p1") is True


# ── Timeout Budget Tests ───────────────────────────────────────────────────


class TestFallbackChainTimeout:
    """Test per-provider and total budget enforcement."""

    @pytest.mark.asyncio
    async def test_per_provider_timeout(self) -> None:
        """Should timeout a slow provider and move to next."""
        slow = MockSlowLLM()
        fast = MockHealthyLLM("fast")

        chain = FallbackChain(
            providers=[("slow", slow), ("fast", fast)],
            chain_type="LLM",
            per_provider_timeout_s=0.1,
            total_budget_s=5.0,
        )

        result = await chain.execute(lambda llm: llm.chat([]))
        assert result.provider_name == "fast"
        assert result.attempts == 2

    @pytest.mark.asyncio
    async def test_total_budget_exhausted(self) -> None:
        """Should stop trying when total budget is exceeded."""
        slow1 = MockSlowLLM()
        slow2 = MockSlowLLM()

        chain = FallbackChain(
            providers=[("slow1", slow1), ("slow2", slow2)],
            chain_type="LLM",
            per_provider_timeout_s=0.2,
            total_budget_s=0.3,
        )

        with pytest.raises(AllProvidersExhaustedError):
            await chain.execute(lambda llm: llm.chat([]))


# ── Failover Callback Tests ───────────────────────────────────────────────


class TestFallbackChainCallback:
    """Test failover notification callbacks."""

    @pytest.mark.asyncio
    async def test_failover_callback_invoked(self) -> None:
        """Should invoke callback with correct arguments on failover."""
        callback = AsyncMock()
        p1 = MockFailingLLM("primary")
        p2 = MockHealthyLLM("secondary")

        chain = FallbackChain(
            providers=[("primary", p1), ("secondary", p2)],
            chain_type="LLM",
        )
        chain.on_failover(callback)

        await chain.execute(lambda llm: llm.chat([]))
        callback.assert_awaited_once_with("LLM", "primary", "secondary")

    @pytest.mark.asyncio
    async def test_callback_exception_does_not_break_chain(self) -> None:
        """Should continue even if the callback raises."""
        async def broken_callback(chain_type: str, failed: str, next_p: str) -> None:
            raise ValueError("callback error")

        p1 = MockFailingLLM()
        p2 = MockHealthyLLM()

        chain = FallbackChain(
            providers=[("p1", p1), ("p2", p2)],
            chain_type="LLM",
        )
        chain.on_failover(broken_callback)

        result = await chain.execute(lambda llm: llm.chat([]))
        assert result.provider_name == "p2"


# ── PROV-01: LLM Fallback in Brain ────────────────────────────────────────


class TestBrainLLMFallback:
    """Test Brain uses FallbackChain[LLMProvider] for intent routing."""

    @pytest.mark.asyncio
    async def test_brain_uses_fallback_chain(self) -> None:
        """PROV-01: Brain should use fallback chain for LLM calls."""
        from core.brain import Brain

        registry = ProviderRegistry()
        registry.register_llm("failing", MockFailingLLM)
        registry.register_llm("healthy", MockHealthyLLM)

        healthy_llm = MockHealthyLLM("healthy")
        failing_llm = MockFailingLLM("failing")

        llm_chain = FallbackChain[LLMProvider](
            providers=[("failing", failing_llm), ("healthy", healthy_llm)],
            chain_type="LLM",
        )

        from unittest.mock import MagicMock

        mock_skill = MagicMock()
        mock_skill.name = "media_control"
        mock_skill.description = "Controls media"
        mock_skill.keywords = []

        brain = Brain(
            registry=registry,
            skills=[mock_skill],
            llm_fallback_chain=llm_chain,
        )

        intent = await brain.process("play some music")
        # Should have used fallback chain (second provider succeeded)
        assert intent.skill_name == "media_control"

    @pytest.mark.asyncio
    async def test_brain_all_llm_fail_returns_pipeline_error(self) -> None:
        """PROV-01: All LLM providers fail -> PipelineError."""
        from core.brain import Brain
        from core.errors import PipelineError

        registry = ProviderRegistry()

        llm_chain = FallbackChain[LLMProvider](
            providers=[
                ("fail1", MockFailingLLM("fail1")),
                ("fail2", MockFailingLLM("fail2")),
            ],
            chain_type="LLM",
        )

        mock_skill = MagicMock()
        mock_skill.name = "test_skill"
        mock_skill.description = "Test"
        mock_skill.keywords = []

        brain = Brain(
            registry=registry,
            skills=[mock_skill],
            llm_fallback_chain=llm_chain,
        )

        with pytest.raises(PipelineError, match="All LLM providers failed"):
            await brain.process("some command that needs LLM")


# ── PROV-02: TTS Fallback in Mouth ────────────────────────────────────────


class TestMouthTTSFallback:
    """Test Mouth uses FallbackChain[TTSProvider] for speech synthesis."""

    @pytest.mark.asyncio
    async def test_mouth_uses_tts_fallback_chain(self) -> None:
        """PROV-02: Mouth should fail over from cloud TTS to local TTS."""
        from core.mouth import Mouth

        failing_tts = MockFailingTTS()
        healthy_tts = MockHealthyTTS("backup_tts")

        tts_chain = FallbackChain[TTSProvider](
            providers=[("edge_tts", failing_tts), ("piper", healthy_tts)],
            chain_type="TTS",
        )

        mouth = Mouth(tts_fallback_chain=tts_chain)

        with patch("core.mouth._play_wav", new_callable=AsyncMock):
            await mouth.speak("Xin chao")

        assert failing_tts.call_count == 1
        assert healthy_tts.call_count == 1

    @pytest.mark.asyncio
    async def test_mouth_all_tts_fail_logs_error(self) -> None:
        """PROV-02: All TTS fail -> error logged, no crash."""
        from core.mouth import Mouth

        tts_chain = FallbackChain[TTSProvider](
            providers=[
                ("tts1", MockFailingTTS()),
                ("tts2", MockFailingTTS()),
            ],
            chain_type="TTS",
        )

        mouth = Mouth(tts_fallback_chain=tts_chain)
        # Should not raise — logs the error
        await mouth.speak("test")

    @pytest.mark.asyncio
    async def test_mouth_single_provider_still_works(self) -> None:
        """Backward compatibility: Mouth works with single provider."""
        from core.mouth import Mouth

        tts = MockHealthyTTS()
        mouth = Mouth(tts_provider=tts)

        with patch("core.mouth._play_wav", new_callable=AsyncMock):
            await mouth.speak("hello")
        assert tts.call_count == 1


# ── PROV-03: STT Fallback in Ears ─────────────────────────────────────────


class TestEarsSTTFallback:
    """Test Ears uses FallbackChain[STTProvider] for transcription."""

    @pytest.mark.asyncio
    async def test_ears_stt_fallback_chain(self) -> None:
        """PROV-03: Ears should try cloud STT, then local on failure."""
        failing_stt = MockFailingSTT()
        healthy_stt = MockHealthySTT("transcribed text")

        stt_chain = FallbackChain[STTProvider](
            providers=[("openai_whisper", failing_stt), ("whisper_local", healthy_stt)],
            chain_type="STT",
        )

        from core.ears import Ears

        config = MagicMock()
        config.stt.language = "vi"
        config.wake_word.sensitivity = 0.5

        ears = Ears(
            stt_provider=failing_stt,
            config=config,
            stt_fallback_chain=stt_chain,
        )

        result = await ears._transcribe_with_fallback(b"fake wav data")
        assert result.text == "transcribed text"
        assert failing_stt.call_count == 1
        assert healthy_stt.call_count == 1

    @pytest.mark.asyncio
    async def test_ears_all_stt_fail_raises_pipeline_error(self) -> None:
        """PROV-03: All STT fail -> PipelineError with user message."""
        from core.ears import Ears
        from core.errors import PipelineError

        failing1 = MockFailingSTT()
        failing2 = MockFailingSTT()

        stt_chain = FallbackChain[STTProvider](
            providers=[("stt1", failing1), ("stt2", failing2)],
            chain_type="STT",
        )

        config = MagicMock()
        config.stt.language = "vi"
        config.wake_word.sensitivity = 0.5

        ears = Ears(
            stt_provider=failing1,
            config=config,
            stt_fallback_chain=stt_chain,
        )

        with pytest.raises(PipelineError, match="All STT providers failed"):
            await ears._transcribe_with_fallback(b"fake wav data")

    @pytest.mark.asyncio
    async def test_ears_single_stt_backward_compat(self) -> None:
        """Backward compatibility: Ears works with single STT provider."""
        healthy_stt = MockHealthySTT("hello")

        config = MagicMock()
        config.stt.language = "vi"
        config.wake_word.sensitivity = 0.5

        from core.ears import Ears

        ears = Ears(stt_provider=healthy_stt, config=config)
        result = await ears._transcribe_with_fallback(b"fake wav data")
        assert result.text == "hello"


# ── Registry Factory Methods ──────────────────────────────────────────────


class TestRegistryFallbackFactories:
    """Test ProviderRegistry.create_*_fallback_chain() methods."""

    def test_create_llm_fallback_chain(self) -> None:
        """Should create chain with registered LLM providers."""
        registry = ProviderRegistry()
        registry.register_llm("groq", MockHealthyLLM)
        registry.register_llm("ollama", MockHealthyLLM)
        registry.set_fallback_chain(["groq", "ollama"])

        chain = registry.create_llm_fallback_chain()
        assert chain.chain_type == "LLM"
        assert chain.provider_names == ["groq", "ollama"]
        assert chain.health_cache is registry.health_cache

    def test_create_stt_fallback_chain(self) -> None:
        """Should create chain with registered STT providers."""
        registry = ProviderRegistry()
        registry.register_stt("openai_whisper", MockHealthySTT)
        registry.register_stt("whisper_local", MockHealthySTT)

        chain = registry.create_stt_fallback_chain(["openai_whisper", "whisper_local"])
        assert chain.chain_type == "STT"
        assert len(chain.providers) == 2

    def test_create_tts_fallback_chain(self) -> None:
        """Should create chain with registered TTS providers."""
        registry = ProviderRegistry()
        registry.register_tts("edge_tts", MockHealthyTTS)
        registry.register_tts("piper", MockHealthyTTS)

        chain = registry.create_tts_fallback_chain(["edge_tts", "piper"])
        assert chain.chain_type == "TTS"
        assert len(chain.providers) == 2

    def test_create_chain_skips_unregistered(self) -> None:
        """Should skip providers not registered in the registry."""
        registry = ProviderRegistry()
        registry.register_llm("ollama", MockHealthyLLM)

        chain = registry.create_llm_fallback_chain(["nonexistent", "ollama"])
        assert chain.provider_names == ["ollama"]

    def test_create_chain_empty_when_no_providers(self) -> None:
        """Should return empty chain when no providers match."""
        registry = ProviderRegistry()
        chain = registry.create_llm_fallback_chain(["nonexistent"])
        assert chain.providers == []


# ── ERRH-02: Spoken Error Messages ────────────────────────────────────────


class TestSpokenErrors:
    """Test that provider failures produce spoken error messages (ERRH-02)."""

    @pytest.mark.asyncio
    async def test_all_providers_exhausted_has_user_message(self) -> None:
        """AllProvidersExhaustedError should carry a Vietnamese user message."""
        err = AllProvidersExhaustedError("LLM", ["groq", "ollama"])
        assert err.user_message
        assert "nha cung cap" in err.user_message.lower()
        assert err.providers_tried == ["groq", "ollama"]

    @pytest.mark.asyncio
    async def test_pipeline_error_from_brain_has_user_message(self) -> None:
        """Brain PipelineError should have a speakable message."""
        from core.brain import Brain
        from core.errors import PipelineError

        registry = ProviderRegistry()
        chain = FallbackChain[LLMProvider](
            providers=[("fail", MockFailingLLM())],
            chain_type="LLM",
        )

        mock_skill = MagicMock()
        mock_skill.name = "test"
        mock_skill.description = "Test"
        mock_skill.keywords = []

        brain = Brain(
            registry=registry,
            skills=[mock_skill],
            llm_fallback_chain=chain,
        )

        with pytest.raises(PipelineError) as exc_info:
            await brain.process("test command for LLM")

        assert exc_info.value.user_message
        assert len(exc_info.value.user_message) > 0

    @pytest.mark.asyncio
    async def test_pipeline_error_from_ears_has_user_message(self) -> None:
        """Ears PipelineError should have a speakable message."""
        from core.ears import Ears
        from core.errors import PipelineError

        chain = FallbackChain[STTProvider](
            providers=[("fail", MockFailingSTT())],
            chain_type="STT",
        )

        config = MagicMock()
        config.stt.language = "vi"
        config.wake_word.sensitivity = 0.5

        ears = Ears(
            stt_provider=MockFailingSTT(),
            config=config,
            stt_fallback_chain=chain,
        )

        with pytest.raises(PipelineError) as exc_info:
            await ears._transcribe_with_fallback(b"audio")

        assert "giong noi" in exc_info.value.user_message.lower()


# ── FallbackResult Tests ──────────────────────────────────────────────────


class TestFallbackResult:
    """Test FallbackResult data class."""

    def test_result_fields(self) -> None:
        """Should correctly store all result fields."""
        result = FallbackResult(
            value="test",
            provider_name="groq",
            attempts=2,
            total_latency_ms=150,
        )
        assert result.value == "test"
        assert result.provider_name == "groq"
        assert result.attempts == 2
        assert result.total_latency_ms == 150
