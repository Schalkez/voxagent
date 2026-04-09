# Resilience Architecture Research

Research for hardening VoxAgent's voice pipeline. Covers six architectural dimensions with component boundaries, data flow, and build order implications.

---

## 1. Audio Pipeline Architecture (Backpressure & Frame Integrity)

### Problem in Current Codebase

`AudioRecorder._on_audio_chunk` silently drops frames via `contextlib.suppress(asyncio.QueueFull)` on an unbounded-then-silently-dropped queue. The `asyncio.Queue()` has no maxsize, so `QueueFull` never fires today — but if a consumer stalls (e.g., STT takes 3 seconds), chunks accumulate in memory unbounded. And if we add a maxsize, chunks drop silently with no metrics, no logging, and no recovery.

### Target Architecture

```
                          ┌─────────────────────────────────────┐
                          │          AudioPipeline              │
                          │  (owns lifecycle, wires stages)     │
                          └──────────┬──────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
         v                           v                           v
 ┌──────────────┐          ┌──────────────────┐        ┌─────────────────┐
 │ AudioRecorder│          │  AudioRingBuffer  │        │  ChunkConsumer  │
 │  (producer)  │─chunks──>│  (bounded, lock-  │─read──>│  (WakeWord/VAD  │
 │              │          │   free circular)  │        │   /STT dispatch)│
 └──────────────┘          └──────────────────┘        └─────────────────┘
                                     │
                                     v
                            ┌──────────────┐
                            │ DropCounter  │
                            │ (metrics +   │
                            │  log every N)│
                            └──────────────┘
```

### Components

| Component | Boundary | Responsibility |
|-----------|----------|----------------|
| `AudioRecorder` | Producer. Owns sounddevice stream. Writes chunks. | Opens mic, pushes int16 frames at 16kHz/80ms. Never blocks in callback. |
| `AudioRingBuffer` | Bounded buffer between producer and consumer. | Fixed-size circular buffer (e.g., 128 slots = ~10s). Overwrites oldest on full. Tracks drop count. Lock-free for single-producer/single-consumer. |
| `ChunkConsumer` | Consumer. Reads at its own pace. | Pulls chunks, feeds to WakeWord/VAD/AEC. Adapts read rate to processing speed. |
| `DropCounter` | Metrics. Observable. | Increments on overwrite. Logs warning every N drops. Exposes count to dashboard via API. |

### Data Flow

```
sounddevice callback (C thread, real-time)
    │
    │  write_nowait(chunk)  ← MUST NOT BLOCK, MUST NOT ALLOCATE
    v
AudioRingBuffer (pre-allocated numpy array, write pointer wraps)
    │
    │  async read() with asyncio.Event notification
    v
ChunkConsumer (asyncio task, Python thread)
    │
    ├── WakeWordDetector.detect(chunk)
    ├── VoiceActivityDetector.detect_speech(chunk)
    └── AEC.filter(chunk)  (see Section 5)
```

### Design Rules

1. **Sounddevice callback is real-time**: No allocations, no locks, no I/O, no logging. Current code calls `indata.copy()` which allocates — replace with pre-allocated ring buffer slots.
2. **Ring buffer, not queue**: `asyncio.Queue` is wrong for audio. A ring buffer overwrites stale audio (correct behavior — old audio is worthless). A queue either drops or blocks (both wrong).
3. **Backpressure metric, not backpressure enforcement**: Audio is a push source. You cannot tell the microphone to slow down. The only correct response to consumer lag is: (a) drop oldest frames, (b) count drops, (c) alert if drop rate exceeds threshold.
4. **Pre-allocate all buffers**: Ring buffer slots are pre-allocated numpy arrays. The callback copies into the next slot via `np.copyto(slot, indata)` — no allocation.
5. **Separation of notification from data**: Use `asyncio.Event` to wake the consumer. The consumer reads from the ring buffer directly — the event is just a signal.

### Build Order Implications

- `AudioRingBuffer` is a standalone data structure — build first, test in isolation.
- `DropCounter` is a simple counter — build alongside ring buffer.
- `AudioRecorder` refactor depends on `AudioRingBuffer`.
- `ChunkConsumer` is the orchestrator — depends on ring buffer + existing WakeWord/VAD.
- **No dependency on AEC, TTS, or providers.** Can be built in Phase 1.

---

## 2. TTS Streaming Architecture (Chunked Synthesis + Interruption)

### Problem in Current Codebase

`Mouth.speak()` calls `TTSProvider.synthesize()` which returns the entire WAV as a single `bytes` blob, then `_play_wav()` plays it blocking via `sd.play() + sd.wait()` in a thread. Three problems:

1. **First-word latency**: User waits for full synthesis before hearing anything. For a 30-word response, that's 2-5 seconds of silence.
2. **No interruption**: Once `sd.play()` is called, there's no way to stop it. If the user says "Hey Vox" mid-response, the TTS plays to completion.
3. **Blocks the pipeline**: `asyncio.to_thread(_play_blocking)` blocks one thread for the entire duration. The main loop cannot process new commands until playback finishes.

### Target Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                          StreamingMouth                              │
│  (orchestrator: owns playback lifecycle + interruption)             │
└─────────────┬──────────────────┬─────────────────┬──────────────────┘
              │                  │                 │
              v                  v                 v
   ┌──────────────────┐  ┌──────────────┐  ┌───────────────────┐
   │ TTSChunkProducer │  │ PlaybackQueue│  │ InterruptController│
   │ (async generator │  │ (bounded     │  │ (asyncio.Event +   │
   │  of WAV chunks)  │  │  asyncio.Q)  │  │  cancellation)     │
   └──────────────────┘  └──────────────┘  └───────────────────┘
              │                  │                 │
              │   put(chunk)     │   get(chunk)    │  set() to abort
              v                  v                 v
         ┌─────────────────────────────────────────────┐
         │              PlaybackWorker                  │
         │  (sounddevice OutputStream, chunk-by-chunk)  │
         │  Checks InterruptController before each chunk│
         └─────────────────────────────────────────────┘
```

### Components

| Component | Boundary | Responsibility |
|-----------|----------|----------------|
| `StreamingMouth` | Orchestrator. Replaces current `Mouth`. | Accepts text, starts chunked synthesis, manages playback lifecycle, exposes `interrupt()`. |
| `TTSChunkProducer` | Async generator. Wraps `TTSProvider`. | Calls provider's streaming API (or splits text into sentences and synthesizes each). Yields WAV chunks as they're ready. |
| `PlaybackQueue` | Bounded `asyncio.Queue[bytes \| None]`. | Decouples synthesis rate from playback rate. `None` sentinel signals end-of-stream. Max 3-5 chunks to limit memory. |
| `PlaybackWorker` | Consumer. Owns `sounddevice.OutputStream`. | Reads chunks from queue, writes to output stream. Checks interrupt flag before each chunk write. |
| `InterruptController` | Shared cancellation primitive. | `asyncio.Event` that signals "stop everything". Checked by both producer (stop synthesizing) and worker (stop playing). |

### Data Flow

```
"Đã mở Chrome rồi nha. Có gì cần thêm không?"
    │
    │  split into sentences (or provider streams natively)
    v
TTSChunkProducer
    │  yields: [chunk1: "Đã mở Chrome rồi nha."] [chunk2: "Có gì cần thêm không?"]
    │          WAV bytes per sentence/phrase
    v
PlaybackQueue (maxsize=3)
    │
    │  PlaybackWorker reads, checks interrupt, plays
    v
sounddevice.OutputStream.write(chunk_pcm)
    │
    v
Speaker

--- INTERRUPT PATH ---

User says "Hey Vox" during playback
    │
    │  WakeWordDetector fires (Ears is listening concurrently, see Section 6)
    v
InterruptController.set()
    │
    ├── PlaybackWorker: stops writing, flushes OutputStream, breaks loop
    ├── TTSChunkProducer: stops yielding, cancels any in-flight API call
    └── PlaybackQueue: drained
    │
    v
StreamingMouth.interrupt() returns, pipeline is clean
```

### TTSProvider Interface Extension

The current `TTSProvider.synthesize()` returns `bytes`. For streaming, add an optional method:

```python
class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, ...) -> bytes:
        """Full synthesis (existing, backward-compatible)."""

    async def synthesize_stream(self, text: str, ...) -> AsyncIterator[bytes]:
        """Stream synthesis in chunks. Default: falls back to full synthesis."""
        yield await self.synthesize(text, ...)
```

This keeps backward compatibility. Providers that support native streaming (ElevenLabs, OpenAI) override `synthesize_stream`. Others get automatic sentence-splitting fallback.

### Text Splitting Strategy

For providers without native streaming:
1. Split on sentence boundaries (`.`, `!`, `?`, Vietnamese sentence-final particles).
2. Minimum chunk: 5 words (avoid choppy single-word synthesis).
3. Maximum chunk: 1 sentence (keeps latency low).
4. Synthesize chunks concurrently (up to 2 in-flight requests).

### Build Order Implications

- `InterruptController` is standalone — build first.
- `PlaybackWorker` depends on `InterruptController` + sounddevice.
- `TTSChunkProducer` depends on `TTSProvider` interface extension.
- `StreamingMouth` depends on all above.
- **Depends on Section 6 (Concurrent Audio)** for barge-in to actually work — the microphone must be listening during playback.
- **Depends on Section 5 (AEC)** to prevent the mic from hearing its own TTS output.

---

## 3. Provider Fallback Architecture (Circuit Breaker + Health Checks)

### Problem in Current Codebase

`ProviderRegistry.get_llm_with_fallback()` iterates the chain and calls `health_check()` on each provider. Three problems:

1. **No circuit breaker**: If OpenAI is down, every single request tries OpenAI first, waits for the timeout, then falls back. This adds latency to every request during an outage.
2. **LLM-only fallback**: `get_llm_with_fallback()` exists but there's no equivalent for STT or TTS. If Edge TTS goes down, the whole pipeline fails.
3. **No health check caching**: `health_check()` makes a real network call each time. For cloud providers, that's 200-500ms added to every request.

### Target Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      ResilientRegistry                           │
│  (extends ProviderRegistry with circuit breakers per provider)   │
└──────────┬─────────────────────┬─────────────────┬──────────────┘
           │                     │                 │
           v                     v                 v
    ┌──────────────┐     ┌──────────────┐   ┌──────────────┐
    │CircuitBreaker│     │CircuitBreaker│   │CircuitBreaker│
    │  (openai)    │     │  (groq)      │   │  (edge_tts)  │
    └──────┬───────┘     └──────┬───────┘   └──────┬───────┘
           │                     │                 │
           v                     v                 v
    ┌──────────────┐     ┌──────────────┐   ┌──────────────┐
    │ OpenAI LLM   │     │ Groq LLM     │   │ Edge TTS     │
    │  Provider    │     │  Provider    │   │  Provider    │
    └──────────────┘     └──────────────┘   └──────────────┘

         ┌──────────────────────────────────┐
         │       HealthCheckScheduler       │
         │  (background task, periodic)     │
         │  Probes all registered providers │
         │  every HEALTH_CHECK_INTERVAL_S   │
         └──────────────────────────────────┘
```

### Components

| Component | Boundary | Responsibility |
|-----------|----------|----------------|
| `CircuitBreaker` | Per-provider state machine. | Tracks failures. States: CLOSED (healthy) -> OPEN (broken, fast-fail) -> HALF_OPEN (probing). Configurable thresholds. |
| `ResilientRegistry` | Extends `ProviderRegistry`. | Wraps every provider call with its circuit breaker. Falls back to next provider when breaker is OPEN. |
| `HealthCheckScheduler` | Background asyncio task. | Periodically probes all registered providers. Transitions breakers from OPEN to HALF_OPEN after cooldown. |
| `FallbackChain` | Per-type ordered list. | Separate chains for LLM, STT, TTS, Vision. Each chain is iterated until a healthy provider is found. |
| `ProviderMetrics` | Observable counters. | Tracks per-provider: request count, failure count, avg latency, circuit state. Exposed to dashboard. |

### Circuit Breaker State Machine

```
          success
    ┌───────────────┐
    │               │
    v               │
 CLOSED ──────> OPEN ──(cooldown expires)──> HALF_OPEN
    ^            │                              │
    │            │ (fail_count >= threshold)     │
    │            │                              │
    │            └──────────────────────────────┘
    │                   probe fails → back to OPEN
    │                   probe succeeds → back to CLOSED
    └──────────────────────────────────────────────
```

### Configuration Constants

```python
FAILURE_THRESHOLD: int = 3          # failures before OPEN
RECOVERY_TIMEOUT_S: float = 30.0    # cooldown before HALF_OPEN
HEALTH_CHECK_INTERVAL_S: float = 60.0  # background probe interval
HEALTH_CHECK_TIMEOUT_S: float = 5.0    # max wait for health check
SUCCESS_THRESHOLD: int = 2          # successes in HALF_OPEN before CLOSED
```

### Fallback Resolution Algorithm

```python
async def get_provider_with_fallback(chain: list[str]) -> Provider:
    for name in chain:
        breaker = get_breaker(name)
        if breaker.state == CircuitState.OPEN:
            continue  # fast skip, no network call
        try:
            provider = get_provider(name)
            result = await breaker.call(provider.health_check)
            if result:
                return provider
        except ProviderUnavailableError:
            continue
    raise AllProvidersUnavailableError(chain)
```

### Per-Type Fallback Chains (Config-Driven)

```yaml
fallback:
  llm: [groq, openai, ollama]
  stt: [whisper_local, openai_whisper]
  tts: [edge_tts, piper, elevenlabs]
  vision: [openai_vision, anthropic_vision]
```

### Build Order Implications

- `CircuitBreaker` is a standalone state machine — build first, test with mock providers.
- `ProviderMetrics` is a simple counter struct — build alongside.
- `ResilientRegistry` extends existing `ProviderRegistry` — depends on `CircuitBreaker`.
- `HealthCheckScheduler` depends on `ResilientRegistry`.
- **FallbackChain expansion** (STT, TTS, Vision) requires updating config schema.
- **No dependency on audio pipeline or TTS streaming.** Can be built in parallel with Section 1.

---

## 4. Error Propagation Architecture (Provider Errors -> User Messages)

### Problem in Current Codebase

The main loop in `app.py` catches `(RuntimeError, OSError, KeyError)` generically, logs the exception, and sleeps 0.5s. No structured error reaches the user. The API layer has a basic `VoxAPIException` hierarchy but it's HTTP-only — the voice pipeline has no equivalent.

Silent failures in the current code:
- `AudioRecorder._on_audio_chunk`: drops on `QueueFull`, no logging.
- `Mouth.speak()`: catches `(RuntimeError, OSError)`, logs, returns nothing.
- `_run_loop`: catches broad exceptions, logs, continues.
- All provider calls: no structured error typing, just generic exceptions.

### Target Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                       Error Hierarchy                              │
│                                                                    │
│  VoxError (base)                                                   │
│    ├── AudioError                                                  │
│    │     ├── MicrophoneUnavailableError                            │
│    │     ├── AudioDroppedFramesError                               │
│    │     └── PlaybackError                                         │
│    ├── ProviderError                                               │
│    │     ├── ProviderUnavailableError                              │
│    │     ├── ProviderTimeoutError                                  │
│    │     ├── ProviderAuthError                                     │
│    │     ├── ProviderQuotaError                                    │
│    │     └── ProviderResponseError                                 │
│    ├── PipelineError                                               │
│    │     ├── TranscriptionError                                    │
│    │     ├── IntentExtractionError                                 │
│    │     ├── SkillExecutionError                                   │
│    │     └── TTSSynthesisError                                     │
│    └── ConfigError                                                 │
│          ├── MissingAPIKeyError                                    │
│          └── InvalidConfigError                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Boundary | Responsibility |
|-----------|----------|----------------|
| `VoxError` | Base exception. In `core/errors.py`. | Carries: `severity` (RECOVERABLE, DEGRADED, FATAL), `user_message` (TTS-safe Vietnamese), `retry_eligible` (bool), `provider_name` (optional). |
| `ErrorMapper` | Maps internal errors to user messages. In `core/errors.py`. | Registry of `VoxError` subclass -> Vietnamese template. E.g., `ProviderTimeoutError` -> "Dịch vụ đang chậm, để tôi thử cách khác." |
| `ErrorBoundary` | Context manager / decorator. In `core/errors.py`. | Wraps pipeline stages. Catches raw exceptions, converts to typed `VoxError`, logs with context, re-raises or returns fallback. |
| `UserErrorReporter` | Consumer of `VoxError`. In `core/mouth.py`. | Takes a `VoxError`, speaks the `user_message` via TTS. Severity-appropriate: RECOVERABLE = brief spoken msg, DEGRADED = spoken + dashboard alert, FATAL = spoken + halt. |

### Data Flow: Error Propagation

```
Provider throws httpx.TimeoutException
    │
    v
ErrorBoundary (wrapping the provider call in Brain/Ears/Mouth)
    │  catches httpx.TimeoutException
    │  maps to ProviderTimeoutError(
    │      provider_name="openai",
    │      severity=RECOVERABLE,
    │      user_message="Dịch vụ đang chậm, để tôi thử cách khác.",
    │      retry_eligible=True
    │  )
    v
Pipeline Stage (Brain.process / Ears._transcribe_frames)
    │  if retry_eligible and circuit breaker allows:
    │      try next provider in fallback chain
    │  else:
    │      propagate VoxError up
    v
Main Loop (_run_loop)
    │  catches VoxError
    │  match severity:
    │    RECOVERABLE: speak user_message, continue loop
    │    DEGRADED:    speak user_message, log warning, emit dashboard event
    │    FATAL:       speak user_message, initiate graceful shutdown
    v
UserErrorReporter -> Mouth.speak(error.user_message)
```

### Error Severity Levels

| Severity | Behavior | Example |
|----------|----------|---------|
| `RECOVERABLE` | Speak brief message, continue. Retry if eligible. | Provider timeout (fallback available) |
| `DEGRADED` | Speak message, continue with reduced capability. Alert dashboard. | All cloud providers down, local-only mode. |
| `FATAL` | Speak message, graceful shutdown. | Microphone hardware failure. |

### Error-to-Message Mapping (Vietnamese)

```python
ERROR_MESSAGES: dict[type[VoxError], str] = {
    MicrophoneUnavailableError: "Không tìm thấy microphone. Kiểm tra lại kết nối nhé.",
    ProviderTimeoutError: "Dịch vụ đang chậm, để tôi thử cách khác.",
    ProviderAuthError: "API key không hợp lệ. Kiểm tra lại cài đặt nhé.",
    ProviderQuotaError: "Đã hết quota API. Chuyển sang dịch vụ khác.",
    TranscriptionError: "Không nghe rõ, anh nói lại được không?",
    IntentExtractionError: "Xin lỗi, tôi không hiểu lệnh đó.",
    SkillExecutionError: "Không thực hiện được. {detail}",
    TTSSynthesisError: "",  # silent — can't speak about TTS failure
}
```

### Build Order Implications

- `VoxError` hierarchy is standalone — build first.
- `ErrorMapper` depends on error hierarchy + i18n templates.
- `ErrorBoundary` depends on error hierarchy — can be applied incrementally (wrap one pipeline stage at a time).
- `UserErrorReporter` depends on `Mouth` — build after TTS streaming (Section 2) so errors can also be interrupted.
- **Integrates with Section 3 (Circuit Breaker)**: `ProviderError` subtypes inform circuit breaker state transitions.
- **Can be built incrementally**: start with error hierarchy + boundary around provider calls, then expand to full pipeline.

---

## 5. Echo Cancellation Architecture (AEC Placement)

### Problem in Current Codebase

No AEC exists. When VoxAgent speaks via TTS, the microphone picks up its own output. This causes:
1. **Wake word false triggers**: TTS audio contains phonemes that match "Hey Vox".
2. **Whisper transcribes TTS output**: If the user speaks during TTS, Whisper gets a mix of user speech + TTS playback.
3. **Feedback loops**: In extreme cases, the assistant responds to its own output.

### Where AEC Sits in the Pipeline

```
Microphone                                          Speaker
    │                                                   ^
    │ raw audio (contains echo)                         │ TTS audio
    v                                                   │
┌──────────┐     ┌─────────┐     ┌──────────────┐     │
│ Recorder │────>│   AEC   │────>│ Clean Audio   │     │
│          │     │ Filter  │     │ (echo-free)   │     │
└──────────┘     └────^────┘     └──────┬───────┘     │
                      │                 │              │
                      │ reference       v              │
                      │ signal    WakeWord/VAD/STT     │
                      │                                │
                      └────── PlaybackWorker ──────────┘
                              (sends reference
                               signal to AEC)
```

**AEC sits between the AudioRecorder (producer) and the ChunkConsumer (WakeWord/VAD/STT).** It is the first processing stage after raw capture and before any detection or transcription.

### Components

| Component | Boundary | Responsibility |
|-----------|----------|----------------|
| `AECFilter` | Audio processing stage. In `core/audio/aec.py`. | Receives raw mic chunk + reference signal, outputs cleaned chunk. Stateful (adaptive filter coefficients). |
| `ReferenceSignalBus` | Shared data channel. In `core/audio/aec.py`. | PlaybackWorker writes TTS audio to the bus. AECFilter reads it as the reference. Thread-safe ring buffer. |
| `EchoState` | State tracker. In `core/audio/aec.py`. | Tracks whether TTS is currently playing. When not playing, AEC is bypassed (no processing cost). |

### AEC Strategy: Tiered Approach

AEC is computationally expensive and hard to get right. Use a tiered strategy:

**Tier 1: Mic Muting (Simplest, build first)**
```
When TTS is playing:
    - Mute wake word detection (don't trigger on own output)
    - Continue recording (buffer audio for potential barge-in)
    - Mark frames as "during_playback" for downstream filtering
```

**Tier 2: Spectral Subtraction (Medium complexity)**
```
When TTS is playing:
    - Know exact TTS audio being played (reference signal)
    - Subtract TTS spectral content from mic input
    - Residual = user speech (if any) + ambient noise
    - Feed residual to WakeWord/VAD
```

**Tier 3: Adaptive Filter (Full AEC, highest quality)**
```
- Use NLMS (Normalized Least Mean Squares) adaptive filter
- Reference signal + mic signal -> cleaned signal
- Handles room reverb, speaker-mic distance, latency alignment
- Libraries: speexdsp (via python-speexdsp), webrtc-aec (via webrtcvad)
```

### Recommended Implementation: Tier 1 + Tier 2

Full adaptive AEC (Tier 3) is overkill for a desktop assistant where the speaker and mic are on the same device. Tier 1 (mic muting for wake word) + Tier 2 (spectral subtraction for barge-in during playback) covers 95% of cases.

### Data Flow with AEC

```
AudioRecorder
    │ raw chunk (may contain TTS echo)
    v
EchoState.is_playing?
    ├── NO:  pass chunk through unchanged (zero cost)
    └── YES: 
         │
         v
    AECFilter.process(mic_chunk, reference_chunk)
         │  reference_chunk = what the speaker is currently playing
         │  aligned by estimated latency (speaker -> mic delay)
         v
    cleaned_chunk (echo removed or attenuated)
         │
         v
    WakeWord / VAD / STT
```

### Latency Alignment

The reference signal and mic signal are offset by the speaker-to-microphone delay (typically 5-50ms on a laptop). This delay must be estimated:

1. **Initial calibration**: Play a known chirp, measure round-trip time.
2. **Cross-correlation**: Continuously correlate reference and mic signals to track drift.
3. **Conservative default**: Use a fixed estimate (20ms for laptops, 5ms for headsets).

### Build Order Implications

- **Tier 1 (mic muting)** depends on `EchoState` + coordination with `PlaybackWorker` (Section 2). Simplest to build. **Build this first.**
- **Tier 2 (spectral subtraction)** depends on `ReferenceSignalBus` + numpy FFT. Medium effort.
- **Tier 3 (adaptive filter)** depends on external library (speexdsp). Only if Tier 2 is insufficient.
- **Strong dependency on Section 2 (TTS Streaming)**: AEC needs to know what the speaker is playing. The `PlaybackWorker` must write to the `ReferenceSignalBus`.
- **Strong dependency on Section 6 (Concurrent Audio)**: AEC only matters if the mic is listening during playback.

---

## 6. Concurrent Audio Architecture (Listen While Speaking)

### Problem in Current Codebase

The current pipeline is strictly sequential:

```
EARS.wait_for_command()  →  BRAIN.process()  →  HANDS.execute()  →  MOUTH.speak()
     └── blocks here ──────────────────────────────────────────────────────────┘
```

During `MOUTH.speak()`, the microphone is either:
- Still recording (but nobody is consuming the chunks — they pile up in the queue), or
- Not recording (Ears is in IDLE/TRANSCRIBING state — not monitoring wake word)

Either way, the user cannot interrupt ("barge in") with a new command or "Hey Vox" during TTS playback.

### Target Architecture: Dual-Track Audio

```
┌──────────────────────────────────────────────────────────────────┐
│                        AudioBus                                  │
│  (shared audio routing: mic -> multiple consumers)               │
└──────────┬──────────────────────┬───────────────────────────────┘
           │                      │
           v                      v
  ┌─────────────────┐    ┌──────────────────────┐
  │ CaptureTrack    │    │ MonitorTrack          │
  │ (full pipeline: │    │ (lightweight: wake    │
  │  VAD -> record  │    │  word only, always on)│
  │  -> STT)        │    │                       │
  └─────────────────┘    └──────────────────────┘
           │                      │
           │                      │ wake word detected during playback
           │                      v
           │              InterruptController.set()
           │              (stops TTS, switches to CaptureTrack)
           │
           v
  Full pipeline continues: BRAIN -> HANDS -> MOUTH
```

### Components

| Component | Boundary | Responsibility |
|-----------|----------|----------------|
| `AudioBus` | Fan-out for mic chunks. In `core/audio/bus.py`. | Single producer (AudioRecorder), multiple consumers. Each consumer gets its own copy of every chunk via subscription. |
| `CaptureTrack` | Primary consumer. Full Ears pipeline. | VAD -> record speech -> STT. Active when pipeline is in EARS phase. Paused during BRAIN/HANDS/MOUTH phases. |
| `MonitorTrack` | Background consumer. Lightweight. | Wake word detection only. Always active, even during TTS playback. When triggered, sets `InterruptController` and signals CaptureTrack to activate. |
| `AudioBusSubscription` | Per-consumer channel. | Each track gets its own bounded queue from the bus. Tracks can independently fall behind without affecting each other. |

### Data Flow: Barge-In Sequence

```
Timeline:
t0: User says "Hey Vox, open Chrome"
t1: EARS captures, STT transcribes
t2: BRAIN routes to app_launcher skill
t3: HANDS executes, returns "Đã mở Chrome rồi nha"
t4: MOUTH begins streaming TTS playback (Section 2)
    │
    │  MonitorTrack is active, listening for wake word
    │  CaptureTrack is paused (not recording/transcribing)
    │  AEC is filtering mic input (Section 5)
    │
t5: User says "Hey Vox, stop" during TTS playback
    │
    │  MonitorTrack detects wake word in AEC-cleaned audio
    v
t6: InterruptController.set()
    │  
    ├── PlaybackWorker stops playback (Section 2)
    ├── TTSChunkProducer stops synthesis (Section 2)
    ├── CaptureTrack activates (starts VAD -> record -> STT)
    │
t7: User says "stop"
t8: CaptureTrack records speech, STT transcribes "stop"
t9: BRAIN routes to system_control or media_control
t10: Normal pipeline continues
```

### State Machine: Pipeline Modes

```
┌──────────────┐     wake word      ┌──────────────┐
│   PASSIVE    │────detected────────>│   ACTIVE     │
│ MonitorTrack │                     │ CaptureTrack │
│   only       │<────STT done───────│ + Monitor    │
└──────────────┘                     └──────┬───────┘
       ^                                    │
       │                                    v
       │                             ┌──────────────┐
       │                             │  PROCESSING  │
       │                             │  BRAIN+HANDS │
       │                             │  + Monitor   │
       │                             └──────┬───────┘
       │                                    │
       │                                    v
       │                             ┌──────────────┐
       │                             │  SPEAKING    │
       │────────TTS done────────────│  MOUTH+AEC  │
       │                             │  + Monitor   │
       │    (or interrupt detected)  └──────────────┘
       │                                    │
       └────────────interrupt───────────────┘
```

Key: **MonitorTrack is always active in every state.** CaptureTrack only activates when needed.

### Performance Budget

MonitorTrack must be extremely lightweight:
- Wake word detection (OpenWakeWord ONNX): ~2ms per 80ms chunk = 2.5% CPU
- AEC Tier 1 (mic muting): ~0ms (just a flag check)
- AEC Tier 2 (spectral subtraction): ~1ms per chunk
- Total: <5ms per 80ms chunk = well within real-time budget

### Build Order Implications

- `AudioBus` is a standalone fan-out structure — build first.
- `MonitorTrack` depends on `AudioBus` + `WakeWordDetector` + `InterruptController` (Section 2).
- `CaptureTrack` depends on `AudioBus` + existing VAD/STT flow.
- **Depends on Section 2 (TTS Streaming)**: Barge-in requires interruptible playback.
- **Depends on Section 5 (AEC)**: MonitorTrack gets garbage wake word detections without at least Tier 1 AEC (mic muting).
- **This is the integration layer** — it ties together Sections 1, 2, and 5.

---

## Cross-Cutting: Suggested Build Order

Based on dependency analysis across all six sections:

```
Phase 1: Foundations (no cross-dependencies)
├── 1a. AudioRingBuffer + DropCounter (Section 1)
├── 1b. VoxError hierarchy + ErrorBoundary (Section 4)
└── 1c. CircuitBreaker + ProviderMetrics (Section 3)

Phase 2: Provider Resilience (depends on 1b, 1c)
├── 2a. ResilientRegistry + FallbackChain for all types (Section 3)
├── 2b. ErrorMapper + UserErrorReporter (Section 4)
└── 2c. HealthCheckScheduler (Section 3)

Phase 3: TTS Streaming (depends on 1a)
├── 3a. InterruptController (Section 2)
├── 3b. PlaybackWorker with sounddevice OutputStream (Section 2)
├── 3c. TTSChunkProducer + sentence splitting (Section 2)
└── 3d. StreamingMouth orchestrator (Section 2)

Phase 4: Concurrent Audio (depends on 3a)
├── 4a. AudioBus fan-out (Section 6)
├── 4b. EchoState + Tier 1 mic muting (Section 5)
├── 4c. MonitorTrack (Section 6)
└── 4d. CaptureTrack + pipeline mode state machine (Section 6)

Phase 5: Advanced AEC (optional, depends on 4a, 4b)
├── 5a. ReferenceSignalBus (Section 5)
├── 5b. Spectral subtraction AEC filter (Section 5)
└── 5c. Latency calibration (Section 5)
```

### Dependency Graph

```
                    ┌───────────────────────┐
                    │ Phase 1: Foundations   │
                    │ RingBuffer, Errors,    │
                    │ CircuitBreaker         │
                    └────┬──────────┬────────┘
                         │          │
              ┌──────────┘          └──────────┐
              v                                v
  ┌───────────────────────┐      ┌───────────────────────┐
  │ Phase 2: Provider     │      │ Phase 3: TTS          │
  │ Resilience            │      │ Streaming             │
  │ Registry, Fallback,   │      │ Chunked playback,     │
  │ Error mapping         │      │ Interruption          │
  └───────────────────────┘      └──────────┬────────────┘
                                            │
                                            v
                              ┌───────────────────────┐
                              │ Phase 4: Concurrent   │
                              │ Audio                 │
                              │ AudioBus, Monitor,    │
                              │ Barge-in, AEC Tier 1  │
                              └──────────┬────────────┘
                                         │
                                         v
                              ┌───────────────────────┐
                              │ Phase 5: Advanced AEC │
                              │ (optional)            │
                              │ Spectral subtraction, │
                              │ Adaptive filter       │
                              └───────────────────────┘
```

### Key Architectural Principles

1. **Never block the audio callback.** The sounddevice callback runs on a C-level thread with real-time priority. Any blocking, allocation, or Python GIL contention causes audible glitches and dropped frames.

2. **Ring buffers for audio, queues for events.** Audio is a continuous stream where old data becomes worthless — use circular buffers that overwrite. Events (errors, state changes, commands) are discrete and must not be lost — use queues.

3. **Every provider call goes through a circuit breaker.** No exceptions. This includes health checks themselves (which have their own shorter timeout).

4. **Errors have severity, not just type.** The same `ProviderTimeoutError` can be RECOVERABLE (fallback available) or DEGRADED (last provider in chain). Severity is determined at the boundary, not at the throw site.

5. **MonitorTrack never stops.** It is the "always-on ear" that enables barge-in. It runs wake word detection on every chunk regardless of pipeline state. Its processing budget is <5ms per 80ms chunk.

6. **AEC is tiered, not all-or-nothing.** Start with mic muting (zero-cost, covers 80% of cases), graduate to spectral subtraction only if needed. Adaptive filtering is a last resort.

7. **Streaming TTS is the enabler for everything else.** Without chunked playback, there's no point in barge-in (nothing to interrupt) or AEC (no concurrent audio). Build it before concurrent audio.

---

*Research completed 2026-04-09. Based on analysis of VoxAgent codebase (recorder.py, mouth.py, ears.py, registry.py, app.py, vad.py, base.py) and production patterns from audio pipeline engineering, resilient distributed systems, and voice assistant architectures.*
