"""Shared test fixtures and mock providers."""

import pytest

from providers.base import LLMProvider, Message, ModelInfo, STTProvider, TranscribeResult


class MockLLMProvider(LLMProvider):
    """Mock LLM that returns canned responses for testing."""

    def __init__(self, response: str = "mock response") -> None:
        self._response = response

    async def chat(self, messages: list[Message], **kwargs: object) -> str:
        """Return the canned response."""
        return self._response

    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict[str, object]],
        **kwargs: object,
    ) -> dict[str, object]:
        """Return a mock tool call result."""
        return {"tool": "none", "result": self._response}

    def get_model_info(self) -> ModelInfo:
        """Return mock model info."""
        return ModelInfo(name="mock-llm", provider="test")

    async def health_check(self) -> bool:
        """Always healthy."""
        return True


class MockSTTProvider(STTProvider):
    """Mock STT that returns predetermined transcription."""

    def __init__(self, text: str = "test transcription") -> None:
        self._text = text

    async def transcribe(self, audio: bytes, language: str = "vi") -> TranscribeResult:
        """Return mock transcription."""
        return TranscribeResult(
            text=self._text,
            confidence=0.95,
            language=language,
            duration_ms=1000,
        )


@pytest.fixture
def mock_llm() -> MockLLMProvider:
    """Provide a default mock LLM provider."""
    return MockLLMProvider()


@pytest.fixture
def mock_llm_factory():
    """Factory fixture for creating mock LLMs with custom responses."""

    def _factory(response: str = "mock") -> MockLLMProvider:
        return MockLLMProvider(response=response)

    return _factory


@pytest.fixture
def mock_stt() -> MockSTTProvider:
    """Provide a default mock STT provider."""
    return MockSTTProvider()
