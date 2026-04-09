# State: VoxAgent Production Hardening

**Last Updated:** 2026-04-09
**Current Phase:** Phase 1 — Error Foundation & Shared Primitives
**Status:** NOT STARTED

---

## Phase Progress

| Phase | Name | Status | Requirements | Completed |
|-------|------|--------|--------------|-----------|
| 1 | Error Foundation & Shared Primitives | Not Started | ERRH-01, ERRH-04, ERRH-05 | 0/3 |
| 2 | Audio I/O Layer (Design Once) | Blocked by P1 | AUDR-04, AUDR-05 | 0/2 |
| 3 | Provider Connection Infrastructure | Blocked by P1 | PROV-04, PROV-05, PROV-06, PROV-07 | 0/4 |
| 4 | Provider Fallback Chains | Blocked by P3 | PROV-01, PROV-02, PROV-03, ERRH-02 | 0/4 |
| 5 | Streaming TTS Pipeline | Blocked by P2 | STTS-01, STTS-02, STTS-03, STTS-04 | 0/4 |
| 6 | Barge-In & Echo Prevention | Blocked by P5 | AUDR-01, BGIN-01, BGIN-02, BGIN-03, BGIN-04 | 0/5 |
| 7 | Audio Feedback & Progress | Blocked by P6 | ERRH-03, PROG-01, PROG-02 | 0/3 |
| 8 | VAD Hardening | Blocked by P2 | AUDR-02, AUDR-03 | 0/2 |
| 9 | Safety & Security Hardening | Blocked by P1 | SAFE-01 thru SAFE-08 | 0/8 |
| 10 | Integration Testing & Stabilization | Blocked by All | Cross-cutting | 0/0 |

---

## Requirement Status

| ID | Description | Phase | Status |
|----|-------------|-------|--------|
| ERRH-01 | VoxError hierarchy | 1 | Pending |
| ERRH-04 | Structured logging (structlog) | 1 | Pending |
| ERRH-05 | Standardized SkillResult errors | 1 | Pending |
| AUDR-04 | Bounded ring buffer with metrics | 2 | Pending |
| AUDR-05 | Audio format normalization at capture | 2 | Pending |
| PROV-05 | Retry with exponential backoff | 3 | Pending |
| PROV-06 | Shared httpx client per provider | 3 | Pending |
| PROV-04 | Circuit breaker per provider | 3 | Pending |
| PROV-07 | Health cache with TTL | 3 | Pending |
| PROV-01 | LLM fallback chain in Brain | 4 | Pending |
| PROV-02 | TTS fallback chain | 4 | Pending |
| PROV-03 | STT fallback chain | 4 | Pending |
| ERRH-02 | Spoken error messages | 4 | Pending |
| STTS-01 | Sentence-level text chunking | 5 | Pending |
| STTS-02 | Queue-based chunked playback | 5 | Pending |
| STTS-03 | Edge TTS incremental consumption | 5 | Pending |
| STTS-04 | Pre-buffer playback (<1.5s first-word) | 5 | Pending |
| AUDR-01 | Mic mute during TTS | 6 | Pending |
| BGIN-01 | Wake word during TTS (100ms interrupt) | 6 | Pending |
| BGIN-02 | Audio fade-out (15-25ms) | 6 | Pending |
| BGIN-03 | Cancel in-flight TTS requests | 6 | Pending |
| BGIN-04 | Pipeline state machine | 6 | Pending |
| ERRH-03 | Error earcon | 7 | Pending |
| PROG-01 | Wake word acknowledgment earcon | 7 | Pending |
| PROG-02 | Timeout progress updates | 7 | Pending |
| AUDR-02 | Adaptive VAD thresholds | 8 | Pending |
| AUDR-03 | VAD hysteresis | 8 | Pending |
| SAFE-01 | Terminal AST validation | 9 | Pending |
| SAFE-02 | Remove code-exec commands from allowlist | 9 | Pending |
| SAFE-03 | Type-safe parameter extraction | 9 | Pending |
| SAFE-04 | PromptGuard integration into Brain | 9 | Pending |
| SAFE-05 | Per-skill execution timeout | 9 | Pending |
| SAFE-06 | File operation path sandboxing | 9 | Pending |
| SAFE-07 | Memory DB bounded growth | 9 | Pending |
| SAFE-08 | API server authentication | 9 | Pending |

---

## Active Decisions

None yet — Phase 1 not started.

## Blockers

None yet.

## Notes

- Phases 2, 3, and 9 can run in parallel after Phase 1 completes
- Phase 9 (Safety) is the most parallelizable — 8 mostly independent requirements
- Research pitfall P1: Audio I/O layer designed once in Phase 2, consumed by Phases 5, 6, 7, 8
- Research pitfall P7: Barge-in (Phase 6) co-designed with mic muting (AUDR-01) in same phase

---
*State initialized: 2026-04-09*
