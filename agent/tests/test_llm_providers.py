"""Tests for LLM providers (OpenAI, Groq, Anthropic, Ollama, DeepSeek, Mistral, OpenRouter)."""

from unittest.mock import patch

import pytest

from providers.base import ModelInfo


class TestOpenAIProvider:
    """Test OpenAI LLM provider."""

    def test_model_info(self) -> None:
        with patch("providers.openai_provider.get_key", return_value="fake-key"):
            from providers.openai_provider import OpenAIProvider

            p = OpenAIProvider()
            info = p.get_model_info()
            assert isinstance(info, ModelInfo)
            assert info.provider == "openai"

    @pytest.mark.asyncio
    async def test_health_check_without_key(self) -> None:
        with patch("providers.openai_provider.get_key", return_value=None):
            from providers.openai_provider import OpenAIProvider

            p = OpenAIProvider()
            result = await p.health_check()
            assert result is False


class TestGroqProvider:
    """Test Groq LLM provider."""

    def test_model_info(self) -> None:
        with patch("providers.groq_provider.get_key", return_value="fake-key"):
            from providers.groq_provider import GroqProvider

            p = GroqProvider()
            info = p.get_model_info()
            assert isinstance(info, ModelInfo)
            assert info.provider == "groq"

    @pytest.mark.asyncio
    async def test_health_check_without_key(self) -> None:
        with patch("providers.groq_provider.get_key", return_value=None):
            from providers.groq_provider import GroqProvider

            p = GroqProvider()
            result = await p.health_check()
            assert result is False


class TestAnthropicProvider:
    """Test Anthropic LLM provider."""

    def test_model_info(self) -> None:
        with patch("providers.anthropic_provider.get_key", return_value="fake-key"):
            from providers.anthropic_provider import AnthropicProvider

            p = AnthropicProvider()
            info = p.get_model_info()
            assert isinstance(info, ModelInfo)
            assert info.provider == "anthropic"

    @pytest.mark.asyncio
    async def test_health_check_without_key(self) -> None:
        with patch("providers.anthropic_provider.get_key", return_value=None):
            from providers.anthropic_provider import AnthropicProvider

            p = AnthropicProvider()
            result = await p.health_check()
            assert result is False


class TestOllamaProvider:
    """Test Ollama LLM provider."""

    def test_model_info(self) -> None:
        from providers.ollama_provider import OllamaProvider

        p = OllamaProvider()
        info = p.get_model_info()
        assert isinstance(info, ModelInfo)
        assert info.provider == "ollama"


class TestDeepSeekProvider:
    """Test DeepSeek LLM provider."""

    def test_model_info(self) -> None:
        with patch("providers.deepseek_provider.get_key", return_value="fake-key"):
            from providers.deepseek_provider import DeepSeekProvider

            p = DeepSeekProvider()
            info = p.get_model_info()
            assert isinstance(info, ModelInfo)
            assert info.provider == "deepseek"


class TestMistralProvider:
    """Test Mistral LLM provider."""

    def test_model_info(self) -> None:
        with patch("providers.mistral_provider.get_key", return_value="fake-key"):
            from providers.mistral_provider import MistralProvider

            p = MistralProvider()
            info = p.get_model_info()
            assert isinstance(info, ModelInfo)
            assert info.provider == "mistral"


class TestOpenRouterProvider:
    """Test OpenRouter LLM provider."""

    def test_model_info(self) -> None:
        with patch("providers.openrouter_provider.get_key", return_value="fake-key"):
            from providers.openrouter_provider import OpenRouterProvider

            p = OpenRouterProvider()
            info = p.get_model_info()
            assert isinstance(info, ModelInfo)
            assert info.provider == "openrouter"
