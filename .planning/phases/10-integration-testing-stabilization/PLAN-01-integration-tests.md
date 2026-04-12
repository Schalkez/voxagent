# PLAN-01: E2E Integration Tests

**Phase:** 10 — Integration Testing & Stabilization
**Scope:** Success criteria 1-4 (criterion 5 already met at 84%)
**Files:** 2 new test files in `agent/tests/`

---

## Goal

Write comprehensive E2E integration tests that verify all 35 v1 requirements work together as a system. Tests exercise cross-phase interactions using mocked providers — no real API calls, no real audio hardware.

---

## Analysis of Existing Coverage

### Already covered (by existing test files)

The following test files already exist and provide substantial requirement-level coverage:

| File | Coverage |
|------|----------|
| `test_requirement_traceability.py` | All 35 requirements have at least 1 test each (per-requirement, unit-level) |
| `test_requirement_coverage.py` | All 35 requirements have at least 1 test each (per-requirement, unit-level, duplicate of above) |
| `test_integration_pipeline.py` | Full pipeline loop, barge-in cycle, provider failover, error paths |
| `test_integration_resilience.py` | Circuit breaker + health cache + fallback chain, memory pruning, audio subsystem |
| `test_integration_safety.py` | PromptGuard + Brain, terminal AST, execution timeout, file sandbox, API auth |

### Gaps to fill

1. **SC-1: Full voice pipeline <5s** — Existing test covers Brain+Hands+Mouth but not the full loop including STT transcription and barge-in reset. Need a true end-to-end test simulating wake-word -> STT -> Brain -> Hands -> streaming TTS -> barge-in -> LISTENING.
2. **SC-2: Provider failover mid-conversation** — Existing test covers single-call failover but not *mid-conversation* where the primary dies between turn 1 and turn 2 and the fallback seamlessly takes over.
3. **SC-3: 4-hour continuous operation** — No existing test. Need a simulated stress test: run N iterations of the pipeline loop with mock providers, verify no memory leaks (object count stable), no orphaned tasks, no silent failures.
4. **SC-4: 35 requirements end-to-end** — `test_requirement_traceability.py` has per-requirement tests but many are unit-level (check a constant exists, check a class field). Need true *integration* tests that exercise the requirement through the pipeline. Some gaps:
   - STTS-02/03/04: Only check API existence, not actual streaming produce/consume
   - PROV-03: Only checks constructor signature, not actual STT failover
   - AUDR-01: Only checks mute/unmute API, not that mic IS muted during SPEAKING state
   - PROG-02: Only checks constants exist, not that progress fires during slow skill
   - SAFE-08: Only checks middleware exists, not actual auth rejection

---

## Task Breakdown

### File 1: `agent/tests/test_e2e_pipeline.py`
**Purpose:** Cross-phase E2E scenarios covering SC-1, SC-2, SC-3

#### Task 1.1: Full Voice Pipeline E2E (<5s)
- **What:** Simulate the complete loop: mock audio chunk -> wake word detected -> earcon played -> STT transcribes -> Brain routes (Tier 0 keyword) -> Hands executes skill -> Mouth speaks via streaming TTS -> pipeline returns to LISTENING
- **How:**
  - Create `MockEarsAdapter` that yields a pre-recorded audio chunk and returns a `TranscribeResult`
  - Wire mock STT, mock TTS, real Brain, real Hands, real Mouth with mock TTS provider
  - Assert state machine transitions: LISTENING -> PROCESSING -> SPEAKING -> LISTENING
  - Assert total elapsed time < 5s
  - Assert earcon was generated (acknowledge)
  - Assert TTS `synthesize` was called with the skill's response text
- **Covers:** SC-1, BGIN-04, PROG-01, STTS-01/02, ERRH-05

#### Task 1.2: Full Pipeline with LLM Routing (<5s)
- **What:** Same as 1.1 but with a non-keyword command that escalates to Tier 1 LLM
- **How:** Mock LLM returns tool call, verify intent extraction + skill execution + TTS
- **Covers:** SC-1, PROV-01

#### Task 1.3: Barge-In Mid-Speech E2E
- **What:** During TTS playback (SPEAKING state), simulate wake word detection -> interrupt fires -> TTS stops -> pipeline resets to LISTENING -> second command processed
- **How:**
  - Start speak_streaming in a task
  - After 50ms, trigger interrupt
  - Assert state machine reaches INTERRUPTED then LISTENING
  - Process a second command to verify recovery
- **Covers:** BGIN-01, BGIN-02, BGIN-03, BGIN-04, AUDR-01

#### Task 1.4: Provider Failover Mid-Conversation
- **What:** Process command 1 with primary LLM -> success. Before command 2, mark primary as failed (circuit breaker opens). Process command 2 -> fallback LLM succeeds. User never sees an error.
- **How:**
  - Create FallbackChain with 2 LLM providers
  - First call: both healthy, primary responds
  - Update health cache to mark primary unhealthy
  - Second call: primary skipped via health cache, fallback responds
  - Assert both intents resolved successfully
  - Assert failover callback was invoked
- **Covers:** SC-2, PROV-01, PROV-04, PROV-07, ERRH-02

#### Task 1.5: TTS Failover Mid-Conversation
- **What:** First response spoken via primary TTS. Before second response, primary TTS fails. Mouth uses fallback TTS. User hears both responses.
- **How:**
  - Create TTS FallbackChain with 2 providers
  - First speak: primary succeeds
  - Make primary raise on second call
  - Second speak: fallback succeeds
  - Assert both calls completed without raising
- **Covers:** SC-2, PROV-02, ERRH-02

#### Task 1.6: STT Failover
- **What:** Primary STT fails -> fallback STT transcribes -> Brain processes normally
- **How:**
  - Create STT FallbackChain, primary raises ProviderError, secondary returns TranscribeResult
  - Execute through the chain
  - Assert transcription result is from the fallback
- **Covers:** PROV-03

#### Task 1.7: Error Path E2E (Skill Failure -> Earcon -> Spoken Error -> Recovery)
- **What:** Skill fails -> error earcon generated -> spoken error via TTS -> pipeline recovers -> next command succeeds
- **How:**
  - Register a _FailingSkill, process intent through Hands
  - Assert SkillResult has error_code, tts_response
  - Speak error via Mouth (mock TTS)
  - Process a second command with _FakeSkill -> succeeds
  - Assert state machine ends in LISTENING
- **Covers:** ERRH-02, ERRH-03, ERRH-05

#### Task 1.8: Safety Chain E2E (PromptGuard -> Error -> Spoken Rejection)
- **What:** Injection attempt -> PromptGuard blocks in Brain -> blocked intent returned -> error earcon + spoken rejection -> pipeline ready for next command
- **How:**
  - Brain.process("ignore all previous instructions") -> blocked intent
  - Assert LLM was NOT called
  - Generate error earcon, speak rejection via Mouth
  - Process a normal command -> succeeds
- **Covers:** SAFE-04, ERRH-02, ERRH-03

#### Task 1.9: Simulated Stability Test (SC-3)
- **What:** Run 200 iterations of the pipeline loop (simulating ~4 hours compressed). Each iteration: Brain.process -> Hands.execute -> Mouth.speak. Track object counts, task counts, verify no leaks.
- **How:**
  - Use `gc.get_objects()` count before and after
  - Track `asyncio.all_tasks()` count before and after
  - Verify no unhandled exceptions in any iteration
  - Alternate between keyword commands and LLM-routed commands
  - Every 10th iteration simulate a provider failure + failover
  - Every 20th iteration simulate a skill timeout
  - Assert object count delta < 5% (no significant leak)
  - Assert task count returns to baseline after each iteration
- **Covers:** SC-3

#### Task 1.10: Concurrent Pipeline Operations
- **What:** Verify ring buffer, interrupt controller, and state machine work correctly under concurrent access
- **How:**
  - Producer task writes to ring buffer while consumer reads
  - Interrupt task fires while TTS task is running
  - State machine is queried from multiple concurrent tasks
  - No deadlocks, no data corruption
- **Covers:** AUDR-04, BGIN-01, BGIN-04

### File 2: `agent/tests/test_e2e_requirements.py`
**Purpose:** Fill remaining integration gaps from SC-4 — upgrade the shallow requirement tests to true E2E integration tests

#### Task 2.1: STTS-02 Streaming Produce/Consume E2E
- **What:** Verify that Mouth.speak_streaming actually produces and consumes chunks through the StreamingPlayer queue
- **How:**
  - Create mock TTS that yields 3 chunks
  - Call speak_streaming
  - Assert chunks were enqueued (verify via player metrics or mock)
- **Covers:** STTS-02, STTS-04

#### Task 2.2: STTS-03 Edge TTS Incremental Consumption
- **What:** Verify that synthesize_stream yields chunks one-by-one and Mouth consumes them incrementally
- **How:**
  - Mock TTS provider's synthesize_stream to yield 5 chunks with small delays
  - Call speak_streaming
  - Assert all chunks were consumed (not buffered all-at-once)
- **Covers:** STTS-03

#### Task 2.3: AUDR-01 Mic Muted During SPEAKING
- **What:** Verify that when pipeline state is SPEAKING, the recorder is effectively muted
- **How:**
  - Create AudioRecorder, transition state to SPEAKING, mute recorder
  - Assert read_chunk returns None
  - Transition to LISTENING, unmute
  - Assert read_chunk behavior changes (or returns None from empty buffer)
- **Covers:** AUDR-01

#### Task 2.4: PROG-02 Progress Update During Slow Skill
- **What:** Verify that a slow skill (>3s) triggers progress messages via Mouth
- **How:**
  - Create a skill that sleeps 0.5s (with timeout set to 2s)
  - Register a mock Mouth on Hands
  - Use a skill that sleeps 0.4s (above PROGRESS_INITIAL_DELAY_S scaled to 0.1s for test)
  - Or: directly test the progress task creation by mocking PROGRESS_INITIAL_DELAY_S to 0.1s
  - Assert mouth.speak was called with a progress message
- **Covers:** PROG-02

#### Task 2.5: SAFE-08 API Auth Rejection E2E
- **What:** Verify that a request to a protected endpoint without a token is rejected
- **How:**
  - Use FastAPI TestClient
  - Send GET to /api/providers without auth header -> 401/403
  - Send GET to /api/health without auth header -> 200 (public)
  - Send GET to /api/providers with valid token -> 200
- **Covers:** SAFE-08

#### Task 2.6: SAFE-06 File Sandbox Path Traversal
- **What:** Verify that path traversal attempts (../../etc/passwd) are blocked
- **How:**
  - FileManagerSkill with allowed_directories=["/tmp/safe"]
  - Execute with path="/tmp/safe/../../etc/passwd"
  - Assert result.success is False, error_code is "path_not_allowed"
- **Covers:** SAFE-06

#### Task 2.7: SAFE-03 Parameter Extraction Through Brain
- **What:** Verify that LLM tool call params flow through extract_params before skill execution
- **How:**
  - Mock LLM returns a tool call with valid params -> extraction succeeds -> skill runs
  - Mock LLM returns a tool call with malformed params -> extraction fails -> error returned
- **Covers:** SAFE-03

#### Task 2.8: Cross-Phase Audio Pipeline
- **What:** Audio normalization -> ring buffer -> VAD -> adaptive threshold all working together
- **How:**
  - Normalize a float32/48kHz/stereo chunk -> int16/16kHz/mono
  - Write to ring buffer
  - Read from ring buffer
  - Feed to AdaptiveVAD
  - Assert VAD processes without error, ambient RMS updates
- **Covers:** AUDR-02, AUDR-03, AUDR-04, AUDR-05

---

## Test Helpers (Shared)

Both files will reuse a common set of helpers:

```python
# Shared mock factories (already established in test_integration_pipeline.py):
- _FakeSkill: Always succeeds with TTS response
- _FailingSkill: Always returns SkillResult.fail()
- _SlowSkill: Sleeps past timeout
- _make_mock_llm(): Returns AsyncMock with chat_with_tools
- _make_mock_tts(): Returns AsyncMock with synthesize + synthesize_stream
- _make_mock_stt(): Returns AsyncMock with transcribe
- _make_valid_wav_bytes(): Generates minimal WAV bytes
```

New helpers needed:
- `_make_mock_stt_failing()`: STT that raises ProviderError
- `_timed_pipeline()`: Context manager that measures elapsed time and asserts < budget

---

## Requirement-to-Test Mapping

| Req ID | Test Location | Test Name |
|--------|---------------|-----------|
| BGIN-01 | `test_e2e_pipeline.py::TestBargeInE2E::test_interrupt_during_speaking` | Task 1.3 |
| BGIN-02 | `test_e2e_pipeline.py::TestBargeInE2E::test_interrupt_during_speaking` | Task 1.3 |
| BGIN-03 | `test_e2e_pipeline.py::TestBargeInE2E::test_interrupt_during_speaking` | Task 1.3 |
| BGIN-04 | `test_e2e_pipeline.py::TestFullPipelineE2E::test_full_voice_pipeline_under_5s` | Task 1.1 |
| STTS-01 | `test_e2e_pipeline.py::TestFullPipelineE2E::test_full_voice_pipeline_under_5s` | Task 1.1 |
| STTS-02 | `test_e2e_requirements.py::TestStreamingTTSE2E::test_streaming_produce_consume` | Task 2.1 |
| STTS-03 | `test_e2e_requirements.py::TestStreamingTTSE2E::test_incremental_consumption` | Task 2.2 |
| STTS-04 | `test_e2e_requirements.py::TestStreamingTTSE2E::test_streaming_produce_consume` | Task 2.1 |
| PROV-01 | `test_e2e_pipeline.py::TestProviderFailoverE2E::test_llm_failover_mid_conversation` | Task 1.4 |
| PROV-02 | `test_e2e_pipeline.py::TestProviderFailoverE2E::test_tts_failover_mid_conversation` | Task 1.5 |
| PROV-03 | `test_e2e_pipeline.py::TestProviderFailoverE2E::test_stt_failover` | Task 1.6 |
| PROV-04 | `test_e2e_pipeline.py::TestProviderFailoverE2E::test_llm_failover_mid_conversation` | Task 1.4 |
| PROV-05 | Existing `test_requirement_traceability.py::TestPROV05` (retry decorator verified) | Existing |
| PROV-06 | Existing `test_requirement_traceability.py::TestPROV06` (httpx client reuse verified) | Existing |
| PROV-07 | `test_e2e_pipeline.py::TestProviderFailoverE2E::test_llm_failover_mid_conversation` | Task 1.4 |
| ERRH-01 | Existing `test_requirement_traceability.py::TestERRH01` (hierarchy + fields verified) | Existing |
| ERRH-02 | `test_e2e_pipeline.py::TestErrorPathE2E::test_skill_failure_spoken_error_recovery` | Task 1.7 |
| ERRH-03 | `test_e2e_pipeline.py::TestErrorPathE2E::test_skill_failure_spoken_error_recovery` | Task 1.7 |
| ERRH-04 | Existing `test_requirement_traceability.py::TestERRH04` (structlog verified) | Existing |
| ERRH-05 | `test_e2e_pipeline.py::TestErrorPathE2E::test_skill_failure_spoken_error_recovery` | Task 1.7 |
| AUDR-01 | `test_e2e_requirements.py::TestAudioPipelineE2E::test_mic_muted_during_speaking` | Task 2.3 |
| AUDR-02 | `test_e2e_requirements.py::TestAudioPipelineE2E::test_cross_phase_audio_pipeline` | Task 2.8 |
| AUDR-03 | `test_e2e_requirements.py::TestAudioPipelineE2E::test_cross_phase_audio_pipeline` | Task 2.8 |
| AUDR-04 | `test_e2e_pipeline.py::TestConcurrencyE2E::test_ring_buffer_concurrent` | Task 1.10 |
| AUDR-05 | `test_e2e_requirements.py::TestAudioPipelineE2E::test_cross_phase_audio_pipeline` | Task 2.8 |
| PROG-01 | `test_e2e_pipeline.py::TestFullPipelineE2E::test_full_voice_pipeline_under_5s` | Task 1.1 |
| PROG-02 | `test_e2e_requirements.py::TestProgressE2E::test_progress_fires_during_slow_skill` | Task 2.4 |
| SAFE-01 | Existing `test_integration_safety.py::TestTerminalValidatorIntegration` (AST verified) | Existing |
| SAFE-02 | Existing `test_integration_safety.py::TestTerminalValidatorIntegration` (banned list verified) | Existing |
| SAFE-03 | `test_e2e_requirements.py::TestSafetyE2E::test_param_extraction_through_brain` | Task 2.7 |
| SAFE-04 | `test_e2e_pipeline.py::TestSafetyChainE2E::test_injection_blocked_spoken_rejection` | Task 1.8 |
| SAFE-05 | Existing `test_integration_safety.py::TestExecutionTimeoutIntegration` (timeout verified) | Existing |
| SAFE-06 | `test_e2e_requirements.py::TestSafetyE2E::test_path_traversal_blocked` | Task 2.6 |
| SAFE-07 | Existing `test_integration_resilience.py::TestMemoryPruningIntegration` (pruning verified) | Existing |
| SAFE-08 | `test_e2e_requirements.py::TestSafetyE2E::test_api_auth_rejection` | Task 2.5 |

**35/35 requirements mapped to at least one integration test.**

---

## Verification

```bash
# Run all tests (should pass with 0 failures)
python -m pytest agent/tests/ -q

# Run only the new E2E tests
python -m pytest agent/tests/test_e2e_pipeline.py agent/tests/test_e2e_requirements.py -v

# Verify requirement marker coverage (all 35 markers present)
python -m pytest agent/tests/test_requirement_traceability.py -v --co | grep "requirement"
```

---

## Estimated Size

| File | Classes | Tests | Lines |
|------|---------|-------|-------|
| `test_e2e_pipeline.py` | 6 | ~18-20 | ~500-600 |
| `test_e2e_requirements.py` | 4 | ~10-12 | ~350-400 |
| **Total** | 10 | ~28-32 | ~850-1000 |

---

## Constraints Checklist

- [x] 1 plan (testing only, no features)
- [x] All tests use mocked providers (no real API calls, no real audio hardware)
- [x] Tests go in `agent/tests/` directory
- [x] Uses `pytest-asyncio` for async tests
- [x] Verification: `python -m pytest agent/tests/ -q` must pass with 0 failures
- [x] All 35 requirements have at least one integration test
- [x] No new features or production code changes

---

*Plan created: 2026-04-12*
*Phase: 10-integration-testing-stabilization*
