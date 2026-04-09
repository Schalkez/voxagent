# Production Voice Assistant Features: Resilience & Reliability

> Research date: 2026-04-09
> Scope: Features dimension for VoxAgent production hardening
> Sources: Alexa, Google Assistant, Siri, Mycroft/OVOS, OpenClaw, Rhasspy, Home Assistant Voice architecture analysis
> Downstream: Requirements definition for hardening milestone

---

## Feature Categories

Each feature is classified as:
- **Table Stakes** -- Must have or users leave. Every production voice assistant ships this.
- **Differentiator** -- Competitive advantage. Not all assistants have it, or VoxAgent's context (desktop agent, local-first) makes it uniquely valuable.
- **Anti-Feature** -- Things to deliberately NOT build. Would add complexity without serving VoxAgent's core value.

Complexity is rated: `Low` (days), `Medium` (1-2 weeks), `High` (2-4 weeks), `Very High` (month+).

---

## 1. TTS Interruption / Barge-In

### Context

Barge-in is the ability for a user to interrupt the assistant while it is speaking. Without it, users must wait for the full TTS response before issuing the next command -- an experience that feels broken on the first interaction.

### How Production Assistants Handle It

**Alexa / Google Home / Siri:**
- TTS audio is played through a managed audio pipeline with an `AbortController`-equivalent signal.
- Wake word detection runs continuously, even during TTS playback.
- When wake word is detected mid-speech: (1) TTS audio stops immediately (<50ms), (2) mic reopens for new command, (3) any in-flight TTS synthesis is cancelled.
- Google Home uses a "full-duplex" model where the mic is always processing even during output, with echo cancellation separating the assistant's own voice from user speech.

**OpenClaw (reference codebase):**
- Queue-based TTS with `AbortController` for barge-in. Each TTS chunk is an independently cancellable unit.
- Audio playback uses a drain/abort pattern: on interrupt, current chunk is faded out over ~20ms (to avoid click artifacts), queue is flushed, and the pipeline resets to listening state.

**Key Design Decision: Partial vs Full Barge-In**
- **Full barge-in** (Alexa model): Any detected speech interrupts TTS. Simpler but causes false interrupts from background noise/TV.
- **Wake-word barge-in** (safer model): Only wake word detection triggers interrupt. User says "Hey Vox" to cut in. More predictable, fewer false positives.
- **Hybrid** (Google model): Full-duplex with echo cancellation allows natural interruption. Very complex to implement correctly.

### Features

| # | Feature | Category | Complexity | Description |
|---|---------|----------|------------|-------------|
| 1.1 | **Wake-word barge-in** | Table Stakes | Medium | Wake word detector runs during TTS playback. On detection: abort current TTS, flush audio queue, resume listening. Requires `AbortController` pattern on TTS pipeline and concurrent wake word processing. |
| 1.2 | **Audio fade-out on interrupt** | Table Stakes | Low | When barge-in triggers, fade out current audio chunk over 15-25ms instead of hard stop. Prevents audible click/pop artifacts. |
| 1.3 | **Cancel in-flight TTS synthesis** | Table Stakes | Low | When barge-in triggers, cancel any HTTP requests or synthesis operations still in progress. Prevents wasted compute and API costs (ElevenLabs charges per character). |
| 1.4 | **Full-duplex barge-in (voice-activity triggered)** | Anti-Feature | Very High | Requires production-grade echo cancellation (AEC) to separate own TTS from user speech. Alexa/Google have dedicated DSP hardware for this. Software AEC (speexdsp, WebRTC AEC) is unreliable on commodity PC hardware with varied speaker/mic configurations. The wake-word model is safer and sufficient for desktop use. |
| 1.5 | **Barge-in state machine** | Table Stakes | Medium | Formal state machine: `LISTENING -> PROCESSING -> SPEAKING -> INTERRUPTED -> LISTENING`. Prevents race conditions (e.g., barge-in arriving while previous interrupt is still cleaning up). |

### Dependencies
- 1.1 depends on: Echo cancellation (5.1) at minimum basic level, or speaker/mic isolation
- 1.2 depends on: Streaming TTS playback (2.2) -- need chunk-level audio control
- 1.3 depends on: Provider fallback architecture (3.x) -- cancellation tokens on provider calls
- 1.5 depends on: 1.1, 1.2, 1.3 all integrated

### VoxAgent Current State
- `mouth.py` plays entire synthesized audio as a single block via `sounddevice`
- No `AbortController` or cancellation token pattern exists
- Wake word detector (`wake_word.py`) does NOT run during TTS playback
- Audio pipeline has no concept of interruptibility

---

## 2. Streaming TTS

### Context

Non-streaming TTS requires synthesizing the entire response before playing any audio. For a 3-sentence response via a cloud TTS provider, this means 1-3 seconds of silence before the user hears anything. Streaming TTS synthesizes and plays incrementally.

### Production Benchmarks

| Metric | Alexa/Google | Good Local | Acceptable | VoxAgent Current |
|--------|-------------|------------|------------|-----------------|
| First-word latency | <200ms | <300ms | <500ms | 1-3s (full synthesis) |
| End-to-end (wake to first word) | <1s | <1.5s | <2s | 3-8s |
| Audio gap between chunks | 0ms (gapless) | <20ms | <50ms | N/A (no streaming) |

### How Production Assistants Handle It

**Alexa:**
- LLM generates tokens; as soon as a sentence boundary is detected, that sentence is sent to TTS.
- TTS returns audio in chunks (typically sentence-level), which are queued and played gaplessly.
- Uses a pre-buffer strategy: starts playing when the first chunk is ready, while subsequent chunks continue synthesizing in parallel.

**Google Home:**
- Similar sentence-level chunking, but with an additional "eager start" optimization: begins TTS on the first clause (comma-separated) rather than waiting for a full sentence.
- Uses their own streaming TTS API that returns audio frames incrementally.

**Edge TTS (VoxAgent's current primary provider):**
- Already supports streaming natively -- the `edge-tts` library yields MP3 chunks as they arrive.
- VoxAgent currently collects ALL chunks, concatenates, converts to WAV, then plays -- missing the streaming opportunity entirely.

**ElevenLabs:**
- Streaming API available (`/v1/text-to-speech/{voice_id}/stream`) with chunked transfer encoding.
- Supports WebSocket streaming for lowest latency (<250ms first byte).

**Piper (local):**
- Processes text to audio in one shot (no native streaming), but is fast enough (<200ms for short sentences) that sentence-level chunking is sufficient.

### Features

| # | Feature | Category | Complexity | Description |
|---|---------|----------|------------|-------------|
| 2.1 | **Sentence-level text chunking** | Table Stakes | Low | Split LLM response at sentence boundaries (`.!?`) before sending to TTS. Each sentence is an independent TTS request. |
| 2.2 | **Chunked audio playback with queue** | Table Stakes | Medium | Audio playback consumes from an `asyncio.Queue` of audio chunks. Play chunk N while chunk N+1 is synthesizing. Gapless crossover between chunks. |
| 2.3 | **Edge TTS streaming consumption** | Table Stakes | Low | Consume `edge-tts` streaming output incrementally instead of collecting all chunks. Pipe MP3 chunks through decoder to playback queue as they arrive. |
| 2.4 | **ElevenLabs streaming API** | Differentiator | Medium | Use ElevenLabs `/stream` endpoint or WebSocket API for real-time audio streaming. Best quality voice with lowest latency. |
| 2.5 | **Pre-buffer with playback threshold** | Table Stakes | Low | Start playback after buffering N chunks (typically 1-2), not after all chunks arrive. Configurable buffer depth for latency vs. reliability tradeoff. |
| 2.6 | **LLM token streaming to TTS pipeline** | Differentiator | Medium | Stream LLM output tokens, detect sentence boundaries in the token stream, and feed completed sentences to TTS immediately -- rather than waiting for full LLM response. Reduces latency by parallelizing LLM generation and TTS synthesis. |
| 2.7 | **Adaptive chunk sizing** | Anti-Feature | Medium | Dynamically adjust chunk size based on network conditions. Over-engineering for desktop use where conditions are stable. Fixed sentence-level chunking is sufficient. |

### Dependencies
- 2.2 depends on: Audio fade-out (1.2) for clean interruption of chunk playback
- 2.3 depends on: 2.2 (needs the queue-based playback)
- 2.4 depends on: 2.2 (needs the queue-based playback)
- 2.6 depends on: LLM providers supporting streaming responses (all VoxAgent cloud providers do, Ollama does too)

### VoxAgent Current State
- `mouth.py:speak()` calls `TTSProvider.synthesize()` which returns complete WAV bytes
- `edge_tts_provider.py` calls `edge-tts` communicate() and collects entire stream into BytesIO
- Playback is via `sounddevice.play()` on the complete buffer -- no chunking
- No streaming LLM response consumption in `brain.py`

---

## 3. Provider Fallback

### Context

Cloud APIs fail. Alexa's 2023 Christmas outage, OpenAI rate limits, Groq capacity issues -- any single-provider dependency is a fragility. Provider fallback means the assistant keeps working when one provider is down.

### How Production Assistants Handle It

**Alexa / Google Home:**
- Multiple redundant backend services across data centers with automatic failover.
- Client devices have local fallback capabilities (offline wake word, basic commands, timers) that work without cloud connectivity.
- Circuit breaker pattern: after N consecutive failures, a provider is marked "unhealthy" and skipped for a cool-down period (typically 30-60s), then probed again.

**Mycroft / OVOS (open-source):**
- Configurable fallback chains: e.g., STT: `faster-whisper -> openai-whisper -> google-stt`.
- Each provider in the chain is tried sequentially on failure.
- Fallback events are logged and surfaced to the user as status changes.

**OpenClaw:**
- Pre-start timeout with `unref()`: provider initialization has a timeout; if it doesn't respond in time, the system continues without it (degraded mode).
- Provider health is checked at startup and periodically. Unhealthy providers are removed from the active pool.

### Features

| # | Feature | Category | Complexity | Description |
|---|---------|----------|------------|-------------|
| 3.1 | **LLM fallback chain (wired into Brain)** | Table Stakes | Medium | `Brain._try_llm_routing()` uses `ProviderRegistry.get_llm_with_fallback()` instead of single-provider. Try configured chain (e.g., `groq -> ollama -> openai`). VoxAgent already has `get_llm_with_fallback()` in registry -- it's just never called. |
| 3.2 | **TTS fallback chain** | Table Stakes | Medium | If primary TTS fails (e.g., Edge TTS network error), fall back to next (e.g., Piper local). User hears response in degraded voice quality rather than silence. |
| 3.3 | **STT fallback chain** | Table Stakes | Medium | If cloud Whisper fails, fall back to local `faster-whisper`. User's speech is still transcribed, possibly with lower accuracy. |
| 3.4 | **Circuit breaker per provider** | Table Stakes | Medium | After N consecutive failures (default: 3) within a window (default: 60s), mark provider as "open" (unhealthy). Skip it in the chain. Probe it after a cool-down (default: 30s). States: `CLOSED` (healthy) -> `OPEN` (failing) -> `HALF_OPEN` (probing). |
| 3.5 | **Retry with exponential backoff** | Table Stakes | Low | Transient failures (HTTP 429, 503, timeouts) are retried with exponential backoff: 1s, 2s, 4s, max 3 retries. Permanent failures (401, 403) are not retried. |
| 3.6 | **Provider health dashboard indicator** | Differentiator | Low | Dashboard shows real-time health status per provider (green/yellow/red). Users can see which providers are healthy/degraded/down. |
| 3.7 | **Graceful degradation announcements** | Differentiator | Low | When falling back to a lower-quality provider, optionally inform the user: "Using local model, responses may be slower." Configurable verbosity. |
| 3.8 | **Connection pooling (shared httpx client)** | Table Stakes | Low | Single `httpx.AsyncClient` per provider with connection pooling and keep-alive. Currently, every API call creates a new client (adding 50-200ms latency). |
| 3.9 | **Cross-provider request hedging** | Anti-Feature | High | Send same request to multiple providers simultaneously, use first response. Wastes API credits and complicates cancellation. Not appropriate for a personal assistant with cost sensitivity. |

### Dependencies
- 3.1 depends on: 3.4 (circuit breaker) to avoid repeatedly trying known-bad providers
- 3.2 depends on: Provider abstraction already exists (`TTSProvider` ABC)
- 3.3 depends on: Provider abstraction already exists (`STTProvider` ABC)
- 3.4 depends on: 3.8 (connection pooling) to make health probes cheap
- 3.5 is independent, can be implemented first

### VoxAgent Current State
- `ProviderRegistry.get_llm_with_fallback()` EXISTS but `Brain._try_llm_routing()` never calls it
- No TTS or STT fallback -- single provider per type
- No retry logic anywhere in the codebase
- No circuit breaker pattern
- Every HTTP call creates a new `httpx.AsyncClient` (CONCERNS.md 3.1)
- Provider health checks make real API calls with `"ping"` message (expensive, slow)

---

## 4. Error Recovery & User-Facing Error Patterns

### Context

Silent failures are the worst UX for a voice assistant. The user says something, nothing happens, and they don't know if the assistant heard them, is processing, or failed. Production assistants ALWAYS communicate state.

### How Production Assistants Handle It

**Alexa:**
- Light ring color indicates state: blue (listening), cyan (processing), red (error/muted), orange (connectivity issue).
- Verbal error messages are specific: "I'm having trouble connecting to the internet" vs "I didn't understand that" vs "I don't know how to do that."
- Never silent. Even on catastrophic failure, plays an error earcon (sound).

**Google Home:**
- Similar visual indicators (LED ring patterns).
- Categorized error responses: "I can't reach Google right now", "I don't know how to help with that", "Something went wrong."
- Automatic retry for transient failures -- user never sees them.

**Siri:**
- Always responds, even if the response is "I'm not sure about that."
- Connectivity errors surface as "I'm having trouble connecting. Please check your internet."

### Error Taxonomy for Voice Assistants

| Error Type | User Impact | Correct Response |
|-----------|-------------|------------------|
| **Transient network failure** | Temporary, auto-recoverable | Retry silently (max 2x), then speak error. User never sees transient failures. |
| **Provider down** | Extended outage | Fall back to alternative, inform if quality degrades. |
| **STT failure** | Couldn't hear user | "I didn't catch that. Could you say it again?" |
| **Intent not understood** | Couldn't parse command | "I'm not sure what you'd like me to do. Could you rephrase that?" |
| **Skill execution failure** | Action failed | Specific error: "I couldn't open Chrome -- it's not installed" not "Something went wrong." |
| **Permission denied** | Dangerous action blocked | "That action requires confirmation. Should I proceed?" (already exists in VoxAgent) |
| **Configuration error** | Missing API key, misconfigured provider | "I need an API key for OpenAI. You can add one in the dashboard." |
| **Internal bug** | Unexpected exception | "Something unexpected happened. I've logged the details." + earcon. |

### Features

| # | Feature | Category | Complexity | Description |
|---|---------|----------|------------|-------------|
| 4.1 | **Custom error hierarchy** | Table Stakes | Medium | `VoxAgentError` base class with subclasses: `ProviderError`, `SkillError`, `AudioError`, `ConfigError`, `SecurityError`. Each carries severity (TRANSIENT, DEGRADED, FATAL), user-facing message, and technical detail. Replaces bare `Exception` catches throughout. |
| 4.2 | **User-facing error messages (spoken)** | Table Stakes | Low | Every error path produces a TTS-friendly message. No silent failures. Error messages are specific to the failure type (see taxonomy above). |
| 4.3 | **Error earcon (audio cue)** | Table Stakes | Low | Short distinctive sound played on error, before the spoken error message. Gives immediate audio feedback that something went wrong. `mouth.py` already has a `play_earcon()` stub. |
| 4.4 | **State earcons (processing, success)** | Differentiator | Low | Audio cues for state transitions: "listening" boop, "processing" tone, "done" chime. Provides non-verbal progress feedback. Alexa's light ring, but in audio. |
| 4.5 | **Aggregate health reporting** | Differentiator | Medium | System knows which modules are degraded and can report overall health. "Your local STT is running but cloud LLM is unreachable. Using local model." Feeds into dashboard (3.6). |
| 4.6 | **Structured error logging** | Table Stakes | Low | All errors logged with structured context: `{error_type, provider, skill, user_command, timestamp, retry_count}`. Enables debugging and pattern detection. |
| 4.7 | **Standardized SkillResult error pattern** | Table Stakes | Low | All skills use consistent `SkillResult(success=False, error=<technical>, tts_response=<user-facing>)`. No more partial error information (CONCERNS.md 7.4). |
| 4.8 | **Automatic error trend detection** | Anti-Feature | High | ML-based detection of error patterns. Over-engineering. Structured logging (4.6) with manual review is sufficient. |

### Dependencies
- 4.1 is foundational -- almost everything else depends on it
- 4.2 depends on: 4.1 (errors carry user-facing messages)
- 4.3 depends on: Audio file assets (earcon sounds), low-latency playback
- 4.5 depends on: 3.4 (circuit breaker state), 4.1 (error hierarchy)
- 4.7 is independent, can be done as a refactor pass

### VoxAgent Current State
- Silent failures throughout (CONCERNS.md 4.4): Eyes returns empty on failure, Mouth logs and returns, STT returns None
- Three different SkillResult error patterns (CONCERNS.md 7.4)
- `mouth.py:play_earcon()` is a TODO stub
- Two separate `ProviderNotFoundError` classes (CONCERNS.md 2.8)
- Broad `except Exception` catches (CONCERNS.md 4.1)
- No structured error logging

---

## 5. Audio Resilience

### Context

Audio is the most failure-prone part of a voice assistant. Microphone quirks, background noise, the assistant's own TTS output being picked up by the mic (echo), network-degraded audio -- all must be handled robustly.

### How Production Assistants Handle It

**Alexa / Google Home (hardware):**
- Dedicated DSP (Digital Signal Processor) for Acoustic Echo Cancellation (AEC), beam-forming (multi-mic), and noise suppression.
- 7+ microphone array with far-field beam-forming for directional pickup.
- Hardware AEC reference signal from the speaker output, ensuring the mic never "hears" the assistant.

**Software-based assistants (Mycroft/OVOS, Rhasspy):**
- Software AEC via `speexdsp` or WebRTC's `AudioProcessing` module.
- Require a "loopback" reference signal (what the speaker is playing) to subtract from mic input.
- Silero VAD with adaptive thresholds based on ambient noise levels.
- WebRTC's noise suppression (NS) removes stationary noise (fan, AC).

**Common VAD patterns:**
- Adaptive energy threshold: baseline noise level measured during silence, speech threshold set at baseline + margin.
- Silero VAD confidence with hysteresis: start-of-speech threshold (0.5) is higher than end-of-speech threshold (0.3) to avoid cutting off trailing words.
- Timeout-based end-of-speech: after 1.5-2s of silence following speech, consider utterance complete.

### Features

| # | Feature | Category | Complexity | Description |
|---|---------|----------|------------|-------------|
| 5.1 | **TTS-output muting (simple AEC)** | Table Stakes | Low | Mute or suppress mic input while TTS is playing. Simplest approach: set a flag `is_speaking` that makes the wake word detector and VAD ignore audio. Prevents Whisper from transcribing VoxAgent's own speech. |
| 5.2 | **Software AEC (speexdsp/WebRTC)** | Differentiator | High | True echo cancellation using speaker output as reference signal. Allows wake word detection during TTS (enabling full-duplex barge-in 1.4). Requires platform-specific audio routing to capture the loopback signal. |
| 5.3 | **Noise suppression (WebRTC NS)** | Differentiator | Medium | Stationary noise removal (fan, AC, street noise) from mic input before STT. Improves transcription accuracy in noisy environments. Can use `py-webrtcvad` or `noisereduce` library. |
| 5.4 | **Adaptive VAD thresholds** | Table Stakes | Medium | Measure ambient noise during idle periods, adjust VAD sensitivity accordingly. Quiet room: lower threshold. Noisy room: higher threshold. Prevents phantom activations in noisy environments and missed activations in quiet ones. |
| 5.5 | **VAD hysteresis (start/end thresholds)** | Table Stakes | Low | Use higher confidence for speech start (0.5) vs speech end (0.35). Prevents premature end-of-utterance detection on brief pauses within a sentence. |
| 5.6 | **Audio queue backpressure** | Table Stakes | Low | Bounded audio queue (max ~500 chunks = ~40s at 80ms/chunk). If STT processing stalls, drop oldest chunks rather than accumulating unbounded memory. Log warning on drops. (CONCERNS.md 3.6) |
| 5.7 | **Audio pipeline health monitoring** | Differentiator | Low | Detect mic disconnection, zero-signal (muted mic), or clipping. Notify user: "Your microphone seems to be muted" or "I can't detect your microphone." |
| 5.8 | **Multi-mic beam-forming** | Anti-Feature | Very High | Requires multiple microphones and DSP algorithms. Desktop PCs/laptops have single mics or stereo at best. Not practical for software-only solution. |
| 5.9 | **Audio format normalization** | Table Stakes | Low | Ensure consistent sample rate (16kHz), bit depth (16-bit), and channel count (mono) regardless of input device. Prevents STT failures from mismatched audio formats. |

### Dependencies
- 5.1 is prerequisite for 1.1 (wake-word barge-in) -- without it, the assistant transcribes itself
- 5.2 is prerequisite for 1.4 (full-duplex barge-in) -- marked anti-feature, so 5.2 becomes optional
- 5.3 is independent, can be added to audio pipeline at any time
- 5.4 depends on: ambient noise measurement infrastructure
- 5.6 is independent, trivial fix

### VoxAgent Current State
- No echo cancellation of any kind -- Whisper WILL transcribe VoxAgent's own TTS output
- VAD uses fixed Silero threshold (0.5) with energy fallback (fixed 500.0 RMS threshold)
- No noise suppression
- Audio queue is unbounded (`asyncio.Queue()` with no maxsize)
- No audio health monitoring
- Audio format is hardcoded to 16kHz mono int16 (correct for Whisper, good)

---

## 6. Progress Feedback

### Context

Some actions take time: installing software, downloading files, running complex queries. Without feedback, users assume the assistant froze. Voice assistants need progress indication equivalent to a loading spinner.

### How Production Assistants Handle It

**Alexa:**
- Pulsing blue light ring during processing.
- For long-running skills: "Working on that..." spoken, then silence with pulsing light, then result.
- Skills can send "progressive response" updates: "I found the recipe. Let me get the details..."

**Google Home:**
- Thinking dots animation on screen-based devices.
- Spoken acknowledgment for long tasks: "Sure, let me check on that..."
- Background task completion: chimes when done, even if user walked away.

**Common patterns:**
1. **Acknowledgment** (<500ms): Immediate audio cue confirming command received.
2. **Progress update** (2-5s): "Working on that..." if task takes longer than expected.
3. **Completion notification**: Result or "Done" when finished.
4. **Background task notification**: Chime + "Your download is complete" for tasks that take >30s.

### Features

| # | Feature | Category | Complexity | Description |
|---|---------|----------|------------|-------------|
| 6.1 | **Immediate acknowledgment earcon** | Table Stakes | Low | Play a short acknowledgment sound immediately after STT completes and before Brain processing begins. Tells user "I heard you, thinking..." |
| 6.2 | **Timeout-based progress update** | Table Stakes | Low | If Brain/Hands takes >3s, speak "Working on that..." Uses a simple `asyncio.wait_for` with a timeout trigger. |
| 6.3 | **Skill-level progress callbacks** | Differentiator | Medium | Skills can emit progress events: `yield SkillProgress(message="Downloading... 50%")`. Long-running skills like terminal commands or file operations report incremental status. |
| 6.4 | **Background task completion notification** | Differentiator | Medium | For tasks taking >30s, move to background, let user continue interacting, and notify when done. Requires task manager (autopilot already exists). |
| 6.5 | **Dashboard real-time progress** | Differentiator | Medium | WebSocket from backend to dashboard showing current pipeline state: `LISTENING -> STT -> THINKING -> EXECUTING -> SPEAKING`. Real-time skill progress for long-running tasks. |
| 6.6 | **Detailed verbal progress for multi-step plans** | Anti-Feature | Medium | "Step 1 of 3: Opening Chrome. Step 2 of 3: Navigating to Google." Annoying for simple tasks. The planner already returns step lists; narrating each one adds latency and verbosity. A single acknowledgment is sufficient. |

### Dependencies
- 6.1 depends on: Earcon playback (4.3)
- 6.2 is independent (simple timeout wrapper)
- 6.3 depends on: Streaming playback (2.2) to speak progress without blocking
- 6.4 depends on: `autopilot.py` task infrastructure (already exists)
- 6.5 depends on: WebSocket added to FastAPI server

### VoxAgent Current State
- Zero progress feedback -- complete silence between command and response
- `mouth.py:play_earcon()` is a TODO stub
- Autopilot exists but is not connected to the voice pipeline for background tasks
- No WebSocket communication between backend and dashboard

---

## 7. Safety & Security (Execution Hardening)

### Context

VoxAgent executes real system commands -- it can delete files, run terminal commands, control applications. Production assistants sandbox execution and validate commands semantically, not just syntactically.

### How Production Assistants Handle It

**Alexa Skills:**
- Skills run in sandboxed Lambda functions with IAM policies limiting AWS resource access.
- No direct system access -- skills communicate through defined APIs.
- Skill certification review before publication (human + automated).

**Google Assistant Actions:**
- Sandboxed Cloud Functions with constrained permissions.
- Fulfillment endpoints have strict request validation.
- Conversational safety filters on input and output.

**Desktop assistants (unique challenge):**
- Desktop agents MUST have system access (that's the point).
- Mitigation is layered: (1) intent validation, (2) permission checks, (3) command sanitization, (4) execution sandboxing, (5) undo capability.

### Features

| # | Feature | Category | Complexity | Description |
|---|---------|----------|------------|-------------|
| 7.1 | **Terminal command AST validation** | Table Stakes | Medium | Parse shell commands into AST (using `shlex` + `ast` for Python, `bashlex` for bash). Validate against allow-list at the AST level, not regex. Catches `python -c "os.system('rm -rf /')"` that regex misses. (CONCERNS.md 1.5) |
| 7.2 | **File operation sandboxing** | Table Stakes | Medium | File manager operations restricted to configurable safe directories (default: user home, downloads, documents). `Path.resolve()` is checked against the jail before ANY operation. (CONCERNS.md 1.4) |
| 7.3 | **Type-safe parameter extraction from LLM** | Table Stakes | Medium | Validate and coerce LLM tool call parameters against expected types (Pydantic models per skill). Prevents type confusion attacks and catches malformed LLM output. |
| 7.4 | **PromptGuard integration into Brain** | Table Stakes | Low | Wire existing `safety.py:PromptGuard` into `brain.py:process()` BEFORE any LLM call. It exists, it's tested, it's just never called. (CONCERNS.md 1.2) |
| 7.5 | **Dangerous command confirmation with detail** | Differentiator | Low | Enhance existing permission system: when confirming dangerous actions, speak WHAT will be done: "I'm about to delete the folder Documents/old-project. Should I continue?" not just "This is a dangerous action." |
| 7.6 | **Execution timeout per skill** | Table Stakes | Low | Skills have a max execution time (configurable, default: 30s). Long-running skills can opt into extended timeouts. Prevents hung skills from blocking the pipeline. |
| 7.7 | **Idempotent cleanup on failure** | Differentiator | Medium | Skills that perform multi-step operations (e.g., "move file then delete source") implement rollback on partial failure. Uses OpenClaw's idempotent cleanup pattern. |
| 7.8 | **Memory DB bounded growth** | Table Stakes | Low | Conversation history capped at configurable limit (default: 10,000 entries). FIFO cleanup policy. Preferences and skill state are not capped (small footprint). (PROJECT.md active requirement) |
| 7.9 | **Marketplace code signing** | Table Stakes | Medium | Remote skill installs require cryptographic signature verification. Unsigned skills are rejected. (CONCERNS.md 1.1 -- currently a critical RCE vulnerability) |
| 7.10 | **API server authentication** | Table Stakes | Low | Management API requires API key authentication, even on localhost. Default to requiring auth, not opt-in. (CONCERNS.md 1.3) |
| 7.11 | **Full process sandboxing (containers/seccomp)** | Anti-Feature | Very High | Running skills in isolated containers or seccomp sandboxes. Massively over-complicated for a personal desktop agent. The permission system + AST validation + file sandboxing provides sufficient protection. |
| 7.12 | **AI-based command risk scoring** | Anti-Feature | High | Using an LLM to evaluate if commands are "safe." Circular dependency (LLM evaluating LLM output), adds latency, and is unreliable. Deterministic validation (AST, sandboxing, permissions) is superior. |

### Dependencies
- 7.1 is independent
- 7.2 is independent
- 7.3 depends on: Pydantic models defined per skill action
- 7.4 is independent (just wiring)
- 7.6 is independent
- 7.8 is independent
- 7.9 should block marketplace feature until implemented
- 7.10 is independent

### VoxAgent Current State
- Terminal uses regex-based allowlist that's easily bypassed (CONCERNS.md 1.5)
- File manager has no sandboxing (CONCERNS.md 1.4)
- PromptGuard exists but is never called (CONCERNS.md 1.2)
- Permission system works but gives generic confirmation messages
- No execution timeouts on skills
- Memory DB has no size limits
- Marketplace downloads arbitrary Python code (CONCERNS.md 1.1)
- API server has no auth by default (CONCERNS.md 1.3)

---

## Summary Matrix

### Table Stakes (Must Have)

| # | Feature | Complexity | Blocks |
|---|---------|------------|--------|
| 1.1 | Wake-word barge-in | Medium | 5.1 |
| 1.2 | Audio fade-out on interrupt | Low | 2.2 |
| 1.3 | Cancel in-flight TTS | Low | -- |
| 1.5 | Barge-in state machine | Medium | 1.1, 1.2, 1.3 |
| 2.1 | Sentence-level text chunking | Low | -- |
| 2.2 | Chunked audio playback with queue | Medium | -- |
| 2.3 | Edge TTS streaming consumption | Low | 2.2 |
| 2.5 | Pre-buffer with playback threshold | Low | 2.2 |
| 3.1 | LLM fallback chain (Brain wiring) | Medium | 3.4 |
| 3.2 | TTS fallback chain | Medium | -- |
| 3.3 | STT fallback chain | Medium | -- |
| 3.4 | Circuit breaker per provider | Medium | 3.8 |
| 3.5 | Retry with exponential backoff | Low | -- |
| 3.8 | Connection pooling (shared httpx) | Low | -- |
| 4.1 | Custom error hierarchy | Medium | -- |
| 4.2 | User-facing error messages | Low | 4.1 |
| 4.3 | Error earcon | Low | -- |
| 4.6 | Structured error logging | Low | 4.1 |
| 4.7 | Standardized SkillResult errors | Low | -- |
| 5.1 | TTS-output muting (simple AEC) | Low | -- |
| 5.4 | Adaptive VAD thresholds | Medium | -- |
| 5.5 | VAD hysteresis | Low | -- |
| 5.6 | Audio queue backpressure | Low | -- |
| 5.9 | Audio format normalization | Low | -- |
| 6.1 | Immediate acknowledgment earcon | Low | 4.3 |
| 6.2 | Timeout-based progress update | Low | -- |
| 7.1 | Terminal AST validation | Medium | -- |
| 7.2 | File operation sandboxing | Medium | -- |
| 7.3 | Type-safe parameter extraction | Medium | -- |
| 7.4 | PromptGuard integration | Low | -- |
| 7.6 | Execution timeout per skill | Low | -- |
| 7.8 | Memory DB bounded growth | Low | -- |
| 7.9 | Marketplace code signing | Medium | -- |
| 7.10 | API server authentication | Low | -- |

**Count: 33 features | ~18 Low, ~12 Medium, 0 High**

### Differentiators (Competitive Advantage)

| # | Feature | Complexity | Why Differentiating |
|---|---------|------------|---------------------|
| 2.4 | ElevenLabs streaming API | Medium | Best-in-class voice quality with real-time latency |
| 2.6 | LLM token streaming to TTS | Medium | Parallelizes LLM generation and TTS -- noticeably faster than competitors |
| 3.6 | Provider health dashboard | Low | Visibility into system state -- open-source assistants lack this |
| 3.7 | Graceful degradation announcements | Low | User always knows system state -- transparency builds trust |
| 4.4 | State earcons | Low | Non-verbal feedback loop makes assistant feel "alive" |
| 4.5 | Aggregate health reporting | Medium | System self-awareness, reports its own degraded state |
| 5.2 | Software AEC (speexdsp) | High | Enables true full-duplex, but only if 1.4 is reconsidered |
| 5.3 | Noise suppression | Medium | Better transcription in noisy environments |
| 5.7 | Audio pipeline health monitoring | Low | Detects mic issues before user gets frustrated |
| 6.3 | Skill progress callbacks | Medium | Long-running tasks report incremental status |
| 6.4 | Background task completion | Medium | User can continue while tasks run |
| 6.5 | Dashboard real-time progress | Medium | Live pipeline state in the dashboard |
| 7.5 | Detailed dangerous-action confirmation | Low | Speaks WHAT will happen, not generic warning |
| 7.7 | Idempotent cleanup on failure | Medium | Rollback on partial multi-step failure |

**Count: 14 features | ~5 Low, ~7 Medium, ~1 High**

### Anti-Features (Do NOT Build)

| # | Feature | Complexity | Why NOT |
|---|---------|------------|---------|
| 1.4 | Full-duplex barge-in | Very High | Requires production AEC hardware or very complex software AEC. Wake-word barge-in (1.1) is sufficient for desktop. |
| 2.7 | Adaptive chunk sizing | Medium | Over-engineering. Desktop networks are stable. Fixed sentence-level chunking works. |
| 3.9 | Cross-provider request hedging | High | Wastes API credits for marginal latency improvement. Fallback chain (3.1) is sufficient. |
| 4.8 | Automatic error trend detection | High | ML-based error analysis. Structured logging (4.6) with manual review is sufficient. |
| 5.8 | Multi-mic beam-forming | Very High | Hardware-dependent. Desktop PCs have single mics. Not a software problem. |
| 6.6 | Verbose multi-step narration | Medium | Annoying. "Step 1 of 3..." adds latency and verbosity to simple commands. |
| 7.11 | Full process sandboxing | Very High | Containers/seccomp for desktop automation is contradictory. Permission system + AST validation is the right granularity. |
| 7.12 | AI-based command risk scoring | High | Circular LLM-evaluating-LLM dependency. Deterministic validation is more reliable. |

**Count: 8 features**

---

## Recommended Implementation Order

Based on dependency analysis, impact, and complexity:

### Phase 1: Foundation (unblocks everything else)
1. **3.8** Connection pooling (shared httpx) -- Low, unblocks 3.4
2. **4.1** Custom error hierarchy -- Medium, unblocks 4.2/4.6/4.5
3. **3.5** Retry with exponential backoff -- Low, independent
4. **5.1** TTS-output muting -- Low, unblocks 1.1
5. **4.7** Standardized SkillResult errors -- Low, independent
6. **7.4** PromptGuard integration -- Low, independent (just wiring)

### Phase 2: Streaming & Fallback (biggest user-facing impact)
7. **2.1** Sentence-level text chunking -- Low
8. **2.2** Chunked audio playback with queue -- Medium, unblocks 2.3/2.5/1.2
9. **2.3** Edge TTS streaming -- Low
10. **2.5** Pre-buffer with playback threshold -- Low
11. **3.4** Circuit breaker -- Medium
12. **3.1** LLM fallback chain wiring -- Medium
13. **3.2** TTS fallback chain -- Medium
14. **3.3** STT fallback chain -- Medium

### Phase 3: Barge-In & Feedback
15. **1.2** Audio fade-out -- Low
16. **1.1** Wake-word barge-in -- Medium
17. **1.3** Cancel in-flight TTS -- Low
18. **1.5** Barge-in state machine -- Medium
19. **4.3** Error earcon -- Low
20. **6.1** Acknowledgment earcon -- Low
21. **6.2** Timeout progress update -- Low
22. **4.2** User-facing error messages -- Low

### Phase 4: Hardening & Safety
23. **5.4** Adaptive VAD thresholds -- Medium
24. **5.5** VAD hysteresis -- Low
25. **5.6** Audio queue backpressure -- Low
26. **7.1** Terminal AST validation -- Medium
27. **7.2** File operation sandboxing -- Medium
28. **7.3** Type-safe parameter extraction -- Medium
29. **7.6** Execution timeout per skill -- Low
30. **7.8** Memory DB bounded growth -- Low
31. **7.10** API server auth -- Low
32. **7.9** Marketplace code signing -- Medium
33. **5.9** Audio format normalization -- Low

---

## Key Insight

The single highest-impact change is **streaming TTS (2.1 + 2.2 + 2.3 + 2.5)**. It transforms VoxAgent from "say something, wait 3 seconds, hear response" to "say something, hear response in <500ms." This is more noticeable to users than any other improvement. Combined with **connection pooling (3.8)** which removes 50-200ms per API call, first-response latency drops from 3-8 seconds to under 1.5 seconds.

The second highest-impact change is **barge-in (1.1 + 1.5 + 5.1)**. Without it, users are held hostage to the assistant's full response before they can interact again. This is the #1 complaint about prototype voice assistants.

Everything else (fallback, error handling, safety) prevents bad experiences but doesn't create good ones. They're essential but invisible when working correctly.
