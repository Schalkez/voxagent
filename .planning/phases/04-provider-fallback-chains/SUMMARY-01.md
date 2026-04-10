# Phase 04: Provider Fallback Chains — Summary

**Status:** Complete
**Date:** 2026-04-10
**Requirements:** PROV-01, PROV-02, PROV-03, ERRH-02

---

## What Was Built

### 1. `agent/providers/fallback.py` — Generic FallbackChain[T]

A type-safe, generic async fallback chain that works with any provider type (LLM, STT, TTS, Vision):

- **`FallbackChain[T]`** dataclass with ordered provider list
- **`execute(operation)`** tries each provider in sequence
- **Skips cached-unhealthy** providers via HealthCache integration (Phase 3)
- **Per-provider timeout** (default 2.5s) prevents slow providers from blocking
- **Total budget** (default 4s) caps end-to-end fallback latency (P4 pitfall)
- **`on_failover()` callback** for spoken announcements during failover
- **`FallbackResult[R]`** carries provider_name, attempts, total_latency_ms
- **`AllProvidersExhaustedError`** with Vietnamese user_message for ERRH-02

### 2. PROV-01: LLM Fallback in Brain

- `Brain.__init__` accepts optional `llm_fallback_chain: FallbackChain[LLMProvider]`
- `_try_llm_routing()` delegates to `_route_with_fallback()` when chain is set
- Falls back to legacy single-provider path when no chain is configured
- Extracted `_parse_tool_response()` for reuse across both paths
- `AllProvidersExhaustedError` → `PipelineError` with user_message

### 3. PROV-02: TTS Fallback in Mouth

- `Mouth.__init__` accepts optional `tts_fallback_chain: FallbackChain[TTSProvider]`
- `speak()` routes to `_speak_with_fallback()` when chain is set
- Falls back to `_speak_single()` for backward compatibility
- All TTS failures are logged (never silently dropped)
- Added `FALLBACK_ANNOUNCE_MSG`, `TTS_ALL_FAILED_MSG` constants for ERRH-02

### 4. PROV-03: STT Fallback in Ears

- `Ears.__init__` accepts optional `stt_fallback_chain: FallbackChain[STTProvider]`
- `_transcribe_frames()` delegates to `_transcribe_with_fallback()`
- Cloud STT → local faster-whisper failover within 4s budget
- `AllProvidersExhaustedError` → `PipelineError` with "Khong the nhan dien giong noi"

### 5. ERRH-02: Zero Silent Failures

- `AllProvidersExhaustedError` carries `user_message` for TTS output
- `PipelineError` from Brain/Ears carries speakable Vietnamese messages
- `app.py` main loop already catches `VoxError` and speaks `ve.user_message`
- Fallback chain logs every attempt, skip, timeout, and success

### 6. Registry Factory Methods

- `ProviderRegistry.create_llm_fallback_chain(names)` → `FallbackChain[LLMProvider]`
- `ProviderRegistry.create_stt_fallback_chain(names)` → `FallbackChain[STTProvider]`
- `ProviderRegistry.create_tts_fallback_chain(names)` → `FallbackChain[TTSProvider]`
- All factories share the registry's HealthCache and skip unregistered providers
- `app.py._init_modules()` wires chains into Brain, Ears, Mouth at startup

### 7. Wiring in `app.py`

- Creates `tts_chain`, `stt_chain`, `llm_chain` from registry factories
- Passes chains to Mouth, Ears, Brain constructors (only when non-empty)
- Fully backward compatible: no chain = original single-provider behavior

---

## Files Changed

| File | Change |
|------|--------|
| `agent/providers/fallback.py` | **NEW** — FallbackChain[T], FallbackResult, AllProvidersExhaustedError |
| `agent/providers/__init__.py` | Added FallbackChain, FallbackResult, AllProvidersExhaustedError exports |
| `agent/providers/registry.py` | Added create_llm/stt/tts_fallback_chain() factory methods |
| `agent/core/brain.py` | Added llm_fallback_chain param, _route_with_fallback(), _parse_tool_response() |
| `agent/core/ears.py` | Added stt_fallback_chain param, _transcribe_with_fallback() |
| `agent/core/mouth.py` | Added tts_fallback_chain param, _speak_with_fallback(), error message constants |
| `agent/core/app.py` | Wire fallback chains into Brain, Ears, Mouth at startup |
| `agent/tests/test_fallback_chain.py` | **NEW** — 30 tests covering all requirements |

---

## Test Results

```
tests/test_fallback_chain.py: 30 passed
Full suite: 447 passed, 2 deselected (pre-existing template failures)
```

### Test Coverage by Requirement

| Requirement | Tests |
|-------------|-------|
| PROV-01 (LLM fallback) | `test_brain_uses_fallback_chain`, `test_brain_all_llm_fail_returns_pipeline_error` |
| PROV-02 (TTS fallback) | `test_mouth_uses_tts_fallback_chain`, `test_mouth_all_tts_fail_logs_error`, `test_mouth_single_provider_still_works` |
| PROV-03 (STT fallback) | `test_ears_stt_fallback_chain`, `test_ears_all_stt_fail_raises_pipeline_error`, `test_ears_single_stt_backward_compat` |
| ERRH-02 (spoken errors) | `test_all_providers_exhausted_has_user_message`, `test_pipeline_error_from_brain_has_user_message`, `test_pipeline_error_from_ears_has_user_message` |
| Core chain logic | 12 tests: basic success, failover, empty chain, latency, health cache skip/mark, timeouts, callbacks |
| Registry factories | 5 tests: create chain, skip unregistered, empty chain |

---

## Success Criteria Verification

1. **Killing primary LLM mid-conversation → automatic failover**: `test_brain_uses_fallback_chain` proves failing provider is skipped and backup succeeds
2. **TTS fallback degrades gracefully**: `test_mouth_uses_tts_fallback_chain` proves cloud→local failover; `on_failover` callback enables spoken announcement
3. **STT fallback within 4s budget**: `FALLBACK_TOTAL_BUDGET_SECONDS = 4.0` enforced by `asyncio.wait_for()`; `test_per_provider_timeout` and `test_total_budget_exhausted` verify
4. **Zero silent failures**: All `AllProvidersExhaustedError` and `PipelineError` instances carry `user_message`; app.py speaks it via `await self._mouth.speak(ve.user_message)`

---

## Design Decisions

1. **Generic FallbackChain[T] over separate LLM/TTS/STT chains**: Same behavior for all provider types, reducing duplication (~80 lines covers all)
2. **Dataclass + execute() over inheritance**: Composition is simpler than making providers aware of fallback. Chain wraps providers, providers stay unmodified
3. **Backward compatible**: All chains are optional parameters. No chain = original single-provider behavior. Zero breaking changes
4. **Health cache integration**: Chain reads cached health and updates it on success/failure. No hot-path health checks (P3 pitfall)
5. **Lambda operation pattern**: `chain.execute(lambda p: p.chat(msgs))` — caller controls what operation runs, chain controls retry/failover logic
