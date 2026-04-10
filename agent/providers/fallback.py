"""Generic FallbackChain[T] for provider failover.

Provides a type-safe, generic fallback chain that tries providers in order,
skipping circuit-broken ones, and logging each failover via structlog.

Integrates with Phase 3 resilience primitives (CircuitBreaker, HealthCache).

Usage::

    chain = FallbackChain[LLMProvider](
        providers=[("groq", groq_instance), ("ollama", ollama_instance)],
        health_cache=registry.health_cache,
    )
    result = await chain.execute(lambda p: p.chat(messages))
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Generic, TypeVar

from core.errors import ErrorSeverity, ProviderError
from core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from providers.resilience import HealthCache

logger = get_logger(module="providers.fallback")

# -- Constants --

FALLBACK_TOTAL_BUDGET_SECONDS = 4.0
FALLBACK_PER_PROVIDER_TIMEOUT_SECONDS = 2.5

T = TypeVar("T")
R = TypeVar("R")


@dataclass(frozen=True)
class FallbackResult(Generic[R]):
    """Result of a fallback chain execution.

    Attributes:
        value: The successful result value.
        provider_name: Name of the provider that succeeded.
        attempts: Number of providers attempted before success.
        total_latency_ms: Total time spent across all attempts.
    """

    value: R
    provider_name: str
    attempts: int
    total_latency_ms: int


class AllProvidersExhaustedError(ProviderError):
    """Raised when all providers in a fallback chain have failed."""

    def __init__(self, chain_type: str, providers_tried: list[str]) -> None:
        super().__init__(
            f"All {chain_type} providers exhausted: {providers_tried}",
            provider_name=chain_type,
            severity=ErrorSeverity.CRITICAL,
            user_message="Tat ca nha cung cap deu khong kha dung.",
            retryable=False,
        )
        self.providers_tried = providers_tried


@dataclass
class FallbackChain(Generic[T]):
    """Generic async fallback chain for any provider type.

    Tries each provider in order. Skips providers whose health cache
    entry is ``False``. Enforces a total latency budget across all attempts.

    Attributes:
        providers: Ordered list of (name, instance) tuples.
        chain_type: Human label for logging (e.g., "LLM", "TTS", "STT").
        health_cache: Optional health cache to skip known-unhealthy providers.
        total_budget_s: Maximum total seconds for the entire chain.
        per_provider_timeout_s: Timeout per individual provider call.
    """

    providers: list[tuple[str, T]]
    chain_type: str = "provider"
    health_cache: HealthCache | None = None
    total_budget_s: float = FALLBACK_TOTAL_BUDGET_SECONDS
    per_provider_timeout_s: float = FALLBACK_PER_PROVIDER_TIMEOUT_SECONDS
    _on_failover: Callable[[str, str, str], Awaitable[None]] | None = field(
        default=None, repr=False
    )

    @property
    def provider_names(self) -> list[str]:
        """Return the ordered list of provider names in this chain."""
        return [name for name, _ in self.providers]

    def on_failover(
        self, callback: Callable[[str, str, str], Awaitable[None]]
    ) -> None:
        """Register a callback for failover events.

        The callback receives (chain_type, failed_provider, next_provider).

        Args:
            callback: Async callable invoked on each failover.
        """
        self._on_failover = callback

    async def execute(
        self, operation: Callable[[T], Awaitable[R]]
    ) -> FallbackResult[R]:
        """Execute an operation against the chain, failing over on errors.

        Tries each provider in order. Skips circuit-broken or cached-unhealthy
        providers. Enforces total and per-provider timeouts.

        Args:
            operation: Async callable that takes a provider and returns a result.

        Returns:
            FallbackResult with the value from the first successful provider.

        Raises:
            AllProvidersExhaustedError: If every provider fails or times out.
        """
        t0 = time.monotonic()
        errors: list[tuple[str, str]] = []
        providers_tried: list[str] = []

        for idx, (name, provider) in enumerate(self.providers):
            # Check total budget
            elapsed = time.monotonic() - t0
            if elapsed >= self.total_budget_s:
                logger.warning(
                    "fallback chain budget exhausted",
                    chain_type=self.chain_type,
                    elapsed_s=round(elapsed, 2),
                    budget_s=self.total_budget_s,
                )
                break

            # Skip cached-unhealthy providers
            if self._is_cached_unhealthy(name):
                logger.debug(
                    "skipping cached-unhealthy provider",
                    chain_type=self.chain_type,
                    provider=name,
                )
                continue

            providers_tried.append(name)
            remaining_budget = self.total_budget_s - (time.monotonic() - t0)
            timeout = min(self.per_provider_timeout_s, remaining_budget)

            try:
                result = await asyncio.wait_for(
                    operation(provider), timeout=max(timeout, 0.1)
                )
                self._mark_healthy(name)
                latency_ms = int((time.monotonic() - t0) * 1000)

                if providers_tried and len(providers_tried) > 1:
                    logger.info(
                        "fallback chain succeeded after failover",
                        chain_type=self.chain_type,
                        provider=name,
                        attempts=len(providers_tried),
                        latency_ms=latency_ms,
                    )

                return FallbackResult(
                    value=result,
                    provider_name=name,
                    attempts=len(providers_tried),
                    total_latency_ms=latency_ms,
                )

            except asyncio.TimeoutError:
                error_msg = f"timeout after {timeout:.1f}s"
                errors.append((name, error_msg))
                self._mark_unhealthy(name)
                logger.warning(
                    "provider timed out",
                    chain_type=self.chain_type,
                    provider=name,
                    timeout_s=round(timeout, 1),
                )

            except Exception as exc:
                error_msg = str(exc)
                errors.append((name, error_msg))
                self._mark_unhealthy(name)
                logger.warning(
                    "provider failed",
                    chain_type=self.chain_type,
                    provider=name,
                    error=error_msg,
                )

            # Notify failover callback
            await self._notify_failover(name, idx)

        raise AllProvidersExhaustedError(self.chain_type, providers_tried)

    async def _notify_failover(self, failed_name: str, failed_idx: int) -> None:
        """Fire the failover callback if there is a next provider."""
        if self._on_failover is None:
            return

        next_name = self._find_next_available(failed_idx + 1)
        if next_name is None:
            return

        try:
            await self._on_failover(self.chain_type, failed_name, next_name)
        except Exception:
            logger.debug("failover callback error", chain_type=self.chain_type)

    def _find_next_available(self, start_idx: int) -> str | None:
        """Find the next non-cached-unhealthy provider name from start_idx."""
        for idx in range(start_idx, len(self.providers)):
            name, _ = self.providers[idx]
            if not self._is_cached_unhealthy(name):
                return name
        return None

    def _is_cached_unhealthy(self, name: str) -> bool:
        """Check if the health cache says this provider is unhealthy."""
        if self.health_cache is None:
            return False
        cached = self.health_cache.get(name)
        return cached is False

    def _mark_healthy(self, name: str) -> None:
        """Update health cache to mark provider as healthy."""
        if self.health_cache is not None:
            self.health_cache.set(name, healthy=True)

    def _mark_unhealthy(self, name: str) -> None:
        """Update health cache to mark provider as unhealthy."""
        if self.health_cache is not None:
            self.health_cache.set(name, healthy=False)
