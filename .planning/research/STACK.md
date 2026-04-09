# Production Hardening Stack Research

Research date: 2026-04-09
Scope: Libraries, tools, and patterns to harden VoxAgent for production use.
Method: PyPI version verification via live API, codebase analysis of existing audio pipeline.

---

## 1. Streaming TTS (Chunked Audio Playback)

### Current State

`mouth.py` synthesizes the **entire** WAV blob via `TTSProvider.synthesize()`, then plays it in one `sd.play()` call. This means:
- First-word latency = full synthesis time (1-5s for a sentence)
- No interruption possible (the whole clip plays via `sd.wait()`)
- No backpressure — numpy array held fully in memory

The `TTSProvider` ABC returns `bytes` (complete WAV), so streaming requires an ABC change to `AsyncIterator[bytes]`.

### Recommendation

| Component | Library | Version | Confidence |
|-----------|---------|---------|------------|
| Streaming playback | `sounddevice` (OutputStream) | >=0.5.5 | **High** |
| Edge TTS streaming | `edge-tts` (built-in `stream()`) | >=7.2.8 | **High** |
| ElevenLabs streaming | `elevenlabs` (built-in `stream()`) | >=2.42.0 | **High** |
| MP3 chunk decode | `miniaudio` | >=1.61 | **High** |
| Fallback chunk decode | `pydub` (already in stack) | >=0.25.1 | **Medium** |

### Architecture: Chunk-and-Play Pipeline

**Why `sounddevice.OutputStream` instead of `sd.play()`:**
`sd.play()` is fire-and-forget with no way to feed chunks incrementally or cancel mid-playback. `OutputStream` with a callback or write-based API lets you push 20-80ms chunks as they arrive from TTS, achieving <500ms first-word latency.

**Why `miniaudio` for decode:**
Edge TTS and ElevenLabs both stream MP3 chunks. `pydub` requires ffmpeg subprocess per chunk (slow). `miniaudio` provides a zero-copy C-level MP3 decoder via `miniaudio.decode()` that works on partial buffers — ideal for streaming. It's a single-file C library with Python bindings, no external dependencies.

**Why NOT `pyaudio`:**
`pyaudio` (v0.2.14) wraps PortAudio just like `sounddevice` but has a much worse API (manual buffer management, no numpy integration, callback threading issues). Since `sounddevice` is already in the stack, adding `pyaudio` would be redundant.

**Pattern — AsyncIterator TTS + OutputStream playback:**
```
TTSProvider.stream(text) -> AsyncIterator[bytes]  # MP3 chunks from provider
  -> miniaudio.decode(chunk) -> numpy int16 array  # Decode each chunk
  -> asyncio.Queue[numpy.ndarray]                  # Bounded buffer (backpressure)
  -> sounddevice.OutputStream callback reads queue  # Plays to speaker
```

The `asyncio.Event` for cancellation enables barge-in: setting the event drains the queue and closes the OutputStream immediately.

### What NOT to Use

| Library | Why Not |
|---------|---------|
| `pyaudio` >=0.2.14 | Redundant with `sounddevice`; worse API, same PortAudio backend |
| `pygame.mixer` | Full game engine dependency for audio playback; no streaming callback API |
| `playsound` | Fire-and-forget only; no streaming, no cancel, abandoned maintenance |
| `simpleaudio` | No streaming support; loads entire WAV into memory |

---

## 2. Acoustic Echo Cancellation (AEC)

### Current State

No AEC exists. When VoxAgent speaks via TTS, the microphone picks up the speaker output, and faster-whisper/OpenAI Whisper transcribes VoxAgent's own voice. This creates false wake-word triggers and garbage transcriptions.

### Recommendation

| Component | Library | Version | Confidence |
|-----------|---------|---------|------------|
| **Primary: Software AEC** | `speexdsp` | >=0.1.1 | **Medium** |
| **Alternative: Simple AEC** | `pyaec` | >=1.0.1 | **Low** |
| **Pragmatic: Mic muting** | No library (pattern) | — | **High** |

### Analysis

**Why this is hard in Python:**
True AEC requires a reference signal (what the speaker is playing) aligned in time with the microphone input, processed sample-by-sample with an adaptive filter. This is a DSP-heavy operation that professional systems (WebRTC, PulseAudio) handle in C/C++ at the OS or driver level.

**`speexdsp` >=0.1.1 (Python bindings for libspeexdsp):**
- Provides `SpeexEchoState` with `echo_cancellation(mic_frame, speaker_frame)` API
- Requires feeding the exact speaker output as the reference signal — this means capturing the playback buffer from `sounddevice.OutputStream`
- Quality is decent but not WebRTC-grade; works for single-speaker desktop scenarios
- **Risk:** The Python bindings (v0.1.1) are minimally maintained. Last PyPI update was 2023. May need pinning.

**`pyaec` >=1.0.1 (pure Python adaptive filter):**
- Implements NLMS (Normalized Least Mean Squares) adaptive filter in pure Python/numpy
- Much simpler but lower quality than speexdsp
- Good for prototyping; not recommended for production due to latency and convergence issues

**Pragmatic alternative — Mic Mute During Playback (no library needed):**
- Mute the microphone (or discard mic input) while TTS is playing
- Re-enable mic + VAD after playback completes + a short silence buffer (200ms)
- This is what most commercial voice assistants actually do in v1
- Zero library dependencies, 100% reliable, but prevents true barge-in during TTS

### Recommended Strategy (Phased)

1. **Phase 1 (immediate):** Mic-mute pattern. Set an `is_speaking` flag in `Mouth`, check it in `AudioRecorder._on_audio_chunk()` to discard input. Zero risk, zero deps.
2. **Phase 2 (if barge-in needed):** Integrate `speexdsp` AEC. Feed the `OutputStream` playback buffer as the reference signal to `SpeexEchoState`. This allows listening while speaking.
3. **Phase 3 (ideal):** If the OS supports it, use system-level AEC (PulseAudio's `module-echo-cancel` on Linux, Windows Audio Session API echo cancellation). No Python library needed — configure at OS level.

### What NOT to Use

| Library | Why Not |
|---------|---------|
| `webrtc-audio-processing` | No maintained Python bindings; C++ library requires complex build |
| `adaptfilt` | Academic library; not maintained since 2019 |
| Rolling your own LMS filter | Convergence tuning is a PhD-level problem; use speexdsp |

---

## 3. Noise Suppression

### Current State

Silero VAD detects speech vs. silence but does NOT suppress noise — it just classifies. Background noise (fan, keyboard, traffic) still reaches faster-whisper, degrading transcription accuracy. The energy-based fallback VAD is especially noise-sensitive.

### Recommendation

| Component | Library | Version | Confidence |
|-----------|---------|---------|------------|
| **Primary: Neural noise suppression** | `deepfilternet` | >=0.5.6 | **High** |
| **Alternative: Spectral gating** | `noisereduce` | >=3.0.3 | **Medium** |
| **Lightweight: RNNoise bindings** | `pyrnnoise` | >=0.4.3 | **Medium** |
| **VAD supplement** | `webrtcvad` | >=2.0.10 | **Medium** |

### Analysis

**`deepfilternet` >=0.5.6 (DeepFilterNet — neural noise suppression):**
- State-of-the-art deep learning noise suppression (published research by Hendrik Schroter)
- Processes 16kHz mono audio in real-time on CPU (~5ms per 20ms frame on modern hardware)
- Dramatically improves STT accuracy in noisy environments
- Ships pre-trained ONNX models — no training needed
- **Caveat:** Adds ~50MB model weight. Torch dependency (already in stack for Silero VAD).
- **Best for:** Always-on noise suppression in the audio pipeline before VAD and STT

**`noisereduce` >=3.0.3 (spectral gating):**
- Traditional signal processing approach (spectral gating / noise profiling)
- Works by learning a noise profile from a "silent" segment, then subtracting it
- Lighter than neural approaches but less effective on non-stationary noise
- No model files, pure numpy/scipy
- **Best for:** Environments with consistent background noise (server room fan, AC)

**`pyrnnoise` >=0.4.3 (RNNoise Python bindings):**
- Wraps Mozilla's RNNoise (GRU-based noise suppression)
- Very lightweight (~200KB model), real-time capable
- Less effective than DeepFilterNet on complex noise but much smaller
- **Best for:** Resource-constrained environments or when torch is not available

**`webrtcvad` >=2.0.10 (Google WebRTC VAD):**
- Not noise suppression — it's a VAD (like Silero) but much lighter (GMM-based)
- Useful as a fast pre-filter before the heavier Silero VAD
- Three aggressiveness modes (1=permissive, 3=aggressive)
- **Best for:** Supplementing Silero VAD with a lightweight first-pass filter to reduce unnecessary Silero inference

### Recommended Strategy

1. **Insert `deepfilternet` as a preprocessing stage** in the audio pipeline: `mic -> noise_suppress -> VAD -> STT`. Process each 80ms chunk through DeepFilterNet before VAD and STT see it.
2. **Keep `noisereduce` as a fallback** for environments without torch (full_local profile with no GPU).
3. **Add `webrtcvad` as a fast pre-filter** before Silero: if WebRTC VAD says "silence" at aggressiveness=3, skip Silero inference entirely. Saves ~2ms per silent chunk.

### What NOT to Use

| Library | Why Not |
|---------|---------|
| `speexdsp-ns` >=0.1.2 | Only file-based processing (no real-time frame API); abandoned since 2023 |
| `scipy.signal` (manual spectral gating) | Reinventing `noisereduce`; same approach but untuned |
| `torchaudio.transforms` | Pulls in full torchaudio (~500MB); overkill for noise suppression alone |

---

## 4. Audio Backpressure & Buffer Management

### Current State

`AudioRecorder` uses an **unbounded** `asyncio.Queue()` with `put_nowait()` + `suppress(QueueFull)`. This means:
- If the consumer (VAD/STT) is slow, chunks silently accumulate in the queue (unbounded memory growth)
- If the queue were bounded, chunks are silently **dropped** (`suppress(QueueFull)`)
- No metrics on queue depth, drop rate, or latency
- No way to detect or recover from sustained backpressure

### Recommendation

| Component | Approach | Library | Confidence |
|-----------|----------|---------|------------|
| Bounded audio queue | `asyncio.Queue(maxsize=N)` | stdlib | **High** |
| Drop policy with metrics | Custom wrapper | None | **High** |
| Playback backpressure | `sounddevice.OutputStream` callback | `sounddevice` >=0.5.5 | **High** |
| Queue monitoring | `structlog` context vars | `structlog` >=25.5.0 | **Medium** |

### Architecture: Bounded Queue with Drop-Oldest Policy

**Why not drop-newest (current behavior):**
Dropping the newest chunk (what `suppress(QueueFull)` does) means you lose the most recent audio — exactly what the user just said. Drop-oldest is better: discard stale audio to make room for fresh input.

**Pattern — `BoundedAudioBuffer`:**
```python
MAX_QUEUE_DEPTH = 50  # ~4 seconds at 80ms chunks
DROP_WARNING_THRESHOLD = 40  # Log warning at 80% capacity

class BoundedAudioBuffer:
    def __init__(self, maxsize: int = MAX_QUEUE_DEPTH):
        self._queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=maxsize)
        self._drops: int = 0

    def push(self, chunk: np.ndarray) -> None:
        if self._queue.full():
            self._queue.get_nowait()  # Drop oldest
            self._drops += 1
        self._queue.put_nowait(chunk)
```

**Playback backpressure (OutputStream):**
For streaming TTS, the `OutputStream` callback requests audio on-demand. If the TTS chunk queue is empty, output silence (zeros). If the queue grows beyond a threshold, the playback is keeping up — no action needed. This is inherently backpressure-aware because the audio hardware pulls at a fixed rate.

**Monitoring:**
Add `structlog` (>=25.5.0) for structured logging with context variables (queue depth, drop count, latency). This is far superior to VoxAgent's current `logging.getLogger()` for production diagnostics.

### What NOT to Use

| Approach | Why Not |
|----------|---------|
| Unbounded `asyncio.Queue()` | Memory leak under sustained load |
| `queue.Queue` (threading) | Wrong concurrency model; VoxAgent is async |
| `multiprocessing.Queue` | Unnecessary IPC overhead for single-process app |
| `collections.deque(maxlen=N)` | Not async-safe; no `await`-able get |

---

## 5. Error Recovery & Circuit Breaker Patterns

### Current State

Error handling is bare-minimum: `try/except` with `logger.exception()` and silent failure. No retries, no backoff, no circuit breaking. A transient network glitch kills the entire pipeline silently.

### Recommendation

| Component | Library | Version | Confidence |
|-----------|---------|---------|------------|
| **Retry with backoff** | `tenacity` | >=9.1.4 | **High** |
| **Alternative retry** | `stamina` | >=25.2.0 | **High** |
| **Circuit breaker** | `aiobreaker` | >=1.2.0 | **Medium** |
| **Structured logging** | `structlog` | >=25.5.0 | **High** |
| **Observability** | `opentelemetry-api` | >=1.41.0 | **Low** |

### Analysis

**`tenacity` >=9.1.4 (retry library):**
- De facto standard for Python retry logic. 28k+ GitHub stars, actively maintained.
- Native async support (`@retry` works on async functions)
- Built-in: exponential backoff, jitter, retry-if-exception-type, stop-after-attempt, before/after callbacks
- **Why tenacity over stamina:** Tenacity is more flexible (custom retry predicates, per-call overrides). Stamina is simpler but opinionated (always uses `is_error` predicate). For VoxAgent's diverse error types (network, audio, model), tenacity's flexibility wins.
- **Pattern for VoxAgent:**
  ```python
  @retry(
      stop=stop_after_attempt(3),
      wait=wait_exponential(multiplier=1, min=0.5, max=10),
      retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
      before_sleep=before_sleep_log(logger, logging.WARNING),
  )
  async def _call_provider(self, messages: list[Message]) -> str: ...
  ```

**`stamina` >=25.2.0 (opinionated retry):**
- Built on top of tenacity but with simpler API and better defaults
- Integrates with `structlog` out of the box for retry logging
- **Best for:** If you want "just make it retry with sane defaults" without configuring tenacity
- **Not recommended as primary** because VoxAgent needs different retry policies for different provider types (network calls vs. local model inference vs. audio I/O)

**`aiobreaker` >=1.2.0 (async circuit breaker):**
- Implements the circuit breaker pattern for async Python
- States: CLOSED (normal) -> OPEN (failing, reject fast) -> HALF-OPEN (test recovery)
- Prevents hammering a dead provider with requests
- **Pattern for VoxAgent:** Wrap each provider with a circuit breaker. When a provider trips open (e.g., 5 failures in 60s), the fallback chain immediately skips to the next provider instead of waiting for timeouts.
- **Caveat:** Small library (last update 2023), but the pattern is simple enough that if it becomes unmaintained, reimplementation is ~50 lines.

### Custom Error Hierarchy (No Library — Pattern)

VoxAgent needs a structured error hierarchy, not library-based:

```python
class VoxAgentError(Exception):
    """Base error with severity and user-facing message."""
    severity: ErrorSeverity  # CRITICAL, HIGH, MEDIUM, LOW
    user_message: str        # What to tell user via TTS
    retryable: bool          # Whether retry makes sense

class ProviderError(VoxAgentError): ...      # LLM/STT/TTS provider failures
class AudioPipelineError(VoxAgentError): ... # Mic, playback, buffer errors
class SkillExecutionError(VoxAgentError): ... # Skill action failures
class SecurityError(VoxAgentError): ...      # Permission, injection errors
```

This enables:
- Retry only `retryable` errors
- Speak `user_message` via TTS for user-facing errors
- Circuit-break on `ProviderError` only
- Log structured `severity` for monitoring

### What NOT to Use

| Library | Why Not |
|---------|---------|
| `backoff` | Less maintained than tenacity; fewer features; no circuit breaker integration |
| `retry` | Abandoned (last release 2016) |
| `pybreaker` | Sync-only; doesn't work with async/await |
| `circuitbreaker` | Sync-only; same issue |
| `resilience4j` (via Py4J) | Java library; absurd overhead for Python |

---

## 6. Provider Fallback Chain

### Current State

`ProviderRegistry` has a basic `get_llm_with_fallback()` that iterates providers and calls `health_check()`. Problems:
- Only works for LLM providers — no fallback for STT, TTS, or Vision
- `health_check()` is called on every request (wasteful; should cache health state)
- No circuit breaker integration — a slow/failing provider blocks the chain with timeouts
- No error context propagation — if all providers fail, the error message is generic

### Recommendation

| Component | Approach | Library | Confidence |
|-----------|----------|---------|------------|
| Generic fallback chain | Custom `FallbackChain[T]` | None (pattern) | **High** |
| Health caching | TTL-based cache | None (pattern) | **High** |
| Circuit integration | `aiobreaker` per provider | `aiobreaker` >=1.2.0 | **Medium** |
| Retry per provider | `tenacity` per call | `tenacity` >=9.1.4 | **High** |

### Architecture: Generic `FallbackChain[T]`

The current registry has fallback only for LLM. The pattern should be generic across all provider types:

```
FallbackChain[TTSProvider]:
  1. ElevenLabs (cloud, high quality) -- circuit breaker + 3 retries
     |-- OPEN? skip immediately
     |-- CLOSED? try with tenacity retry
     |-- FAILED? mark failure, move to next
  2. Edge TTS (cloud, free) -- circuit breaker + 3 retries
     |-- same pattern
  3. Piper (local, always available) -- no circuit breaker, 1 retry
     |-- local providers don't need circuit breakers
     |-- FAILED? raise ProviderError with all accumulated errors
```

**Key design decisions:**
- **Separate fallback chains per provider type** (LLM, STT, TTS, Vision) — configured in YAML
- **Circuit breakers on cloud providers only** — local providers (Ollama, Piper, faster-whisper) don't need them
- **Retry within each provider** (tenacity), **failover across providers** (FallbackChain)
- **Health check caching** with TTL (30s for cloud, 5min for local) — don't health-check on every single request
- **Error aggregation** — if all providers fail, the error includes details from each attempt

### What NOT to Use

| Approach | Why Not |
|----------|---------|
| Single retry around the entire chain | Retries the whole chain from scratch; wastes time re-trying providers that already failed |
| Load balancing (round-robin) | Wrong pattern for voice assistant; you want best-quality-first, not distributed |
| `httpx` retry transport | Only handles HTTP retries; doesn't cover local provider failures or non-HTTP errors |

---

## Summary: New Dependencies

### Required (High Confidence)

| Package | Version | Purpose | Size Impact |
|---------|---------|---------|-------------|
| `tenacity` | >=9.1.4 | Retry with exponential backoff | ~50KB (pure Python) |
| `miniaudio` | >=1.61 | Streaming MP3 decode for TTS chunks | ~500KB (C extension) |
| `structlog` | >=25.5.0 | Structured logging for production diagnostics | ~200KB (pure Python) |

### Recommended (Medium Confidence)

| Package | Version | Purpose | Size Impact |
|---------|---------|---------|-------------|
| `deepfilternet` | >=0.5.6 | Neural noise suppression | ~50MB (models) |
| `aiobreaker` | >=1.2.0 | Async circuit breaker | ~20KB (pure Python) |
| `pyrnnoise` | >=0.4.3 | Lightweight noise suppression (fallback) | ~1MB (C extension) |
| `noisereduce` | >=3.0.3 | Spectral noise reduction (no-torch fallback) | ~100KB (requires scipy) |

### Optional / Phased (Lower Confidence)

| Package | Version | Purpose | Size Impact |
|---------|---------|---------|-------------|
| `speexdsp` | >=0.1.1 | Acoustic echo cancellation (Phase 2) | ~200KB (C extension) |
| `webrtcvad` | >=2.0.10 | Fast VAD pre-filter | ~100KB (C extension) |
| `opentelemetry-api` | >=1.41.0 | Distributed tracing (Phase 3) | ~500KB |

### Version Upgrades for Existing Deps

| Package | Current | Recommended | Reason |
|---------|---------|-------------|--------|
| `edge-tts` | >=6.1 | >=7.2.8 | Streaming `stream()` API improvements |
| `sounddevice` | >=0.5.1 | >=0.5.5 | Bug fixes for OutputStream callback |
| `elevenlabs` | (not pinned) | >=2.42.0 | `text_to_speech.stream()` for chunked audio |

### Explicitly NOT Adding

| Package | Reason |
|---------|--------|
| `pyaudio` | Redundant with sounddevice (same PortAudio backend, worse API) |
| `pygame` | Massive game engine; overkill for audio playback |
| `backoff` | Less maintained, fewer features than tenacity |
| `pybreaker` | Sync-only; incompatible with async architecture |
| `torchaudio` | 500MB+ dependency just for noise suppression |
| `speexdsp-ns` | File-only API; no real-time frame processing |

### No-Library Patterns (Custom Implementation)

| Pattern | Description |
|---------|-------------|
| `BoundedAudioBuffer` | Drop-oldest bounded queue with metrics (~30 lines) |
| `VoxAgentError` hierarchy | Custom exception classes with severity + retryable flag (~50 lines) |
| `FallbackChain[T]` | Generic async provider fallback with circuit breaker integration (~80 lines) |
| Mic-mute AEC (Phase 1) | `is_speaking` flag to discard mic input during TTS (~10 lines) |
| Health cache | TTL-based provider health caching (~40 lines) |

---

## Dependency Graph (New -> Existing)

```
tenacity ---------> (no deps, pure Python)
miniaudio --------> (vendored C library, no external deps)
structlog --------> (no deps, pure Python)
deepfilternet ----> torch (already in stack via Silero VAD)
aiobreaker -------> (no deps, pure Python)
pyrnnoise --------> (vendored C library via cffi)
noisereduce ------> numpy (already in stack), scipy
speexdsp ---------> (system libspeexdsp required)
webrtcvad --------> (vendored C library)
```

No new heavy transitive dependencies. `deepfilternet` reuses the existing `torch` dependency. `noisereduce` would pull in `scipy` (~30MB) which is new but well-justified for signal processing.

---

*Versions verified against PyPI JSON API on 2026-04-09.*
