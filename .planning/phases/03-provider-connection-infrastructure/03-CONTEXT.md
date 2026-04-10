# Phase 03: Provider Connection Infrastructure - Context

**Date:** 2026-04-09
**Phase:** 03 - Provider Connection Infrastructure
**Depends on:** Phase 01 (Error Foundation) - completed

---

## Problem Statement

Every provider creates a new `httpx.AsyncClient` per request (connection overhead). Health checks make live API calls in the hot path (`get_llm_with_fallback` calls `health_check()` which does a real request). No retry logic exists for transient HTTP failures. No circuit breaker prevents hammering a downed provider.

## Current State Analysis

### httpx Client Lifecycle (PROV-06)
- `OpenAIProvider.chat()`: `async with httpx.AsyncClient(timeout=30) as client:` per call
- `GroqProvider.chat()`: same pattern
- `AnthropicProvider.chat()`: same pattern (timeout=60)
- `OpenAIWhisperProvider.transcribe()`: same pattern
- `ElevenLabsCloneProvider.synthesize()`: same pattern
- **Impact:** New TCP connection + TLS handshake every request; no connection reuse

### Health Check Hot Path (PROV-07)
- `ProviderRegistry.get_llm_with_fallback()` calls `provider.health_check()` for EVERY request
- LLM health checks do a real `chat()` call with `max_tokens=1` (200-500ms)
- STT health check calls OpenAI `/v1/models` endpoint
- TTS health checks call Edge TTS `list_voices()` or ElevenLabs `/voices`
- **Impact:** 200-500ms latency added to every fallback lookup

### No Retry Logic (PROV-05)
- All providers raise on HTTP errors with no retry
- Transient 429/502/503 errors cause immediate failure
- **Impact:** Spurious failures kill the voice pipeline

### No Circuit Breaker (PROV-04)
- Failed providers are retried every single time
- No fail-fast mechanism for known-down providers
- **Impact:** Stacking timeouts during outages (15s for 3 cloud providers)

## Implementation Plan

### A. `agent/providers/resilience.py` (new file)
- `RetryConfig` dataclass: max_attempts=3, backoff_base=0.5, retryable statuses
- `CircuitBreakerConfig` dataclass: fail_max=5, reset_timeout=60
- `HealthCache` class: TTL-based caching (30s cloud, 300s local)
- `with_retry()` decorator using tenacity
- `create_circuit_breaker()` factory using aiobreaker

### B. `agent/providers/base.py` (modify)
- Add shared `httpx.AsyncClient` lifecycle to base classes
- Add `_circuit_breaker` attribute
- Lazy client creation, explicit `close()` method

### C. Provider implementations (modify)
- Replace `async with httpx.AsyncClient() as client:` with `self._http_client`
- Wire retry decorator on HTTP-calling methods

### D. `agent/providers/registry.py` (modify)
- Replace live `health_check()` calls with `HealthCache` lookups
- Add circuit breaker state awareness to fallback selection

## Dependencies Added
- `tenacity>=9.1.4` - async retry with exponential backoff
- `aiobreaker>=1.2.0` - async circuit breaker state machine
