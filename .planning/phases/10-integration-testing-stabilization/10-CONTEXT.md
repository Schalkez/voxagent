# Phase 10: Integration Testing & Stabilization - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

End-to-end verification of all phases working together. No new features -- only cross-cutting integration tests, performance benchmarks, and edge case fixes. Coverage already at 84% (exceeds 80% target).

</domain>

<decisions>
## Implementation Decisions

### Test Scope Strategy
- **D-01:** Cross-phase scenario tests that exercise the full pipeline (wake word -> STT -> Brain -> skill -> TTS -> barge-in)
- **D-02:** Provider failover tests that verify circuit breaker -> health cache -> fallback chain integration
- **D-03:** All tests use mocked providers (no real API calls, no real audio hardware)

### Stability Verification
- **D-04:** Simulated stress tests with mocked providers -- verify no memory leaks, no orphaned threads, no silent failures over extended execution
- **D-05:** Resource cleanup verification: all httpx clients closed, all asyncio tasks cancelled, ring buffer properly drained

### E2E Test Design
- **D-06:** Critical path 1: Full voice pipeline (wake -> STT -> Brain -> skill -> TTS) completes in simulated <5s
- **D-07:** Critical path 2: Provider failover mid-conversation (kill primary, verify fallback, resume)
- **D-08:** Critical path 3: Barge-in during TTS (wake word interrupts, fade-out, pipeline resets to LISTENING)
- **D-09:** Critical path 4: Safety chain (PromptGuard blocks injection -> error earcon -> spoken error)

### Claude's Discretion
- Test file organization and naming
- Mock implementation details
- Specific assertion strategies

</decisions>

<canonical_refs>
## Canonical References

### Phase Summaries (what was built)
- `.planning/phases/01-error-foundation-shared-primitives/SUMMARY-01.md` -- VoxError hierarchy
- `.planning/phases/02-audio-i-o-layer-design-once/SUMMARY-01.md` -- Ring buffer, normalizer
- `.planning/phases/03-provider-connection-infrastructure/SUMMARY.md` -- Retry, circuit breaker, health cache
- `.planning/phases/04-provider-fallback-chains/SUMMARY-01.md` -- FallbackChain[T]
- `.planning/phases/05-streaming-tts-pipeline/SUMMARY-01.md` -- Streaming TTS
- `.planning/phases/06-barge-in-echo-prevention/SUMMARY-01.md` -- Pipeline state machine, barge-in
- `.planning/phases/07-audio-feedback-progress/SUMMARY-01.md` -- Earcons, progress
- `.planning/phases/08-vad-hardening/SUMMARY-01.md` -- Adaptive VAD
- `.planning/phases/09-safety-security-hardening/SUMMARY-01.md` -- Safety features

### Roadmap
- `.planning/ROADMAP.md` -- Phase 10 success criteria (section "Phase 10")

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Test Assets
- `agent/tests/test_integration_pipeline.py` -- Existing integration test patterns
- `agent/tests/test_integration_resilience.py` -- Provider resilience test patterns
- `agent/tests/test_integration_safety.py` -- Safety integration test patterns
- `agent/tests/test_barge_in.py` -- Barge-in unit tests (can be extended to E2E)

### Established Patterns
- All tests use `pytest-asyncio` with `mode=Mode.AUTO`
- Mocking: `unittest.mock.patch`, `AsyncMock` for async providers
- Coverage via `pytest-cov` with `--cov=agent/core --cov=agent/skills`

### Integration Points
- `core/app.py` -- Main pipeline loop (_run_loop) is the E2E entry point
- `core/pipeline_state.py` -- State machine drives all transitions
- `providers/fallback.py` -- FallbackChain orchestrates provider switching

</code_context>

<specifics>
## Specific Requirements

Phase 10 success criteria from ROADMAP.md:
1. Full voice pipeline completes in <5s for simple commands
2. Provider failover mid-conversation works without user intervention
3. 4-hour continuous operation with no memory leaks, no orphaned threads, no silent failures
4. All 35 v1 requirements have at least one passing integration test
5. Core and skills test coverage exceeds 80% (DONE: 84%)

</specifics>

<deferred>
## Deferred Ideas

None -- Phase 10 is the final phase, no scope to defer.

</deferred>

---

*Phase: 10-integration-testing-stabilization*
*Context gathered: 2026-04-12*
