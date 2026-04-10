# Phase 3: Provider Connection Infrastructure -- Summary

**Completed:** 2026-04-10
**Requirements:** PROV-04, PROV-05, PROV-06, PROV-07

---

## What Was Built

### PROV-06: Shared httpx Client per Provider (Connection Pooling)

- Added `HttpProvider` mixin to `providers/base.py` with lazy-init `http_client` property
- All provider ABCs (`LLMProvider`, `STTProvider`, `TTSProvider`, `VisionProvider`) inherit from `HttpProvider`
- Each provider creates exactly **one** `httpx.AsyncClient` on first use and reuses it across all requests
- Connection pool configured: `max_connections=10`, `max_keepalive_connections=5`
- Explicit `async close()` method for clean shutdown
- Client auto-recreates if accessed after close (resilient to restarts)

**Providers updated:** OpenAI, Groq, Anthropic, Ollama, DeepSeek, Mistral, OpenRouter, OpenAI Whisper STT, ElevenLabs TTS, OpenAI Vision, Anthropic Vision, Gemini Vision (12 providers total)

### PROV-05: Retry with Exponential Backoff (tenacity)

- `RetryConfig` dataclass: max_attempts (3), backoff_base (0.5s), backoff_max (10s)
- `with_retry()` decorator wraps async provider methods
- Retries only on transient HTTP failures: 429, 502, 503, 504, connection errors, read timeouts
- Does NOT retry on client errors (400, 401, 403, 404) -- prevents wasted API calls
- Each retry attempt logged via structlog with attempt number and error

### PROV-04: Circuit Breaker per Provider

- `CircuitBreakerConfig` dataclass: fail_max (5), reset_timeout (60s)
- `create_circuit_breaker()` factory creates named aiobreaker instances
- Standard three-state machine: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
- After N consecutive failures, circuit opens and subsequent calls fail-fast (zero network I/O)
- All state transitions logged via structlog with provider name
- `timedelta`-based timeout (fixes aiobreaker float bug)

### PROV-07: Health Cache with TTL

- `HealthCache` with configurable TTL (30s cloud, 300s local)
- `get()` returns cached healthy/unhealthy or `None` (stale/missing)
- `set()`, `invalidate()`, `invalidate_all()` for cache management
- `is_stale()` convenience method
- Registry's `get_llm_with_fallback()` reads cached state **only** -- zero health-check HTTP calls in the hot path
- Live health check triggered only when cache entry is stale or missing
- `refresh_health()` method for background scheduler use

### Registry Lifecycle

- `ProviderRegistry.close_all()` closes all provider HTTP clients on shutdown
- `health_cache` property exposed for external health refresh tasks
- `refresh_health()` runs live check and updates cache in one call

---

## Files Changed

| File | Change |
|------|--------|
| `providers/base.py` | Added `HttpProvider` mixin with shared client lifecycle |
| `providers/resilience.py` | Fixed `timedelta` for circuit breaker, cleaned state logger |
| `providers/registry.py` | Added `HealthCache` integration, `close_all()`, `refresh_health()` |
| `providers/openai_provider.py` | Switched to `self.http_client` (shared) |
| `providers/groq_provider.py` | Switched to `self.http_client` (shared) |
| `providers/anthropic_provider.py` | Switched to `self.http_client` with custom timeout |
| `providers/ollama_provider.py` | Switched to `self.http_client` with custom timeout |
| `providers/deepseek_provider.py` | Switched to `self.http_client` (shared) |
| `providers/mistral_provider.py` | Switched to `self.http_client` (shared) |
| `providers/openrouter_provider.py` | Switched to `self.http_client` (shared) |
| `providers/stt/openai_whisper.py` | Switched to `self.http_client`, structlog |
| `providers/tts/elevenlabs_clone.py` | Switched to `self.http_client`, structlog |
| `providers/vision/openai_vision.py` | Switched to `self.http_client`, structlog |
| `providers/vision/anthropic_vision.py` | Switched to `self.http_client`, structlog |
| `providers/vision/gemini_vision.py` | Switched to `self.http_client`, structlog |
| `tests/test_resilience.py` | 44 new tests covering all 4 requirements |

---

## Test Results

```
44 passed, 2 warnings in 1.98s
```

| Test Class | Count | Covers |
|------------|-------|--------|
| `TestHttpProviderSharedClient` | 7 | PROV-06 |
| `TestRetryConfig` | 2 | PROV-05 |
| `TestIsRetryableHttpError` | 8 | PROV-05 |
| `TestWithRetryDecorator` | 3 | PROV-05 |
| `TestCircuitBreakerConfig` | 2 | PROV-04 |
| `TestCircuitBreaker` | 4 | PROV-04 |
| `TestHealthCache` | 8 | PROV-07 |
| `TestRegistryHealthCacheFallback` | 5 | PROV-07 |
| `TestRegistryCloseAll` | 2 | PROV-06 |
| `TestRegistryRefreshHealth` | 3 | PROV-07 |

---

## Success Criteria Verification

1. **Each provider creates exactly one httpx.AsyncClient at init and reuses it** -- Verified: `test_client_reused_across_accesses`, `test_client_has_connection_pool_limits`
2. **Transient HTTP failures trigger automatic retry with exponential backoff -- max 3 attempts** -- Verified: `test_retries_on_503_then_succeeds`, `test_raises_after_max_attempts`, `test_no_retry_on_400`
3. **After N consecutive failures, circuit breaker opens and subsequent calls fail-fast** -- Verified: `test_opens_after_n_failures`
4. **Health check results cached with TTL -- zero health-check HTTP calls during normal request flow** -- Verified: `test_zero_health_checks_when_cache_warm`, `test_uses_cached_healthy_provider`
5. **All circuit breaker state transitions logged via structlog** -- Verified: structlog output in test captures shows state change logging

---

## Pitfalls Addressed

- **P3 (Health checks in hot path):** `get_llm_with_fallback()` now reads cached state only. Live checks only on cache miss.
- **P4.5 (httpx client lifecycle):** Lazy init, explicit close, connection pooling with limits. No `ResourceWarning` on shutdown.
- **P4.3 (Retry non-idempotent ops):** Retry predicate only matches transient HTTP errors. Non-transient errors (400-level) pass through immediately.
