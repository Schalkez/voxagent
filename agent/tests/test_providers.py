"""Tests for the provider registry and fallback chain."""


import pytest

from providers.base import (
    LLMProvider,
    Message,
    ModelInfo,
    STTProvider,
    TranscribeResult,
    TTSProvider,
)
from providers.registry import ProviderNotFoundError, ProviderRegistry


class MockLLM(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, healthy: bool = True) -> None:
        self._healthy = healthy

    async def chat(self, messages: list[Message], **kwargs: object) -> str:
        return "mock response"

    async def chat_with_tools(
        self, messages: list[Message], tools: list[dict[str, object]], **kwargs: object
    ) -> dict[str, object]:
        return {"tool": "", "result": "mock"}

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(name="mock", provider="mock")

    async def health_check(self) -> bool:
        return self._healthy


class MockUnhealthyLLM(LLMProvider):
    """Mock LLM that always fails health check."""

    async def chat(self, messages: list[Message], **kwargs: object) -> str:
        return ""

    async def chat_with_tools(
        self, messages: list[Message], tools: list[dict[str, object]], **kwargs: object
    ) -> dict[str, object]:
        return {"tool": "", "result": ""}

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(name="unhealthy", provider="mock")

    async def health_check(self) -> bool:
        return False


class MockSTT(STTProvider):
    """Mock STT provider."""

    async def transcribe(self, audio: bytes, language: str = "vi") -> TranscribeResult:
        return TranscribeResult(text="mock text", confidence=0.9, language=language, duration_ms=100)


class MockTTS(TTSProvider):
    """Mock TTS provider."""

    async def synthesize(self, text: str, voice: str = "vi-female", speed: float = 1.0) -> bytes:
        return b"mock wav data"


class TestProviderRegistryLLM:
    """Test LLM provider registration and retrieval."""

    def test_register_and_get(self) -> None:
        """Should register and retrieve an LLM provider."""
        registry = ProviderRegistry()
        registry.register_llm("test", MockLLM)
        provider = registry.get_llm("test")
        assert isinstance(provider, MockLLM)

    def test_get_unregistered_raises(self) -> None:
        """Should raise ProviderNotFoundError for unknown providers."""
        registry = ProviderRegistry()
        with pytest.raises(ProviderNotFoundError):
            registry.get_llm("nonexistent")

    def test_get_returns_cached_instance(self) -> None:
        """Each get_llm call should return the same cached instance."""
        registry = ProviderRegistry()
        registry.register_llm("test", MockLLM)
        a = registry.get_llm("test")
        b = registry.get_llm("test")
        assert a is b


class TestProviderRegistrySTT:
    """Test STT provider registration."""

    def test_register_and_get_stt(self) -> None:
        """Should register and retrieve an STT provider."""
        registry = ProviderRegistry()
        registry.register_stt("test", MockSTT)
        provider = registry.get_stt("test")
        assert isinstance(provider, MockSTT)

    def test_get_stt_unregistered_raises(self) -> None:
        """Should raise for unknown STT providers."""
        registry = ProviderRegistry()
        with pytest.raises(ProviderNotFoundError):
            registry.get_stt("nonexistent")


class TestProviderRegistryTTS:
    """Test TTS provider registration."""

    def test_register_and_get_tts(self) -> None:
        """Should register and retrieve a TTS provider."""
        registry = ProviderRegistry()
        registry.register_tts("test", MockTTS)
        provider = registry.get_tts("test")
        assert isinstance(provider, MockTTS)


class TestFallbackChain:
    """Test LLM fallback chain logic."""

    @pytest.mark.asyncio
    async def test_fallback_returns_healthy_provider(self) -> None:
        """Should return the first healthy provider in the chain."""
        registry = ProviderRegistry()
        registry.register_llm("unhealthy", MockUnhealthyLLM)
        registry.register_llm("healthy", MockLLM)
        registry.set_fallback_chain(["unhealthy", "healthy"])

        provider = await registry.get_llm_with_fallback()
        assert isinstance(provider, MockLLM)

    @pytest.mark.asyncio
    async def test_fallback_raises_when_all_fail(self) -> None:
        """Should raise when no providers are healthy."""
        registry = ProviderRegistry()
        registry.register_llm("a", MockUnhealthyLLM)
        registry.register_llm("b", MockUnhealthyLLM)
        registry.set_fallback_chain(["a", "b"])

        with pytest.raises(ProviderNotFoundError):
            await registry.get_llm_with_fallback()

    @pytest.mark.asyncio
    async def test_empty_fallback_chain_raises(self) -> None:
        """Should raise with empty fallback chain."""
        registry = ProviderRegistry()
        registry.set_fallback_chain([])

        with pytest.raises(ProviderNotFoundError):
            await registry.get_llm_with_fallback()
