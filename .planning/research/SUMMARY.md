# VoxAgent Production Hardening: Research Summary

> Synthesized: 2026-04-09
> Sources: STACK.md, FEATURES.md, ARCHITECTURE.md, PITFALLS.md

---

## 1. Key Stack Decisions

### Add

| Package | Version | Purpose | Confidence |
|---------|---------|---------|------------|
| `tenacity` | >=9.1.4 | Retry with exponential backoff (async-native, flexible predicates) | High |
| `miniaudio` | >=1.61 | Streaming MP3 chunk decode for TTS (zero-copy C decoder, no ffmpeg) | High |
| `structlog` | >=25.5.0 | Structured logging with context vars (replaces `logging.getLogger()`) | High |
| `aiobreaker` | >=1.2.0 | Async circuit breaker (per-provider state machine) | Medium |
| `deepfilternet` | >=0.5.6 | Neural noise suppression (reuses existing torch dep) | Medium |
| `noisereduce` | >=3.0.3 | Spectral noise reduction (no-torch fallback, pulls scipy) | Medium |

### Upgrade

| Package | From | To | Reason |
|---------|------|----|--------|
| `edge-tts` | >=6.1 | >=7.2.8 | Native `stream()` API for chunked TTS |
| `sounddevice` | >=0.5.1 | >=0.5.5 | Bug fixes for `OutputStream` callback mode |
| `elevenlabs` | unpinned | >=2.42.0 | `text_to_speech.stream()` for chunked audio |

### Keep (Leverage Existing)

- `sounddevice` -- already in stack; use `OutputStream` instead of `sd.play()` for streaming + interruption
- `torch` -- already in stack for Silero VAD; reused by `deepfilternet`
- `pydub` -- keep as fallback decoder only; not suitable for streaming (batch-only)
- `httpx` -- keep but fix lifecycle (shared client per provider, explicit close)

### Avoid

| Package | Reason |
|---------|--------|
| `pyaudio` | Redundant with sounddevice (same PortAudio backend, worse API) |
| `pygame` | Massive game engine; overkill for audio playback |
| `backoff` | Less maintained, fewer features than tenacity |
| `pybreaker` / `circuitbreaker` | Sync-only; incompatible with async architecture |
| `torchaudio` | 500MB+ just for noise suppression |
| `webrtc-audio-processing` | No maintained Python bindings; complex C++ build |

### Build In-House (No Library)

| Pattern | Lines | Purpose |
|---------|-------|---------|
| `AudioRingBuffer` | ~60 | Lock-free circular buffer with drop-oldest + metrics |
| `VoxError` hierarchy | ~50 | Custom exceptions with severity, user-message, retryable flag |
| `FallbackChain[T]` | ~80 | Generic async provider fallback for LLM/STT/TTS/Vision |
| `InterruptController` | ~20 | `asyncio.Event`-based cancellation for barge-in |
| Mic-mute AEC (Tier 1) | ~10 | `is_speaking` flag to discard mic input during TTS |
| Health cache | ~40 | TTL-based provider health state (avoid hot-path health checks) |

---

## 2. Feature Priorities

### Table Stakes (33 features -- must ship)

| Area | Feature | Complexity | Key Dependency |
|------|---------|------------|----------------|
| **Streaming TTS** | Sentence-level text chunking (2.1) | Low | -- |
| | Chunked audio playback with queue (2.2) | Medium | -- |
| | Edge TTS streaming consumption (2.3) | Low | 2.2 |
| | Pre-buffer with playback threshold (2.5) | Low | 2.2 |
| **Barge-In** | Wake-word barge-in (1.1) | Medium | 5.1 (mic muting) |
| | Audio fade-out on interrupt (1.2) | Low | 2.2 |
| | Cancel in-flight TTS synthesis (1.3) | Low | -- |
| | Barge-in state machine (1.5) | Medium | 1.1 + 1.2 + 1.3 |
| **Provider Resilience** | Connection pooling / shared httpx (3.8) | Low | -- |
| | Retry with exponential backoff (3.5) | Low | -- |
| | Circuit breaker per provider (3.4) | Medium | 3.8 |
| | LLM fallback chain wired into Brain (3.1) | Medium | 3.4 |
| | TTS fallback chain (3.2) | Medium | -- |
| | STT fallback chain (3.3) | Medium | -- |
| **Error Handling** | Custom error hierarchy (4.1) | Medium | -- |
| | User-facing spoken errors (4.2) | Low | 4.1 |
| | Error earcon (4.3) | Low | -- |
| | Structured error logging (4.6) | Low | 4.1 |
| | Standardized SkillResult errors (4.7) | Low | -- |
| **Audio Resilience** | TTS-output mic muting (5.1) | Low | -- |
| | Adaptive VAD thresholds (5.4) | Medium | -- |
| | VAD hysteresis start/end (5.5) | Low | -- |
| | Audio queue backpressure (5.6) | Low | -- |
| | Audio format normalization (5.9) | Low | -- |
| **Progress Feedback** | Immediate acknowledgment earcon (6.1) | Low | 4.3 |
| | Timeout-based progress update (6.2) | Low | -- |
| **Safety & Security** | Terminal AST validation (7.1) | Medium | -- |
| | File operation sandboxing (7.2) | Medium | -- |
| | Type-safe parameter extraction (7.3) | Medium | -- |
| | PromptGuard integration into Brain (7.4) | Low | -- |
| | Execution timeout per skill (7.6) | Low | -- |
| | Memory DB bounded growth (7.8) | Low | -- |
| | Marketplace code signing (7.9) | Medium | -- |
| | API server authentication (7.10) | Low | -- |

**Breakdown: 18 Low, 12 Medium, 0 High**

### Differentiators (14 features -- competitive advantage)

| Feature | Complexity | Why It Differentiates |
|---------|------------|----------------------|
| ElevenLabs streaming API (2.4) | Medium | Best-in-class voice quality with real-time latency |
| LLM token streaming to TTS pipeline (2.6) | Medium | Parallelizes LLM + TTS; noticeably faster than competitors |
| Provider health dashboard indicator (3.6) | Low | System transparency that open-source assistants lack |
| Graceful degradation announcements (3.7) | Low | "Using local model" -- builds user trust |
| State earcons (4.4) | Low | Non-verbal feedback makes assistant feel alive |
| Aggregate health reporting (4.5) | Medium | Self-aware system reports its own degraded state |
| Noise suppression (5.3) | Medium | Better STT accuracy in noisy rooms |
| Audio pipeline health monitoring (5.7) | Low | Detects mic issues before user gets frustrated |
| Skill progress callbacks (6.3) | Medium | Long-running tasks report incremental status |
| Background task completion (6.4) | Medium | User continues interacting while tasks finish |
| Dashboard real-time progress (6.5) | Medium | Live pipeline state via WebSocket |
| Detailed dangerous-action confirmation (7.5) | Low | Speaks WHAT will happen, not generic warning |
| Idempotent cleanup on failure (7.7) | Medium | Rollback on partial multi-step skill failure |
| Software AEC via speexdsp (5.2) | High | Enables true full-duplex (only if barge-in via wake-word is insufficient) |

### Anti-Features (do NOT build)

| Feature | Why Not |
|---------|---------|
| Full-duplex barge-in (1.4) | Requires hardware-grade AEC; wake-word barge-in is sufficient for desktop |
| Adaptive chunk sizing (2.7) | Over-engineering; desktop networks are stable |
| Cross-provider request hedging (3.9) | Wastes API credits for marginal latency gain |
| Automatic error trend detection (4.8) | ML overkill; structured logging + manual review is enough |
| Multi-mic beam-forming (5.8) | Hardware-dependent; desktop PCs have single mics |
| Verbose multi-step narration (6.6) | Annoying; adds latency to simple commands |
| Full process sandboxing (7.11) | Containers for a desktop agent is contradictory |
| AI-based command risk scoring (7.12) | Circular LLM-evaluating-LLM; deterministic validation wins |

---

## 3. Architecture Patterns

### Pattern 1: Audio Ring Buffer (replaces unbounded asyncio.Queue)

Replace the current `asyncio.Queue()` with a pre-allocated circular buffer. The sounddevice C-thread callback writes via `np.copyto()` (no allocation). Consumer reads via `asyncio.Event` notification. Drop-oldest policy with a `DropCounter` for metrics. Ring buffers are correct for audio (old data is worthless); queues are correct for events (must not be lost).

**Key rule:** Never block, allocate, or log in the sounddevice callback.

### Pattern 2: Streaming TTS Pipeline (chunk-and-play)

```
TTSProvider.synthesize_stream(text) -> AsyncIterator[bytes]
  -> miniaudio.decode(chunk) -> numpy PCM
  -> asyncio.Queue (bounded, maxsize=3-5)
  -> sounddevice.OutputStream callback pulls from queue
  -> InterruptController (asyncio.Event) aborts on barge-in
```

`synthesize_stream()` is added to the `TTSProvider` ABC with a default fallback that calls `synthesize()`. Providers with native streaming (Edge TTS, ElevenLabs) override it. Pre-buffer 2-3 chunks before starting playback.

### Pattern 3: Dual-Track Concurrent Audio (AudioBus)

Single audio producer fans out to two independent consumers:
- **CaptureTrack**: Full pipeline (VAD -> record -> STT). Active only during EARS phase.
- **MonitorTrack**: Wake-word only. Always active, even during TTS. Budget: <5ms per 80ms chunk.

MonitorTrack enables barge-in by firing the `InterruptController` when wake word is detected during playback.

### Pattern 4: Circuit Breaker + FallbackChain[T]

Per-provider `CircuitBreaker` (CLOSED -> OPEN -> HALF_OPEN) wraps every provider call. Separate `FallbackChain` per type (LLM, STT, TTS, Vision) configured in YAML. Cloud providers get circuit breakers; local providers do not. Health checks are cached with TTL (30s cloud, 5min local) and run in a background scheduler, never in the hot path.

### Pattern 5: Tiered Error Propagation

```
VoxError (base: severity + user_message + retryable)
  -> ProviderError, AudioError, PipelineError, ConfigError
```

`ErrorBoundary` context manager wraps pipeline stages, catches raw exceptions, maps to typed `VoxError`. Errors propagate naturally to the main loop boundary. Only three catch points: main loop, provider HTTP calls, system I/O. Severity is determined at the boundary (RECOVERABLE / DEGRADED / FATAL), not at the throw site.

### Pattern 6: Tiered AEC (Echo Cancellation)

- **Tier 1 (build first):** Mic-mute flag during TTS playback. Zero cost, covers 80% of cases.
- **Tier 2 (if barge-in needs improvement):** Spectral subtraction using TTS reference signal from `OutputStream`.
- **Tier 3 (last resort):** Adaptive filter via `speexdsp`. Only if Tier 2 is insufficient.

### Pattern 7: Retry + Fallback Separation

Retry within each provider (tenacity: 3 attempts, exponential backoff, only for idempotent + transient errors). Failover across providers (FallbackChain: skip to next when circuit opens). Aggressive per-provider timeouts: 2-3s cloud, 1s health check. Total fallback budget: 4s max before hitting local provider.

---

## 4. Critical Pitfalls

### P1: Design audio I/O layer once, not three times

Streaming TTS, barge-in, and echo cancellation all share the same audio output layer. If implemented as independent features, each phase rewrites the previous. **Design the `AudioOutput` skeleton upfront** with OutputStream, chunk queue, stop signal, and reference signal tap -- even if only streaming is built first.

> Source: PITFALLS.md 8.2, ARCHITECTURE.md Section 6

### P2: Never buffer the full TTS stream before playback

Adding `synthesize_stream()` is pointless if playback still calls `b"".join(chunks)` before `sd.play()`. The playback layer must pull from a queue concurrently with synthesis. If first-word latency benchmarks don't improve, the streaming is fake.

> Source: PITFALLS.md 1.1, 1.3

### P3: Health checks in the hot path destroy voice latency

`get_llm_with_fallback()` currently calls `health_check()` (a real API call, 200-500ms) on every request. With fallback chains, this multiplies. Cache health state in background; fallback reads cached state. Only live-check when cache is stale or after a request failure.

> Source: PITFALLS.md 4.1, FEATURES.md 3.4, ARCHITECTURE.md Section 3

### P4: Fallback chains must respect a total latency budget

Sequential fallback through 3 cloud providers with 5s timeouts each = 15s wait. Voice pipeline has a ~3s budget. Set aggressive per-provider timeouts (2-3s), enforce a total chain budget (4s), and consider racing primary + fast-fallback with `asyncio.wait(FIRST_COMPLETED)`.

> Source: PITFALLS.md 4.4

### P5: Error hierarchy must be adopted incrementally, not defined and forgotten

A beautiful exception hierarchy with zero callers is dead code. Introduce per-module: (1) define exceptions, (2) update raises, (3) update catches, (4) verify with tests. One module at a time, starting with Brain.

> Source: PITFALLS.md 6.1, 6.2

### P6: Terminal allowlist is fundamentally broken

`python`, `node`, `pip`, `git` are in `ALLOWED_COMMAND_PREFIXES` but are arbitrary code execution vectors. AST-based validation cannot make `python -c` safe. **Remove code-execution commands from the allowlist entirely**. For necessary commands, require voice confirmation or execute via Python APIs (pathlib, shutil) instead of shelling out.

> Source: PITFALLS.md 7.1, 7.2, FEATURES.md 7.1

### P7: Barge-in and echo cancellation are architecturally inseparable

Mic muting prevents echo but kills barge-in. Full-duplex barge-in requires AEC. These cannot be designed independently. Use the tiered approach: Tier 1 mic-mute (no barge-in during TTS), Tier 2 spectral subtraction (wake-word barge-in during TTS), co-designed in the same phase.

> Source: PITFALLS.md 3.1, ARCHITECTURE.md Section 5+6

---

## 5. Recommended Implementation Order

### Phase 1: Foundations (no cross-dependencies, ~1-2 weeks)

All items are independent; build in parallel.

| # | Item | Complexity | Unblocks |
|---|------|------------|----------|
| 1 | `AudioRingBuffer` + `DropCounter` | Low | Audio pipeline refactor |
| 2 | `VoxError` hierarchy + `ErrorBoundary` | Medium | Error mapping, fallback, structured logging |
| 3 | `CircuitBreaker` state machine | Medium | Provider fallback |
| 4 | Connection pooling (shared httpx per provider) | Low | Retry logic, circuit breakers |
| 5 | Standardized `SkillResult` error pattern | Low | Consistent error UX |
| 6 | PromptGuard integration into Brain | Low | Security baseline |
| 7 | `InterruptController` (asyncio.Event skeleton) | Low | TTS streaming, barge-in |

### Phase 2: Streaming TTS + Provider Resilience (~2-3 weeks)

Two parallel tracks that converge later.

**Track A: Streaming TTS**

| # | Item | Complexity | Unblocks |
|---|------|------------|----------|
| 8 | `TTSProvider.synthesize_stream()` ABC extension | Low | Streaming providers |
| 9 | Sentence-level text chunking | Low | Non-streaming provider fallback |
| 10 | `PlaybackWorker` (sounddevice OutputStream + queue) | Medium | Chunked playback |
| 11 | Edge TTS streaming consumption | Low | First-word latency <500ms |
| 12 | Pre-buffer with playback threshold | Low | Jitter absorption |
| 13 | `StreamingMouth` orchestrator | Medium | Replaces current Mouth |

**Track B: Provider Resilience**

| # | Item | Complexity | Unblocks |
|---|------|------------|----------|
| 14 | Retry with exponential backoff (tenacity) | Low | Transient failure recovery |
| 15 | `ResilientRegistry` + `FallbackChain` for all types | Medium | Multi-provider fallback |
| 16 | `HealthCheckScheduler` (background probes) | Low | Cached health state |
| 17 | LLM/TTS/STT fallback chain wiring | Medium | End-to-end resilience |
| 18 | `ErrorMapper` + user-facing spoken errors | Low | Never-silent failures |
| 19 | Structured error logging (structlog) | Low | Production diagnostics |

### Phase 3: Barge-In + Audio Feedback (~2 weeks)

Depends on Phase 2 Track A (streaming TTS).

| # | Item | Complexity | Unblocks |
|---|------|------------|----------|
| 20 | Mic-mute AEC (Tier 1: `is_speaking` flag) | Low | Safe wake-word during TTS |
| 21 | `AudioBus` fan-out (CaptureTrack + MonitorTrack) | Medium | Concurrent audio |
| 22 | Wake-word barge-in | Medium | User can interrupt TTS |
| 23 | Audio fade-out on interrupt (15-25ms) | Low | Click-free interruption |
| 24 | Cancel in-flight TTS synthesis | Low | Save API costs |
| 25 | Barge-in state machine (PASSIVE/ACTIVE/PROCESSING/SPEAKING) | Medium | Race condition prevention |
| 26 | Error + acknowledgment earcons | Low | Audio feedback UX |
| 27 | Timeout-based progress update ("Working on that...") | Low | Long-task feedback |

### Phase 4: Hardening & Safety (~2 weeks)

Mostly independent; can be parallelized.

| # | Item | Complexity | Unblocks |
|---|------|------------|----------|
| 28 | Adaptive VAD thresholds | Medium | Noisy environment support |
| 29 | VAD hysteresis (start 0.5, end 0.35) | Low | Fewer premature cutoffs |
| 30 | Audio format normalization | Low | Cross-device reliability |
| 31 | Terminal AST validation (remove python/node from allowlist) | Medium | Security |
| 32 | File operation sandboxing (path jail) | Medium | Security |
| 33 | Type-safe LLM parameter extraction (Pydantic) | Medium | Security |
| 34 | Execution timeout per skill (default 30s) | Low | Pipeline liveness |
| 35 | Memory DB bounded growth (FIFO, 10k cap) | Low | Unbounded growth prevention |
| 36 | API server authentication (localhost key) | Low | Security baseline |
| 37 | Marketplace code signing | Medium | Blocks marketplace RCE |

### Phase 5: Differentiators (ongoing, pick based on user feedback)

| Item | Complexity |
|------|------------|
| ElevenLabs streaming API | Medium |
| LLM token streaming -> TTS pipeline | Medium |
| Noise suppression (deepfilternet) | Medium |
| Provider health dashboard | Low |
| Spectral subtraction AEC (Tier 2) | Medium |
| Dashboard real-time progress (WebSocket) | Medium |
| Skill progress callbacks | Medium |
| Background task completion notifications | Medium |

---

## 6. Net New Dependencies

### Required (install immediately)

| Package | Version | Size | Transitive Deps |
|---------|---------|------|-----------------|
| `tenacity` | >=9.1.4 | ~50KB | None (pure Python) |
| `miniaudio` | >=1.61 | ~500KB | None (vendored C) |
| `structlog` | >=25.5.0 | ~200KB | None (pure Python) |

### Recommended (install in Phase 2-3)

| Package | Version | Size | Transitive Deps |
|---------|---------|------|-----------------|
| `aiobreaker` | >=1.2.0 | ~20KB | None (pure Python) |
| `deepfilternet` | >=0.5.6 | ~50MB | torch (already in stack) |
| `noisereduce` | >=3.0.3 | ~100KB | scipy (~30MB, new) |

### Optional (Phase 5+)

| Package | Version | Size | Transitive Deps |
|---------|---------|------|-----------------|
| `speexdsp` | >=0.1.1 | ~200KB | System libspeexdsp |
| `webrtcvad` | >=2.0.10 | ~100KB | None (vendored C) |
| `pyrnnoise` | >=0.4.3 | ~1MB | cffi |
| `opentelemetry-api` | >=1.41.0 | ~500KB | Several (tracing ecosystem) |

### Version Bumps (existing deps)

| Package | Current | Target |
|---------|---------|--------|
| `edge-tts` | >=6.1 | >=7.2.8 |
| `sounddevice` | >=0.5.1 | >=0.5.5 |
| `elevenlabs` | unpinned | >=2.42.0 |

### Total New Footprint

- **Minimal (Required only):** ~750KB
- **With Recommended:** ~51MB (dominated by deepfilternet models; reuses existing torch)
- **With Optional:** ~53MB
- **New heavy transitive dep:** `scipy` (~30MB) via `noisereduce` -- justified for signal processing

---

*All version numbers verified against PyPI on 2026-04-09. See individual research files for detailed analysis: STACK.md (libraries), FEATURES.md (feature matrix), ARCHITECTURE.md (component design), PITFALLS.md (failure modes).*
