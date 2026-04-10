"""Tests for provider resilience: retry, circuit breaker, health cache, shared client.

Covers PROV-04 (circuit breaker), PROV-05 (retry with backoff),
PROV-06 (shared httpx client), PROV-07 (health cache with TTL).
"""

from __future__ import annotations

import time

import httpx
import pytest

from providers.base import (
    LLMProvider,
    Message,
    ModelInfo,
    STTProvider,
    TranscribeResult,
)
from providers.registry import ProviderNotFoundError, ProviderRegistry
from providers.resilience import (
    DEFAULT_BACKOFF_BASE_SECONDS,
    DEFAULT_CIRCUIT_FAIL_MAX,
    DEFAULT_MAX_ATTEMPTS,
    CircuitBreakerConfig,
    HealthCache,
    RetryConfig,
    _is_retryable_http_error,
    create_circuit_breaker,
    with_retry,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


class FakeLLM(LLMProvider):
    """Minimal LLM provider for testing shared client lifecycle."""

    def __init__(self, *, healthy: bool = True) -> None:
        self._healthy = healthy

    async def chat(self, messages: list[Message], **kwargs: object) -> str:
        return "ok"

    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict[str, object]],
        **kwargs: object,
    ) -> dict[str, object]:
        return {"tool": "", "result": "ok"}

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(name="fake", provider="test")

    async def health_check(self) -> bool:
        return self._healthy


class FakeSTT(STTProvider):
    """Minimal STT provider for testing shared client lifecycle."""

    async def transcribe(
        self, audio: bytes, language: str = "vi", task: str = "transcribe"
    ) -> TranscribeResult:
        return TranscribeResult(text="hello", confidence=0.9, language=language, duration_ms=100)


# ── PROV-06: Shared httpx client tests ─────────────────────────────────────────


class TestHttpProviderSharedClient:
    """Verify that HttpProvider creates exactly one client and reuses it."""

    @pytest.mark.asyncio
    async def test_client_created_lazily(self) -> None:
        """Client should not exist until first access."""
        provider = FakeLLM()
        assert provider._http_client is None

    @pytest.mark.asyncio
    async def test_client_reused_across_accesses(self) -> None:
        """Same client instance returned on repeated property access."""
        provider = FakeLLM()
        client_a = provider.http_client
        client_b = provider.http_client
        assert client_a is client_b
        await provider.close()

    @pytest.mark.asyncio
    async def test_client_has_connection_pool_limits(self) -> None:
        """Client should be configured with connection pooling."""
        provider = FakeLLM()
        client = provider.http_client
        pool = client._transport._pool  # type: ignore[attr-defined]
        assert pool._max_connections == 10
        assert pool._max_keepalive_connections == 5
        await provider.close()

    @pytest.mark.asyncio
    async def test_close_releases_client(self) -> None:
        """After close(), the client should be None."""
        provider = FakeLLM()
        _ = provider.http_client
        assert provider._http_client is not None
        await provider.close()
        assert provider._http_client is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self) -> None:
        """Calling close() multiple times should not raise."""
        provider = FakeLLM()
        _ = provider.http_client
        await provider.close()
        await provider.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_client_recreated_after_close(self) -> None:
        """Accessing http_client after close should create a new one."""
        provider = FakeLLM()
        first = provider.http_client
        await provider.close()
        second = provider.http_client
        assert first is not second
        await provider.close()

    @pytest.mark.asyncio
    async def test_stt_provider_inherits_http_client(self) -> None:
        """STTProvider also gets shared http_client from mixin."""
        provider = FakeSTT()
        client = provider.http_client
        assert isinstance(client, httpx.AsyncClient)
        await provider.close()


# ── PROV-05: Retry with exponential backoff ────────────────────────────────────


class TestRetryConfig:
    """Verify retry configuration defaults and customisation."""

    def test_default_config(self) -> None:
        """Default config should have 3 attempts and sensible backoff."""
        cfg = RetryConfig()
        assert cfg.max_attempts == DEFAULT_MAX_ATTEMPTS
        assert cfg.backoff_base == DEFAULT_BACKOFF_BASE_SECONDS
        assert 429 in cfg.retryable_statuses
        assert 502 in cfg.retryable_statuses
        assert 503 in cfg.retryable_statuses

    def test_custom_config(self) -> None:
        """Custom config values should override defaults."""
        cfg = RetryConfig(max_attempts=5, backoff_base=1.0, backoff_max=30.0)
        assert cfg.max_attempts == 5
        assert cfg.backoff_base == 1.0
        assert cfg.backoff_max == 30.0


class TestIsRetryableHttpError:
    """Verify that the retryable error predicate classifies correctly."""

    def test_429_is_retryable(self) -> None:
        """Rate limit (429) should be retryable."""
        request = httpx.Request("POST", "https://api.example.com")
        response = httpx.Response(429, request=request)
        exc = httpx.HTTPStatusError("rate limit", request=request, response=response)
        assert _is_retryable_http_error(exc) is True

    def test_502_is_retryable(self) -> None:
        """Bad gateway (502) should be retryable."""
        request = httpx.Request("POST", "https://api.example.com")
        response = httpx.Response(502, request=request)
        exc = httpx.HTTPStatusError("bad gateway", request=request, response=response)
        assert _is_retryable_http_error(exc) is True

    def test_503_is_retryable(self) -> None:
        """Service unavailable (503) should be retryable."""
        request = httpx.Request("POST", "https://api.example.com")
        response = httpx.Response(503, request=request)
        exc = httpx.HTTPStatusError("unavailable", request=request, response=response)
        assert _is_retryable_http_error(exc) is True

    def test_400_is_not_retryable(self) -> None:
        """Client error (400) should NOT be retryable."""
        request = httpx.Request("POST", "https://api.example.com")
        response = httpx.Response(400, request=request)
        exc = httpx.HTTPStatusError("bad request", request=request, response=response)
        assert _is_retryable_http_error(exc) is False

    def test_401_is_not_retryable(self) -> None:
        """Auth error (401) should NOT be retryable."""
        request = httpx.Request("POST", "https://api.example.com")
        response = httpx.Response(401, request=request)
        exc = httpx.HTTPStatusError("unauthorized", request=request, response=response)
        assert _is_retryable_http_error(exc) is False

    def test_connect_error_is_retryable(self) -> None:
        """Connection errors should be retryable."""
        exc = httpx.ConnectError("connection refused")
        assert _is_retryable_http_error(exc) is True

    def test_read_timeout_is_retryable(self) -> None:
        """Read timeouts should be retryable."""
        exc = httpx.ReadTimeout("timed out")
        assert _is_retryable_http_error(exc) is True

    def test_non_http_error_is_not_retryable(self) -> None:
        """Non-HTTP exceptions should NOT be retryable."""
        exc = ValueError("not an http error")
        assert _is_retryable_http_error(exc) is False


class TestWithRetryDecorator:
    """Verify that with_retry() actually retries on transient failures."""

    @pytest.mark.asyncio
    async def test_retries_on_503_then_succeeds(self) -> None:
        """Function should retry on 503 and eventually succeed."""
        call_count = 0

        @with_retry(RetryConfig(max_attempts=3, backoff_base=0.01, backoff_max=0.05))
        async def flaky_call() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                request = httpx.Request("POST", "https://api.example.com")
                response = httpx.Response(503, request=request)
                raise httpx.HTTPStatusError("unavailable", request=request, response=response)
            return "success"

        result = await flaky_call()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self) -> None:
        """Should raise the last error after exhausting retries."""

        @with_retry(RetryConfig(max_attempts=2, backoff_base=0.01, backoff_max=0.02))
        async def always_fails() -> str:
            request = httpx.Request("POST", "https://api.example.com")
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError("unavailable", request=request, response=response)

        with pytest.raises(httpx.HTTPStatusError):
            await always_fails()

    @pytest.mark.asyncio
    async def test_no_retry_on_400(self) -> None:
        """Should NOT retry on non-transient errors (400)."""
        call_count = 0

        @with_retry(RetryConfig(max_attempts=3, backoff_base=0.01))
        async def client_error() -> str:
            nonlocal call_count
            call_count += 1
            request = httpx.Request("POST", "https://api.example.com")
            response = httpx.Response(400, request=request)
            raise httpx.HTTPStatusError("bad request", request=request, response=response)

        with pytest.raises(httpx.HTTPStatusError):
            await client_error()
        assert call_count == 1  # No retries


# ── PROV-04: Circuit breaker ──────────────────────────────────────────────────


class TestCircuitBreakerConfig:
    """Verify circuit breaker configuration."""

    def test_default_config(self) -> None:
        """Default config should have 5 failures and 60s reset."""
        cfg = CircuitBreakerConfig()
        assert cfg.fail_max == DEFAULT_CIRCUIT_FAIL_MAX
        assert cfg.reset_timeout == 60.0

    def test_custom_config(self) -> None:
        """Custom config values should override defaults."""
        cfg = CircuitBreakerConfig(fail_max=3, reset_timeout=30.0)
        assert cfg.fail_max == 3
        assert cfg.reset_timeout == 30.0


class TestCircuitBreaker:
    """Verify circuit breaker creation and state transitions."""

    def test_create_returns_breaker(self) -> None:
        """create_circuit_breaker should return a CircuitBreaker instance."""
        from aiobreaker import CircuitBreaker

        cb = create_circuit_breaker("test-provider")
        assert isinstance(cb, CircuitBreaker)
        assert cb.name == "test-provider"

    def test_create_with_custom_config(self) -> None:
        """Custom config should be applied to the breaker."""
        cfg = CircuitBreakerConfig(fail_max=2, reset_timeout=10.0)
        cb = create_circuit_breaker("custom-test", config=cfg)
        assert cb.fail_max == 2

    @pytest.mark.asyncio
    async def test_opens_after_n_failures(self) -> None:
        """Circuit should open after fail_max consecutive failures."""
        from aiobreaker import CircuitBreakerError

        cfg = CircuitBreakerConfig(fail_max=3, reset_timeout=60.0)
        cb = create_circuit_breaker("fail-test", config=cfg)

        async def failing_call() -> None:
            raise ConnectionError("server down")

        # Fail until circuit opens — aiobreaker raises CircuitBreakerError
        # on the failure that triggers the threshold.
        errors_seen = 0
        for _ in range(5):
            try:
                await cb.call_async(failing_call)
            except CircuitBreakerError:
                # Circuit is open — this is the expected path after threshold
                break
            except ConnectionError:
                errors_seen += 1

        # Should have seen some failures before the breaker opened
        assert errors_seen >= 2

        # Subsequent calls should fail-fast with CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            await cb.call_async(failing_call)

    @pytest.mark.asyncio
    async def test_succeeds_when_closed(self) -> None:
        """Calls should pass through when circuit is closed."""
        cb = create_circuit_breaker("success-test")

        async def ok_call() -> str:
            return "healthy"

        result = await cb.call_async(ok_call)
        assert result == "healthy"


# ── PROV-07: Health cache with TTL ────────────────────────────────────────────


class TestHealthCache:
    """Verify TTL-based health state caching."""

    def test_get_unknown_returns_none(self) -> None:
        """Unknown providers should return None (cache miss)."""
        cache = HealthCache()
        assert cache.get("nonexistent") is None

    def test_set_and_get_healthy(self) -> None:
        """Setting healthy=True should be retrievable."""
        cache = HealthCache()
        cache.set("openai", True)
        assert cache.get("openai") is True

    def test_set_and_get_unhealthy(self) -> None:
        """Setting healthy=False should be retrievable."""
        cache = HealthCache()
        cache.set("openai", False)
        assert cache.get("openai") is False

    def test_expired_entry_returns_none(self) -> None:
        """Entries older than TTL should return None (stale)."""
        cache = HealthCache(ttl=0.01)  # 10ms TTL
        cache.set("openai", True)
        time.sleep(0.02)
        assert cache.get("openai") is None

    def test_fresh_entry_not_stale(self) -> None:
        """Fresh entries should not be considered stale."""
        cache = HealthCache(ttl=60.0)
        cache.set("openai", True)
        assert cache.is_stale("openai") is False

    def test_missing_entry_is_stale(self) -> None:
        """Missing entries should be stale."""
        cache = HealthCache()
        assert cache.is_stale("missing") is True

    def test_invalidate_specific_provider(self) -> None:
        """Invalidating a provider should make its entry stale."""
        cache = HealthCache()
        cache.set("openai", True)
        cache.set("groq", True)
        cache.invalidate("openai")
        assert cache.get("openai") is None
        assert cache.get("groq") is True

    def test_invalidate_all(self) -> None:
        """Invalidating all should clear the entire cache."""
        cache = HealthCache()
        cache.set("openai", True)
        cache.set("groq", True)
        cache.invalidate_all()
        assert cache.get("openai") is None
        assert cache.get("groq") is None


# ── Registry integration: cached health in fallback ──────────────────────────


class TestRegistryHealthCacheFallback:
    """Verify that get_llm_with_fallback() uses cached health, not live checks."""

    @pytest.mark.asyncio
    async def test_uses_cached_healthy_provider(self) -> None:
        """Should return provider without calling health_check if cache says healthy."""
        registry = ProviderRegistry()
        registry.register_llm("fast", FakeLLM)
        registry.set_fallback_chain(["fast"])

        # Pre-populate cache
        registry.health_cache.set("fast", True)

        provider = await registry.get_llm_with_fallback()
        assert isinstance(provider, FakeLLM)

    @pytest.mark.asyncio
    async def test_skips_cached_unhealthy_provider(self) -> None:
        """Should skip providers that cache says are unhealthy."""
        registry = ProviderRegistry()

        class HealthyLLM(FakeLLM):
            """Subclass to differentiate in assertion."""

        registry.register_llm("broken", type("BrokenLLM", (FakeLLM,), {}))
        registry.register_llm("healthy", HealthyLLM)
        registry.set_fallback_chain(["broken", "healthy"])

        # Mark broken as unhealthy, healthy as healthy
        registry.health_cache.set("broken", False)
        registry.health_cache.set("healthy", True)

        provider = await registry.get_llm_with_fallback()
        assert isinstance(provider, HealthyLLM)

    @pytest.mark.asyncio
    async def test_live_check_when_cache_stale(self) -> None:
        """Should do live health check when cache is stale."""
        registry = ProviderRegistry()
        registry.register_llm("stale", FakeLLM)
        registry.set_fallback_chain(["stale"])

        # No cache entry -- should trigger live check
        provider = await registry.get_llm_with_fallback()
        assert isinstance(provider, FakeLLM)
        # After live check, cache should be populated
        assert registry.health_cache.get("stale") is True

    @pytest.mark.asyncio
    async def test_raises_when_all_providers_unhealthy(self) -> None:
        """Should raise ProviderNotFoundError when all fail."""
        registry = ProviderRegistry()
        registry.register_llm("bad", lambda: FakeLLM(healthy=False))
        registry.set_fallback_chain(["bad"])

        # Cache says unhealthy
        registry.health_cache.set("bad", False)

        with pytest.raises(ProviderNotFoundError):
            await registry.get_llm_with_fallback()

    @pytest.mark.asyncio
    async def test_zero_health_checks_when_cache_warm(self) -> None:
        """No health_check() calls should happen when cache is warm."""
        registry = ProviderRegistry()

        health_check_calls = 0
        original_health = FakeLLM.health_check

        async def counting_health(self_inner: FakeLLM) -> bool:
            nonlocal health_check_calls
            health_check_calls += 1
            return await original_health(self_inner)

        # Monkey-patch to count calls
        FakeLLM.health_check = counting_health  # type: ignore[assignment]
        try:
            registry.register_llm("cached", FakeLLM)
            registry.set_fallback_chain(["cached"])
            registry.health_cache.set("cached", True)

            await registry.get_llm_with_fallback()
            assert health_check_calls == 0, "health_check should not be called when cache is warm"
        finally:
            FakeLLM.health_check = original_health  # type: ignore[assignment]


class TestRegistryCloseAll:
    """Verify that close_all() cleans up all provider HTTP clients."""

    @pytest.mark.asyncio
    async def test_close_all_closes_clients(self) -> None:
        """close_all() should close all instantiated provider clients."""
        registry = ProviderRegistry()
        registry.register_llm("a", FakeLLM)
        registry.register_stt("b", FakeSTT)

        # Force instantiation
        llm = registry.get_llm("a")
        stt = registry.get_stt("b")

        # Access clients to create them
        _ = llm.http_client
        _ = stt.http_client

        assert llm._http_client is not None
        assert stt._http_client is not None

        await registry.close_all()

        assert llm._http_client is None
        assert stt._http_client is None

    @pytest.mark.asyncio
    async def test_close_all_idempotent(self) -> None:
        """Calling close_all() multiple times should not raise."""
        registry = ProviderRegistry()
        registry.register_llm("a", FakeLLM)
        _ = registry.get_llm("a")

        await registry.close_all()
        await registry.close_all()  # Should not raise


class TestRegistryRefreshHealth:
    """Verify that refresh_health() updates the cache."""

    @pytest.mark.asyncio
    async def test_refresh_healthy_provider(self) -> None:
        """refresh_health() should set cache to True for healthy providers."""
        registry = ProviderRegistry()
        registry.register_llm("good", FakeLLM)

        result = await registry.refresh_health("good")
        assert result is True
        assert registry.health_cache.get("good") is True

    @pytest.mark.asyncio
    async def test_refresh_unhealthy_provider(self) -> None:
        """refresh_health() should set cache to False for unhealthy providers."""
        registry = ProviderRegistry()
        registry.register_llm("bad", lambda: FakeLLM(healthy=False))

        result = await registry.refresh_health("bad")
        assert result is False
        assert registry.health_cache.get("bad") is False

    @pytest.mark.asyncio
    async def test_refresh_unknown_provider(self) -> None:
        """refresh_health() should return False for unknown providers."""
        registry = ProviderRegistry()

        result = await registry.refresh_health("nonexistent")
        assert result is False
        assert registry.health_cache.get("nonexistent") is False
