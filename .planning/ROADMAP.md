# Roadmap: VoxAgent Production Hardening

**Created:** 2026-04-09
**Granularity:** Fine (10 phases, 35 requirements)
**Core Value:** Voice-first desktop automation that actually works in real-world conditions

---

## Phase 1: Error Foundation & Shared Primitives

Build the error hierarchy, structured logging, and standardized result types that every subsequent phase depends on. No feature behavior changes — only internal plumbing.

### Requirements

| ID | Requirement |
|----|-------------|
| ERRH-01 | Custom VoxError hierarchy with severity, user_message, and retryable flag |
| ERRH-04 | Structured error logging via structlog with context vars |
| ERRH-05 | Standardized SkillResult error format returned from all skills |

### Success Criteria

1. Every raised exception in `core/` and `providers/` is a `VoxError` subclass (no bare `Exception` or `RuntimeError`)
2. `structlog` replaces `logging.getLogger()` in all modified modules — log output includes provider, skill, and latency fields
3. All skills return `SkillResult` with typed error fields — no skill returns raw strings or raises untyped exceptions
4. Existing test suite passes with zero regressions

---

## Phase 2: Audio I/O Layer (Design Once)

Replace the unbounded audio queue with a ring buffer, normalize audio format at capture, and establish the `InterruptController` skeleton. This phase exists because research pitfall P1 warns: design the shared audio output layer once upfront, or rewrite it three times.

### Requirements

| ID | Requirement |
|----|-------------|
| AUDR-04 | Audio queue uses bounded ring buffer with drop-oldest policy and metrics |
| AUDR-05 | Audio format normalized to int16/16kHz/mono at capture |

### Success Criteria

1. Audio capture callback never allocates memory or blocks — ring buffer write completes in <1us
2. Drop counter increments when buffer is full; dropped chunks are logged (not silent)
3. All downstream consumers receive int16/16kHz/mono regardless of hardware capture format
4. Audio pipeline starts and stops cleanly with no orphaned threads or callbacks

---

## Phase 3: Provider Connection Infrastructure

Establish shared httpx clients, retry logic, and circuit breakers — the building blocks that fallback chains need. No fallback wiring yet, just per-provider resilience.

### Requirements

| ID | Requirement |
|----|-------------|
| PROV-05 | Retry with exponential backoff on transient failures (tenacity) |
| PROV-06 | Shared httpx client per provider with connection pooling |
| PROV-04 | Circuit breaker per provider — after N consecutive failures, skip for cooldown |
| PROV-07 | Provider health cached with TTL — no health checks in hot path |

### Success Criteria

1. Each provider creates exactly one `httpx.AsyncClient` at init and reuses it across requests (verified by connection count)
2. Transient HTTP failures (429, 502, 503) trigger automatic retry with exponential backoff — max 3 attempts
3. After N consecutive failures, circuit breaker opens and subsequent calls fail-fast without network I/O for the cooldown period
4. Health check results are cached with TTL — zero health-check HTTP calls occur during normal request flow
5. All circuit breaker state transitions are logged via structlog

---

## Phase 4: Provider Fallback Chains

Wire `FallbackChain[T]` into Brain (LLM), Mouth (TTS), and Ears (STT). When a provider fails and its circuit opens, the chain auto-advances to the next provider. User hears spoken error messages instead of silence.

### Requirements

| ID | Requirement |
|----|-------------|
| PROV-01 | LLM fallback chain wired into Brain |
| PROV-02 | TTS fallback chain — Edge TTS -> ElevenLabs -> Piper local |
| PROV-03 | STT fallback chain — OpenAI Whisper -> faster-whisper local |
| ERRH-02 | User hears spoken error messages instead of silent failures |

### Success Criteria

1. Killing the primary LLM provider mid-conversation causes automatic failover to the next chain entry — user hears the response (not silence)
2. TTS fallback degrades gracefully: cloud TTS failure -> local Piper with spoken announcement ("Switching to local voice")
3. STT fallback from cloud Whisper to local faster-whisper completes within 4s total budget
4. User hears a spoken error message for every failure that affects their experience — zero silent failures

---

## Phase 5: Streaming TTS Pipeline

Sentence-level chunking, queue-based playback via `sounddevice.OutputStream`, Edge TTS incremental consumption, and pre-buffering. This is the first user-visible latency improvement.

### Requirements

| ID | Requirement |
|----|-------------|
| STTS-01 | LLM response text split at sentence boundaries before TTS |
| STTS-02 | Audio playback from asyncio.Queue — play chunk N while N+1 synthesizes |
| STTS-03 | Edge TTS streaming output consumed incrementally via miniaudio decoder |
| STTS-04 | Playback starts after buffering 1-2 chunks, not after all arrive (first-word <1.5s) |

### Success Criteria

1. First audio chunk plays within 1.5s of LLM response completion (measured end-to-end, not just TTS latency)
2. No audible gap between consecutive sentence chunks during playback (gapless streaming)
3. Edge TTS responses are decoded chunk-by-chunk via miniaudio — memory usage stays constant regardless of response length
4. Playback starts after 1-2 chunks are buffered, not after the full response is synthesized

---

## Phase 6: Barge-In & Echo Prevention

Mic muting during TTS, dual-track audio bus (capture + monitor), wake-word interrupt during playback, fade-out, in-flight cancellation, and the pipeline state machine. Co-designed per pitfall P7: barge-in and echo cancellation are architecturally inseparable.

### Requirements

| ID | Requirement |
|----|-------------|
| AUDR-01 | Mic muted (input discarded) while TTS is playing |
| BGIN-01 | Wake word detector runs continuously during TTS playback, triggers interrupt within 100ms |
| BGIN-02 | Audio fades out over 15-25ms on interrupt (no click/pop) |
| BGIN-03 | In-flight TTS synthesis HTTP requests cancelled on interrupt |
| BGIN-04 | Pipeline state machine enforces LISTENING->PROCESSING->SPEAKING->INTERRUPTED->LISTENING without race conditions |

### Success Criteria

1. Whisper never transcribes VoxAgent's own TTS output (echo loop eliminated)
2. Saying "Hey Vox" during TTS playback interrupts audio within 100ms — verified by timestamp delta
3. Audio fade-out produces no audible click or pop artifact (subjective + waveform analysis shows 15-25ms ramp)
4. In-flight TTS HTTP requests are cancelled on interrupt — no wasted API calls after barge-in
5. State machine rejects invalid transitions (e.g., SPEAKING->PROCESSING) and logs violations

---

## Phase 7: Audio Feedback & Progress

Earcons for wake-word acknowledgment, error sounds, and timeout-based progress updates for long-running skills. This phase completes the audio UX.

### Requirements

| ID | Requirement |
|----|-------------|
| ERRH-03 | Error earcon plays before spoken error (distinct beep for errors vs success) |
| PROG-01 | Immediate acknowledgment earcon when wake word detected |
| PROG-02 | Timeout-based progress update — if skill >3s, speak "Processing..." with periodic updates |

### Success Criteria

1. User hears a distinct earcon within 200ms of wake word detection — confirms the system heard them
2. Error earcon is audibly different from acknowledgment earcon (different frequency/pattern)
3. Skills running longer than 3s trigger a spoken progress update; updates repeat periodically until completion
4. Earcons play through the streaming TTS pipeline without disrupting ongoing audio

---

## Phase 8: VAD Hardening

Adaptive VAD thresholds based on ambient noise and hysteresis to prevent premature cutoffs. These are audio resilience improvements that don't depend on barge-in but benefit from the stabilized audio layer.

### Requirements

| ID | Requirement |
|----|-------------|
| AUDR-02 | VAD thresholds adapt to ambient noise level (not hardcoded RMS 500.0) |
| AUDR-03 | VAD hysteresis — require N consecutive speech frames to start, M silence frames to stop |

### Success Criteria

1. VAD correctly detects speech in environments with ambient noise up to 60dB (fan, AC) without constant false triggers
2. Short pauses (<500ms) within a sentence do not prematurely end recording (hysteresis prevents false stops)
3. VAD start threshold adapts within 2s of environment change (e.g., turning on a fan)
4. No regression in quiet-room VAD accuracy — false trigger rate stays below 1%

---

## Phase 9: Safety & Security Hardening

Terminal AST validation, dangerous command removal, type-safe parameter extraction, PromptGuard wiring, execution timeouts, file sandboxing, memory DB bounds, and API authentication. Mostly independent items that can be parallelized.

### Requirements

| ID | Requirement |
|----|-------------|
| SAFE-01 | Terminal skill validates commands via AST parsing, not regex |
| SAFE-02 | Remove python/pip/node/git from terminal allowlist |
| SAFE-03 | Type-safe parameter extraction from LLM tool calls with validation and fallback |
| SAFE-04 | PromptGuard integrated into Brain.process() pipeline |
| SAFE-05 | Per-skill execution timeout enforced (configurable, default 30s) |
| SAFE-06 | File operations restricted to user-configurable allowed directories |
| SAFE-07 | Memory DB bounded growth — auto-prune conversations older than configurable TTL |
| SAFE-08 | API server requires authentication token |

### Success Criteria

1. `python -c "import os; os.system('rm -rf /')"` is rejected by AST validation — not just pattern-matched
2. `python`, `pip`, `node`, `git` commands are completely removed from the terminal allowlist (no bypass possible)
3. LLM tool call parameters are validated via Pydantic models — malformed parameters return typed errors, not crashes
4. PromptGuard runs on every user input before Brain processes it — injection attempts are blocked and logged
5. A skill exceeding its timeout is forcefully cancelled — the pipeline continues to next command

---

## Phase 10: Integration Testing & Stabilization

End-to-end verification of all phases working together. No new features — only cross-cutting integration tests, performance benchmarks, and edge case fixes.

### Requirements

No new requirements — this phase validates all 35 requirements work together.

### Success Criteria

1. Full voice pipeline (wake word -> STT -> Brain -> skill -> TTS -> barge-in) completes in <5s for simple commands
2. Provider failover mid-conversation (kill primary, verify fallback, resume) works without user intervention
3. 4-hour continuous operation with no memory leaks, no orphaned threads, and no silent failures
4. All 35 v1 requirements have at least one passing integration test that exercises the requirement end-to-end
5. Core and skills test coverage exceeds 80%

---

## Dependency Graph

```
Phase 1 (Error Foundation)
  |
  +---> Phase 2 (Audio I/O Layer)
  |       |
  |       +---> Phase 5 (Streaming TTS) ---> Phase 6 (Barge-In & Echo)
  |       |                                       |
  |       +---> Phase 8 (VAD Hardening)           +---> Phase 7 (Audio Feedback)
  |
  +---> Phase 3 (Provider Connections)
  |       |
  |       +---> Phase 4 (Fallback Chains)
  |
  +---> Phase 9 (Safety & Security) [independent after Phase 1]
  |
  All ---> Phase 10 (Integration & Stabilization)
```

### Parallelization Opportunities

- **After Phase 1:** Phases 2, 3, and 9 can start in parallel
- **After Phase 2:** Phase 5 and Phase 8 can start in parallel
- **After Phase 3:** Phase 4 can start immediately
- **After Phase 5:** Phase 6 starts (depends on streaming TTS)
- **After Phase 6:** Phase 7 starts (depends on barge-in state machine)
- **Phase 9** is independent of the audio/provider tracks after Phase 1

---

## Coverage Verification

| Category | Requirements | Phase(s) | Count |
|----------|-------------|----------|-------|
| Barge-In | BGIN-01, BGIN-02, BGIN-03, BGIN-04 | Phase 6 | 4 |
| Streaming TTS | STTS-01, STTS-02, STTS-03, STTS-04 | Phase 5 | 4 |
| Provider Resilience | PROV-01, PROV-02, PROV-03 | Phase 4 | 3 |
| Provider Resilience | PROV-04, PROV-05, PROV-06, PROV-07 | Phase 3 | 4 |
| Error Handling | ERRH-01, ERRH-04, ERRH-05 | Phase 1 | 3 |
| Error Handling | ERRH-02 | Phase 4 | 1 |
| Error Handling | ERRH-03 | Phase 7 | 1 |
| Audio Resilience | AUDR-04, AUDR-05 | Phase 2 | 2 |
| Audio Resilience | AUDR-01 | Phase 6 | 1 |
| Audio Resilience | AUDR-02, AUDR-03 | Phase 8 | 2 |
| Progress Feedback | PROG-01, PROG-02 | Phase 7 | 2 |
| Safety & Security | SAFE-01 thru SAFE-08 | Phase 9 | 8 |
| **Total** | | | **35** |

**35/35 v1 requirements mapped. 0 unmapped. 100% coverage.**

---
*Roadmap created: 2026-04-09*
*Derived from: REQUIREMENTS.md (35 v1 requirements), research/SUMMARY.md (pitfalls, architecture patterns, implementation order)*
