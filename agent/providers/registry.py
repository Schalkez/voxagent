"""Provider registry with fallback chain support.

Core modules access providers exclusively through this registry.
Direct imports of provider implementations are prohibited.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from providers.base import (
        LLMProvider,
        STTProvider,
        TTSProvider,
        VisionProvider,
    )


class ProviderNotFoundError(KeyError):
    """Raised when a requested provider is not registered."""


class ProviderRegistry:
    """Factory for creating and managing provider instances.

    All provider types (LLM, STT, TTS, Vision) are registered by name
    and instantiated on demand. Supports a fallback chain for automatic
    failover when a provider is unavailable.
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._llm_providers: dict[str, type[LLMProvider]] = {}
        self._stt_providers: dict[str, type[STTProvider]] = {}
        self._tts_providers: dict[str, type[TTSProvider]] = {}
        self._vision_providers: dict[str, type[VisionProvider]] = {}
        self._fallback_chain: list[str] = []

    # ── LLM ──

    def register_llm(self, name: str, provider_class: type[LLMProvider]) -> None:
        """Register an LLM provider class by name.

        Args:
            name: Provider identifier (e.g., 'ollama', 'openai').
            provider_class: The provider class to register.
        """
        self._llm_providers[name] = provider_class

    def get_llm(self, name: str) -> LLMProvider:
        """Get an LLM provider instance by name.

        Args:
            name: Provider identifier.

        Returns:
            An instantiated LLMProvider.

        Raises:
            ProviderNotFoundError: If the provider is not registered.
        """
        if name not in self._llm_providers:
            msg = f"LLM provider '{name}' not registered. Available: {list(self._llm_providers)}"
            raise ProviderNotFoundError(msg)
        return self._llm_providers[name]()

    # ── STT ──

    def register_stt(self, name: str, provider_class: type[STTProvider]) -> None:
        """Register an STT provider class by name."""
        self._stt_providers[name] = provider_class

    def get_stt(self, name: str) -> STTProvider:
        """Get an STT provider instance by name."""
        if name not in self._stt_providers:
            msg = f"STT provider '{name}' not registered. Available: {list(self._stt_providers)}"
            raise ProviderNotFoundError(msg)
        return self._stt_providers[name]()

    # ── TTS ──

    def register_tts(self, name: str, provider_class: type[TTSProvider]) -> None:
        """Register a TTS provider class by name."""
        self._tts_providers[name] = provider_class

    def get_tts(self, name: str) -> TTSProvider:
        """Get a TTS provider instance by name."""
        if name not in self._tts_providers:
            msg = f"TTS provider '{name}' not registered. Available: {list(self._tts_providers)}"
            raise ProviderNotFoundError(msg)
        return self._tts_providers[name]()

    # ── Vision ──

    def register_vision(self, name: str, provider_class: type[VisionProvider]) -> None:
        """Register a Vision provider class by name."""
        self._vision_providers[name] = provider_class

    def get_vision(self, name: str) -> VisionProvider:
        """Get a Vision provider instance by name."""
        if name not in self._vision_providers:
            msg = f"Vision provider '{name}' not registered. Available: {list(self._vision_providers)}"
            raise ProviderNotFoundError(msg)
        return self._vision_providers[name]()

    # ── Fallback ──

    def set_fallback_chain(self, chain: list[str]) -> None:
        """Set the LLM fallback chain for automatic failover.

        Args:
            chain: Ordered list of provider names to try.
        """
        self._fallback_chain = chain

    async def get_llm_with_fallback(self) -> LLMProvider:
        """Get the first available LLM provider from the fallback chain.

        Iterates through the fallback chain and returns the first provider
        that passes a health check.

        Returns:
            A healthy LLMProvider instance.

        Raises:
            ProviderNotFoundError: If no providers in the chain are available.
        """
        for name in self._fallback_chain:
            try:
                provider = self.get_llm(name)
                if await provider.health_check():
                    return provider
            except (ProviderNotFoundError, ConnectionError):
                continue

        msg = f"No available LLM providers in fallback chain: {self._fallback_chain}"
        raise ProviderNotFoundError(msg)
