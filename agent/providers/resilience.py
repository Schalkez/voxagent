"""Provider resilience primitives: retry, circuit breaker, and health cache.

Provides building blocks for provider connection infrastructure:
- ``RetryConfig`` + ``with_retry()`` — exponential backoff via tenacity
- ``CircuitBreakerConfig`` + ``create_circuit_breaker()`` — per-provider circuit breaker
- ``HealthCache`` — TTL-based health state cache (keeps health checks off hot path)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING

import httpx
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

# ── Constants ────────────────────────────────────────────────────────────────

RETRYABLE_HTTP_STATUSES: frozenset[int] = frozenset({429, 502, 503, 504})
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_BASE_SECONDS = 0.5
DEFAULT_BACKOFF_MAX_SECONDS = 10.0
DEFAULT_CIRCUIT_FAIL_MAX = 5
DEFAULT_CIRCUIT_RESET_TIMEOUT_SECONDS = 60.0
CLOUD_HEALTH_TTL_SECONDS = 30.0
LOCAL_HEALTH_TTL_SECONDS = 300.0

logger = get_logger(module="providers.resilience")


# ── Retry ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RetryConfig:
    """Configuration for automatic retry with exponential backoff.

    Attributes:
        max_attempts: Maximum number of attempts (including the initial one).
        backoff_base: Base delay in seconds for exponential backoff.
        backoff_max: Maximum backoff delay cap in seconds.
        retryable_statuses: HTTP status codes that trigger a retry.
    """

    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    backoff_base: float = DEFAULT_BACKOFF_BASE_SECONDS
    backoff_max: float = DEFAULT_BACKOFF_MAX_SECONDS
    retryable_statuses: frozenset[int] = RETRYABLE_HTTP_STATUSES


def _is_retryable_http_error(exc: BaseException) -> bool:
    """Check whether an exception represents a transient HTTP failure.

    Args:
        exc: The exception to inspect.

    Returns:
        True if the error is retryable (429, 502, 503, 504 or connection error).
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_HTTP_STATUSES
    return isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout))


def _log_retry(retry_state: RetryCallState) -> None:
    """Log each retry attempt with structured context."""
    attempt = retry_state.attempt_number
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    logger.warning(
        "retrying provider call",
        attempt=attempt,
        error=str(exc) if exc else "unknown",
    )


def with_retry(config: RetryConfig | None = None) -> Callable:  # type: ignore[type-arg]
    """Create a tenacity retry decorator for async provider methods.

    Retries on transient HTTP failures (429, 502, 503, 504) and connection
    errors with exponential backoff.

    Args:
        config: Retry configuration. Uses defaults if None.

    Returns:
        A decorator that wraps async functions with retry logic.
    """
    cfg = config or RetryConfig()
    return retry(
        stop=stop_after_attempt(cfg.max_attempts),
        wait=wait_exponential(multiplier=cfg.backoff_base, max=cfg.backoff_max),
        retry=retry_if_exception(_is_retryable_http_error),
        before_sleep=_log_retry,
        reraise=True,
    )


# ── Circuit Breaker ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Configuration for per-provider circuit breaker.

    Attributes:
        fail_max: Consecutive failures before opening the circuit.
        reset_timeout: Seconds to wait before transitioning to half-open.
    """

    fail_max: int = DEFAULT_CIRCUIT_FAIL_MAX
    reset_timeout: float = DEFAULT_CIRCUIT_RESET_TIMEOUT_SECONDS


def create_circuit_breaker(
    name: str,
    config: CircuitBreakerConfig | None = None,
) -> object:
    """Create an aiobreaker CircuitBreaker for a named provider.

    All state transitions (closed -> open -> half-open -> closed) are
    logged via structlog.

    Args:
        name: Provider name used for logging and identification.
        config: Circuit breaker configuration. Uses defaults if None.

    Returns:
        An aiobreaker.CircuitBreaker instance.
    """
    from aiobreaker import CircuitBreaker, CircuitBreakerListener

    cfg = config or CircuitBreakerConfig()
    cb_logger = get_logger(module="providers.circuit_breaker", provider=name)

    class _StateLogger(CircuitBreakerListener):
        """Logs circuit breaker state transitions via structlog."""

        def state_change(self, cb: CircuitBreaker, old_state: object, new_state: object) -> None:
            """Log state transitions between closed/open/half-open."""
            cb_logger.warning(
                "circuit breaker state change",
                old_state=type(old_state).__name__,
                new_state=type(new_state).__name__,
            )

        def failure(self, cb: CircuitBreaker, exception: Exception) -> None:
            cb_logger.debug(
                "circuit breaker recorded failure",
                fail_count=cb.fail_counter,
                error=str(exception),
            )

        def success(self, cb: CircuitBreaker) -> None:
            cb_logger.debug("circuit breaker recorded success")

    return CircuitBreaker(
        fail_max=cfg.fail_max,
        timeout_duration=timedelta(seconds=cfg.reset_timeout),
        listeners=[_StateLogger()],
        name=name,
    )


# ── Health Cache ─────────────────────────────────────────────────────────────


@dataclass
class _HealthEntry:
    """Single cached health check result.

    Attributes:
        healthy: Whether the provider was healthy at check time.
        checked_at: Monotonic timestamp of the check.
    """

    healthy: bool
    checked_at: float


@dataclass
class HealthCache:
    """TTL-based cache for provider health status.

    Prevents health checks from running in the hot path. Background
    tasks or explicit ``refresh()`` calls populate the cache; the
    fallback selector reads cached state only.

    Attributes:
        ttl: Cache time-to-live in seconds.
    """

    ttl: float = CLOUD_HEALTH_TTL_SECONDS
    _entries: dict[str, _HealthEntry] = field(default_factory=dict, repr=False)

    def get(self, provider_name: str) -> bool | None:
        """Get cached health status for a provider.

        Args:
            provider_name: Provider identifier.

        Returns:
            True/False if cached and not expired, None if unknown or stale.
        """
        entry = self._entries.get(provider_name)
        if entry is None:
            return None
        if (time.monotonic() - entry.checked_at) > self.ttl:
            return None
        return entry.healthy

    def set(self, provider_name: str, healthy: bool) -> None:
        """Update cached health status for a provider.

        Args:
            provider_name: Provider identifier.
            healthy: Whether the provider is healthy.
        """
        self._entries[provider_name] = _HealthEntry(
            healthy=healthy,
            checked_at=time.monotonic(),
        )

    def invalidate(self, provider_name: str) -> None:
        """Remove cached health status for a provider.

        Args:
            provider_name: Provider identifier.
        """
        self._entries.pop(provider_name, None)

    def invalidate_all(self) -> None:
        """Clear all cached health entries."""
        self._entries.clear()

    def is_stale(self, provider_name: str) -> bool:
        """Check whether the cached entry is missing or expired.

        Args:
            provider_name: Provider identifier.

        Returns:
            True if entry is missing or TTL has elapsed.
        """
        return self.get(provider_name) is None
