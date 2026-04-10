"""Provider registry with fallback chain support and health caching.

Core modules access providers exclusively through this registry.
Direct imports of provider implementations are prohibited.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.errors import ErrorSeverity, ProviderError
from core.logging import get_logger
from providers.resilience import HealthCache

if TYPE_CHECKING:
    from providers.base import (
        HttpProvider,
        LLMProvider,
        STTProvider,
        TTSProvider,
        VisionProvider,
    )
    from providers.fallback import FallbackChain


class ProviderNotFoundError(ProviderError, KeyError):
    """Raised when a requested provider is not registered."""

    def __init__(self, msg: str) -> None:
        ProviderError.__init__(
            self,
            msg,
            provider_name="",
            severity=ErrorSeverity.WARNING,
            user_message="Khong tim thay nha cung cap.",
            retryable=False,
        )


logger = get_logger(module="providers.registry")


class ProviderRegistry:
    """Factory for creating and managing provider instances.

    All provider types (LLM, STT, TTS, Vision) are registered by name
    and instantiated on demand. Supports a fallback chain for automatic
    failover when a provider is unavailable.

    Uses ``HealthCache`` to avoid health-check HTTP calls in the hot path.
    """

    def __init__(self) -> None:
        """Initialize an empty registry with health cache."""
        self._llm_providers: dict[str, type[LLMProvider]] = {}
        self._stt_providers: dict[str, type[STTProvider]] = {}
        self._tts_providers: dict[str, type[TTSProvider]] = {}
        self._vision_providers: dict[str, type[VisionProvider]] = {}
        self._fallback_chain: list[str] = []
        # Instance caches to avoid repeated keyring lookups
        self._llm_instances: dict[str, LLMProvider] = {}
        self._stt_instances: dict[str, STTProvider] = {}
        self._tts_instances: dict[str, TTSProvider] = {}
        self._vision_instances: dict[str, VisionProvider] = {}
        # Health cache — prevents health checks in the hot path
        self._health_cache = HealthCache()

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
        if name not in self._llm_instances:
            self._llm_instances[name] = self._llm_providers[name]()
        return self._llm_instances[name]

    # ── STT ──

    def register_stt(self, name: str, provider_class: type[STTProvider]) -> None:
        """Register an STT provider class by name."""
        self._stt_providers[name] = provider_class

    def get_stt(self, name: str) -> STTProvider:
        """Get an STT provider instance by name."""
        if name not in self._stt_providers:
            msg = f"STT provider '{name}' not registered. Available: {list(self._stt_providers)}"
            raise ProviderNotFoundError(msg)
        if name not in self._stt_instances:
            self._stt_instances[name] = self._stt_providers[name]()
        return self._stt_instances[name]

    # ── TTS ──

    def register_tts(self, name: str, provider_class: type[TTSProvider]) -> None:
        """Register a TTS provider class by name."""
        self._tts_providers[name] = provider_class

    def get_tts(self, name: str) -> TTSProvider:
        """Get a TTS provider instance by name."""
        if name not in self._tts_providers:
            msg = f"TTS provider '{name}' not registered. Available: {list(self._tts_providers)}"
            raise ProviderNotFoundError(msg)
        if name not in self._tts_instances:
            self._tts_instances[name] = self._tts_providers[name]()
        return self._tts_instances[name]

    # ── Vision ──

    def register_vision(self, name: str, provider_class: type[VisionProvider]) -> None:
        """Register a Vision provider class by name."""
        self._vision_providers[name] = provider_class

    def get_vision(self, name: str) -> VisionProvider:
        """Get a Vision provider instance by name."""
        if name not in self._vision_providers:
            msg = f"Vision provider '{name}' not registered. Available: {list(self._vision_providers)}"
            raise ProviderNotFoundError(msg)
        if name not in self._vision_instances:
            self._vision_instances[name] = self._vision_providers[name]()
        return self._vision_instances[name]

    # ── Introspection ──

    def list_registered(self) -> dict[str, list[str]]:
        """List all registered provider names by type.

        Returns:
            Dict with keys 'llm', 'stt', 'tts', 'vision' mapping to name lists.
        """
        return {
            "llm": list(self._llm_providers.keys()),
            "stt": list(self._stt_providers.keys()),
            "tts": list(self._tts_providers.keys()),
            "vision": list(self._vision_providers.keys()),
        }

    # ── Health Cache ──

    @property
    def health_cache(self) -> HealthCache:
        """Access the health cache for external refresh tasks.

        Returns:
            The shared HealthCache instance.
        """
        return self._health_cache

    async def refresh_health(self, name: str) -> bool:
        """Run a live health check and update the cache.

        Args:
            name: Provider name to check.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            provider = self.get_llm(name)
            healthy = await provider.health_check()
        except (ProviderNotFoundError, Exception):
            healthy = False

        self._health_cache.set(name, healthy)
        logger.debug("health check refreshed", provider=name, healthy=healthy)
        return healthy

    # ── Fallback ──

    def set_fallback_chain(self, chain: list[str]) -> None:
        """Set the LLM fallback chain for automatic failover.

        Args:
            chain: Ordered list of provider names to try.
        """
        self._fallback_chain = chain

    async def get_llm_with_fallback(self) -> LLMProvider:
        """Get the first available LLM provider from the fallback chain.

        Uses cached health state to avoid HTTP calls in the hot path.
        Falls back to a live health check only when the cache is stale.

        Returns:
            A healthy LLMProvider instance.

        Raises:
            ProviderNotFoundError: If no providers in the chain are available.
        """
        for name in self._fallback_chain:
            try:
                provider = self.get_llm(name)
            except ProviderNotFoundError:
                continue

            # Check cached health first — zero network I/O
            cached = self._health_cache.get(name)
            if cached is True:
                logger.debug("using cached healthy provider", provider=name)
                return provider
            if cached is False:
                logger.debug("skipping cached unhealthy provider", provider=name)
                continue

            # Cache is stale or missing — do a live check
            logger.info("health cache stale, checking live", provider=name)
            healthy = await provider.health_check()
            self._health_cache.set(name, healthy)
            if healthy:
                return provider

        msg = f"No available LLM providers in fallback chain: {self._fallback_chain}"
        raise ProviderNotFoundError(msg)

    # ── Fallback Chain Factories ──

    def create_llm_fallback_chain(
        self, provider_names: list[str] | None = None
    ) -> FallbackChain[LLMProvider]:
        """Create a FallbackChain for LLM providers.

        Args:
            provider_names: Ordered list of provider names. Defaults to
                the configured fallback chain.

        Returns:
            A FallbackChain[LLMProvider] ready for use.
        """
        from providers.fallback import FallbackChain

        names = provider_names or self._fallback_chain
        providers: list[tuple[str, LLMProvider]] = []
        for name in names:
            try:
                providers.append((name, self.get_llm(name)))
            except ProviderNotFoundError:
                logger.debug("skipping unregistered LLM for chain", provider=name)
        return FallbackChain(
            providers=providers,
            chain_type="LLM",
            health_cache=self._health_cache,
        )

    def create_stt_fallback_chain(
        self, provider_names: list[str] | None = None
    ) -> FallbackChain[STTProvider]:
        """Create a FallbackChain for STT providers.

        Args:
            provider_names: Ordered list of provider names.

        Returns:
            A FallbackChain[STTProvider] ready for use.
        """
        from providers.fallback import FallbackChain

        names = provider_names or list(self._stt_providers.keys())
        providers: list[tuple[str, STTProvider]] = []
        for name in names:
            try:
                providers.append((name, self.get_stt(name)))
            except ProviderNotFoundError:
                logger.debug("skipping unregistered STT for chain", provider=name)
        return FallbackChain(
            providers=providers,
            chain_type="STT",
            health_cache=self._health_cache,
        )

    def create_tts_fallback_chain(
        self, provider_names: list[str] | None = None
    ) -> FallbackChain[TTSProvider]:
        """Create a FallbackChain for TTS providers.

        Args:
            provider_names: Ordered list of provider names.

        Returns:
            A FallbackChain[TTSProvider] ready for use.
        """
        from providers.fallback import FallbackChain

        names = provider_names or list(self._tts_providers.keys())
        providers: list[tuple[str, TTSProvider]] = []
        for name in names:
            try:
                providers.append((name, self.get_tts(name)))
            except ProviderNotFoundError:
                logger.debug("skipping unregistered TTS for chain", provider=name)
        return FallbackChain(
            providers=providers,
            chain_type="TTS",
            health_cache=self._health_cache,
        )

    # ── Lifecycle ──

    async def close_all(self) -> None:
        """Close all shared HTTP clients across all provider instances.

        Should be called during application shutdown to release connection
        pools and prevent resource warnings.
        """
        all_instances: list[HttpProvider] = [
            *self._llm_instances.values(),
            *self._stt_instances.values(),
            *self._tts_instances.values(),
            *self._vision_instances.values(),
        ]
        for instance in all_instances:
            try:
                await instance.close()
            except Exception:
                logger.debug(
                    "error closing provider client",
                    provider=type(instance).__name__,
                )
        logger.info("all provider clients closed", count=len(all_instances))
