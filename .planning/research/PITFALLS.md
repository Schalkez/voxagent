# VoxAgent Hardening: Critical Pitfalls

> Scope: Voice assistant production hardening for VoxAgent
> Generated: 2026-04-09
> Inputs: Codebase analysis (mouth.py, recorder.py, ears.py, brain.py, terminal.py, registry.py, edge_tts_provider.py, app.py, base.py), PROJECT.md, CONCERNS.md

---

## 1. Streaming TTS: Retrofitting Onto a Batch-TTS System

### Context in VoxAgent

`TTSProvider.synthesize()` returns `bytes` (a complete WAV blob). `Mouth.speak()` calls `_play_wav()` which reads the entire WAV into a numpy array and plays it with `sd.play()` + `sd.wait()`. Edge TTS already streams internally (`async for chunk in communicate.stream()`) but collects all chunks into a single `bytes` before returning. The entire pipeline is synchronous-complete: nothing plays until the last byte arrives.

### Pitfall 1.1: Adding `synthesize_stream()` Without Changing the Playback Contract

**What goes wrong:** Teams add an `AsyncIterator[bytes]` streaming method to `TTSProvider` but keep `_play_wav()` as the playback path. They buffer the iterator back into a single blob before playing. Result: you've added complexity but latency is identical. First-word latency remains equal to full-synthesis time.

**Warning signs:** First-word latency benchmarks don't improve after implementing streaming. The `sd.play()` call still receives a single array.

**Prevention:**
- Replace `sd.play()` + `sd.wait()` with `sd.OutputStream` using a callback that pulls from an `asyncio.Queue[np.ndarray]`. The queue is fed by the streaming TTS iterator.
- The playback callback and the TTS producer run concurrently. Audio starts playing as soon as the first chunk arrives.
- Never buffer the full stream before playback. If you find yourself calling `b"".join(chunks)` before playing, the streaming is fake.

**Phase:** Streaming TTS implementation.

### Pitfall 1.2: Chunk Boundary Audio Artifacts (Clicks and Pops)

**What goes wrong:** Each TTS chunk is a self-contained audio segment. When played back-to-back, the last sample of chunk N and the first sample of chunk N+1 may have a discontinuity (amplitude jump). This produces audible clicks at every chunk boundary. Edge TTS returns MP3 chunks; decoding each independently resets the decoder state.

**Warning signs:** Audible clicking at regular intervals during long utterances. More noticeable with Piper (raw PCM) than Edge TTS (MP3 frames).

**Prevention:**
- Use a single persistent MP3 decoder that processes a byte stream, not independent per-chunk decoders. For `pydub`/`ffmpeg`, pipe the concatenated stream rather than decoding per chunk.
- Apply short crossfade (2-5ms) at chunk boundaries, or use overlap-add.
- For PCM providers (Piper), ensure the TTS engine outputs chunks at natural boundaries (sentence breaks, breath pauses) rather than at fixed byte offsets.

**Phase:** Streaming TTS implementation.

### Pitfall 1.3: Edge TTS MP3-to-WAV Conversion Kills Streaming Advantage

**What goes wrong:** `EdgeTTSProvider.synthesize()` already collects all MP3 chunks, then calls `_mp3_to_wav()` using `pydub.AudioSegment.from_mp3()` which requires the entire MP3 in memory. If you add a streaming method that yields chunks, each chunk still needs MP3 decoding, and `pydub` cannot do incremental MP3 decoding.

**Warning signs:** You end up with a streaming method that internally blocks on `AudioSegment.from_mp3()` for each chunk, adding latency per chunk.

**Prevention:**
- Use `ffmpeg` in streaming/pipe mode (`subprocess.Popen` with `stdin=PIPE`, `stdout=PIPE`) for real-time MP3-to-PCM conversion. Feed MP3 bytes in, read PCM bytes out.
- Or use `miniaudio` / `pyav` which support incremental codec decode.
- Do NOT wrap `pydub` in an async iterator and call it "streaming." pydub is batch-only.

**Phase:** Streaming TTS implementation.

### Pitfall 1.4: Blocking the Event Loop During Playback

**What goes wrong:** VoxAgent correctly uses `asyncio.to_thread(_play_blocking)` for the current batch path. But when switching to `sd.OutputStream` with a callback, the callback runs on sounddevice's internal C thread. If you try to `await queue.get()` from that callback, you'll deadlock (the callback is not on the asyncio event loop). If you use `queue.get_nowait()` and it's empty, you get a buffer underrun (silence gaps).

**Warning signs:** Intermittent silence gaps during TTS playback. Deadlocks when the TTS source is slow. The sounddevice callback raising `QueueEmpty`.

**Prevention:**
- Pre-buffer 2-3 chunks before starting the OutputStream. This absorbs network jitter.
- In the sounddevice callback, use `queue.get_nowait()` wrapped in a try/except; on empty queue, output silence (zeros) rather than crashing. Track underruns with a counter for diagnostics.
- The async TTS iterator fills the queue from the event loop; the sounddevice callback drains it from the audio thread. These are two separate worlds. Use `asyncio.Queue` only if the callback can use `put_nowait()` / `get_nowait()`.

**Phase:** Streaming TTS implementation.

---

## 2. Barge-In / TTS Interruption

### Context in VoxAgent

Currently, `_play_wav()` calls `sd.play()` + `sd.wait()` inside `asyncio.to_thread()`. The thread blocks until the entire audio finishes. During TTS playback, the Ears pipeline is in `LISTENING_FOR_WAKE_WORD` state from the last cycle but the main loop is blocked at `await self._mouth.speak(result.tts_response)` in `_run_loop()`. The user cannot interrupt.

### Pitfall 2.1: Stopping sd.play() From Another Thread Without sd.stop()

**What goes wrong:** `sd.play()` is a high-level convenience function that uses a global OutputStream. Calling `sd.stop()` from another thread while `sd.wait()` blocks is actually safe, but many teams don't know this and instead try to cancel the `asyncio.to_thread()` task. Cancelling an `asyncio.Task` wrapping `to_thread` does NOT stop the thread. The audio keeps playing.

**Warning signs:** `task.cancel()` is called but TTS continues playing. The user has to wait for the full utterance to finish.

**Prevention:**
- Use an explicit `sd.OutputStream` (not `sd.play()`) with a `threading.Event` stop signal. The callback checks the event on each buffer fill and outputs silence when set.
- OR keep `sd.play()` but call `sd.stop()` from the wake-word detection path. `sd.stop()` is thread-safe and will cause `sd.wait()` to return immediately.
- The critical architecture change: Ears and Mouth must run concurrently, not sequentially. The main loop must `await` both listening and speaking simultaneously (e.g., `asyncio.gather` or a separate playback task).

**Phase:** TTS interruption support.

### Pitfall 2.2: Wake Word Detector Hears the TTS Output (Self-Triggering)

**What goes wrong:** While TTS is playing through speakers, the microphone picks up the TTS audio. OpenWakeWord may detect "Hey Vox" in the TTS output (especially if the assistant says something phonetically similar). This causes a self-trigger: the assistant interrupts itself, creating a feedback loop.

**Warning signs:** The assistant triggers a new command cycle immediately after starting to speak. Logs show wake word detected during TTS playback. Happens more in quiet rooms where speaker-to-mic coupling is strong.

**Prevention:**
- Suppress wake word detection during TTS playback. Use a simple boolean flag (`_is_speaking`) checked before processing wake word results.
- Better: implement echo suppression (see Section 3) so the wake word detector only receives cleaned audio.
- Even better: keep wake word detection active but require a higher confidence threshold during playback (e.g., 0.7 normal vs 0.9 during TTS).

**Phase:** TTS interruption + echo cancellation (must be co-designed).

### Pitfall 2.3: Barge-In Without Draining the Audio Queue

**What goes wrong:** When barge-in is detected, the TTS stream is stopped, but buffered chunks in the playback queue remain. If the next cycle's recording starts immediately, stale TTS audio chunks in the queue may be processed, or worse, the queue feeds old audio to the next playback.

**Warning signs:** Brief burst of old TTS audio after the user interrupts. Ghost transcriptions of the assistant's own speech appearing as user commands.

**Prevention:**
- On barge-in: (1) stop the OutputStream, (2) drain the TTS chunk queue completely, (3) drain the `AudioRecorder._audio_queue` (already has `_drain_queue()` but it's only called on `start()`), (4) THEN start recording user speech.
- The drain order matters. Audio queue first (mic buffer), then TTS queue.

**Phase:** TTS interruption support.

### Pitfall 2.4: Concurrent Access to sounddevice Input/Output Streams

**What goes wrong:** sounddevice uses PortAudio underneath. On many platforms, you cannot have an InputStream (mic) and an OutputStream (speakers) using different host APIs or conflicting configurations. Teams that open mic and speaker streams separately may get `PortAudioError` on Windows (especially with WASAPI exclusive mode).

**Warning signs:** `sd.PortAudioError: [PaErrorCode -9999] Unanticipated host error` when trying to play TTS while the microphone stream is open. Works fine when testing recording and playback separately but fails when both are active.

**Prevention:**
- Use a single `sd.Stream` (full-duplex) with both input and output channels, OR ensure both streams use the same host API (`hostapi` parameter in sounddevice).
- Test specifically on Windows with the default audio device. Windows WASAPI exclusive mode is the most common failure case.
- Fallback: if full-duplex fails, close mic during TTS, reopen after. This loses barge-in but avoids crashes.

**Phase:** TTS interruption support.

---

## 3. Echo Cancellation

### Context in VoxAgent

CONCERNS.md lists "No echo cancellation" as a gap. Currently, Whisper will transcribe the assistant's own TTS output if it's picked up by the microphone. This is especially dangerous with barge-in: the assistant hears itself, transcribes its own words, and processes them as a new command.

### Pitfall 3.1: Naive Suppression (Muting Mic During TTS) Kills Barge-In

**What goes wrong:** The simplest "echo cancellation" is to stop recording while speaking. But this contradicts the barge-in requirement: the user MUST be able to speak during TTS. If you mute the mic, barge-in is impossible. If you don't mute, the assistant hears itself.

**Warning signs:** You implemented barge-in and echo suppression as separate features, and they're mutually exclusive.

**Prevention:**
- These two features are architecturally coupled. Design them together in the same phase, not sequentially.
- Use a state machine: IDLE -> LISTENING -> TTS_PLAYING (mic on, AEC active, wake word sensitive) -> BARGE_IN_DETECTED -> TTS_STOPPED -> RECORDING.
- During TTS_PLAYING, process mic audio through AEC before feeding to wake word / VAD.

**Phase:** Echo cancellation + TTS interruption (same phase, not separate).

### Pitfall 3.2: Real AEC Requires a Reference Signal That You Don't Have

**What goes wrong:** Proper Acoustic Echo Cancellation (like WebRTC AEC or SpeexDSP) needs the "reference signal" (the exact audio being played to the speakers) to subtract it from the mic input. With `sd.play()` (the current batch approach), you don't have easy access to the output buffer. Many teams skip the reference signal and just try spectral subtraction on the mic input, which produces metallic artifacts and kills speech quality.

**Warning signs:** Echo "cancellation" makes voices sound robotic. It removes some TTS echo but also removes parts of the user's speech.

**Prevention:**
- When you switch to `sd.OutputStream`, you control exactly which samples are being sent to the speaker. Save a copy of each output buffer as the AEC reference signal. Feed both the mic input and the reference to the AEC algorithm.
- Use `speexdsp-python` (`SpeexEchoState`) or `webrtc-audio-processing-python` for proven AEC. Don't implement AEC from scratch.
- The reference signal MUST be sample-aligned with the mic input. Account for the hardware playback delay (the DAC buffer adds 5-20ms of latency between writing to the OutputStream and actual speaker emission). Measure this delay per-device.

**Phase:** Echo cancellation.

### Pitfall 3.3: AEC Tail Length Misconfiguration

**What goes wrong:** AEC algorithms model the room impulse response up to a "tail length." If the tail is too short, echoes from room reflections leak through. If too long, convergence is slow and processing is heavier. Teams often pick arbitrary values (128ms) without measuring the actual room.

**Warning signs:** AEC works in a small room but fails in a larger room. Or it works after 10 seconds but not immediately (slow convergence).

**Prevention:**
- Start with 100-200ms tail length (reasonable for a typical desk setup).
- Make it configurable. Provide a calibration mode that plays a test tone and measures the round-trip time.
- For VoxAgent's desktop use case, the speaker-to-mic distance is usually < 1m, so 150ms tail is generally sufficient.

**Phase:** Echo cancellation.

### Pitfall 3.4: Sample Rate Mismatch Between Input and Output Streams

**What goes wrong:** VoxAgent's mic records at 16kHz (`SAMPLE_RATE = 16_000` in recorder.py). Edge TTS outputs are converted to 16kHz mono WAV. But if the output `sd.OutputStream` uses the system default rate (often 44.1kHz or 48kHz), the reference signal is at a different rate than the mic input. AEC algorithms require both to be at the same sample rate.

**Warning signs:** AEC produces no effect or produces garbage. It works on one machine but not another.

**Prevention:**
- Explicitly set both input and output streams to the same sample rate (16kHz is fine).
- OR resample the reference signal to match the mic rate before feeding to AEC.
- Assert sample rate equality at AEC initialization, not at runtime.

**Phase:** Echo cancellation.

---

## 4. Circuit Breaker / Provider Fallback

### Context in VoxAgent

`ProviderRegistry.get_llm_with_fallback()` exists but is never called by Brain. Brain catches `ProviderNotFoundError` and falls back to "ollama" hardcoded. Each provider creates a new `httpx.AsyncClient` per request (CONCERNS 3.1). Health checks make real API calls that cost money (CONCERNS 3.4).

### Pitfall 4.1: Health Check in the Hot Path Adds Latency to Every Request

**What goes wrong:** `get_llm_with_fallback()` calls `provider.health_check()` for EVERY request to find a healthy provider. Health checks make a real API call (`"ping"` with `max_tokens=1`). In the voice pipeline where the user is waiting, you cannot add 200-500ms of health check latency before every LLM call.

**Warning signs:** Adding fallback support increases p50 latency by the health check RTT. The system is slower with fallback than without.

**Prevention:**
- Track provider health asynchronously with a background heartbeat (every 30-60 seconds), not in the hot path.
- Use cached health state: `_last_healthy: dict[str, tuple[bool, float]]`. The fallback path reads cached state, not live health.
- Only trigger a live health check when the cached state is stale (>60s) or after a request failure.

**Phase:** Provider fallback chains.

### Pitfall 4.2: Circuit Breaker Without State Reset (Permanent Open)

**What goes wrong:** A circuit breaker opens after N failures, routing traffic to the fallback. But if there's no half-open state (periodic probe to check if the primary recovered), the circuit stays open forever. The user starts VoxAgent, OpenAI has a 30-second outage, and the circuit breaker routes to Ollama. OpenAI recovers, but VoxAgent stays on Ollama for the entire session.

**Warning signs:** Provider never recovers after a transient failure. Logs show "circuit open for provider X" but never "circuit closed."

**Prevention:**
- Implement the standard three-state circuit breaker: CLOSED (normal) -> OPEN (failing, use fallback) -> HALF_OPEN (probe the primary with one request).
- Half-open transition: after a cooldown period (e.g., 60s), allow one request to the primary. If it succeeds, close the circuit. If it fails, reset the cooldown.
- Log state transitions prominently. Surface the current circuit state in the dashboard health endpoint.

**Phase:** Provider fallback chains.

### Pitfall 4.3: Retry Logic Applied to Non-Idempotent Operations

**What goes wrong:** Exponential backoff retry is correct for `GET`-like operations (LLM chat, health checks). But if applied blindly to all provider calls, you might retry a TTS synthesis that already started playing (producing duplicate speech) or retry a tool execution that already had side effects (running a terminal command twice).

**Warning signs:** The assistant speaks the same sentence twice. A terminal command executes twice. Side effects are doubled after transient errors.

**Prevention:**
- Classify operations as idempotent or non-idempotent. Only auto-retry idempotent operations (LLM chat, STT transcribe, TTS synthesize-without-play).
- For the play step: never retry. If playback fails, skip to the next utterance.
- For skill execution: never auto-retry. Return the error to the user. Let them re-issue the command.
- Apply retry at the provider layer (HTTP request), not at the pipeline layer (skill execution).

**Phase:** Retry logic with exponential backoff.

### Pitfall 4.4: Fallback Chains That Don't Respect Latency Budgets

**What goes wrong:** The fallback chain is `["groq", "openai", "anthropic", "ollama"]`. Groq times out after 5 seconds, OpenAI times out after 5 seconds, Anthropic times out after 5 seconds — the user waits 15 seconds before hitting the local fallback. The voice pipeline has a ~3 second total latency budget. Waiting for three cloud providers to timeout destroys the UX.

**Warning signs:** Response time spikes to 10-20 seconds during provider outages. Users perceive the assistant as dead.

**Prevention:**
- Set aggressive per-provider timeouts: 2-3 seconds for cloud LLM calls, 1 second for health checks. Don't use the httpx default (5s connect + 30s read).
- Use a total fallback budget: if the entire chain hasn't responded in 4 seconds, skip to local immediately.
- Consider racing the primary and a fast fallback concurrently (`asyncio.wait` with `FIRST_COMPLETED`) rather than sequential fallback.

**Phase:** Provider fallback chains.

### Pitfall 4.5: Shared httpx.AsyncClient Lifecycle Mismanagement

**What goes wrong:** CONCERNS.md (3.1) correctly identifies that a new `httpx.AsyncClient` is created per request. The fix is to share one client per provider. But if the client is created at provider `__init__` time and never closed, it leaks connections. If it's closed in `__del__`, it may run after the event loop is closed, causing warnings. If it's shared across event loops (e.g., test isolation), httpx raises `RuntimeError`.

**Warning signs:** `ResourceWarning: unclosed <httpx.AsyncClient>`. Tests that pass individually but fail when run together. Connection pool exhaustion after many requests.

**Prevention:**
- Create the `AsyncClient` lazily on first use, store it on the instance.
- Add an explicit `async def close()` method to each provider. Call it during `VoxAgentApp.stop()`.
- In tests, use `async with httpx.AsyncClient() as client:` in a fixture, not a shared module-level client.
- Set `limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)` to prevent unbounded connection growth.

**Phase:** Provider fallback chains (prerequisite: fix httpx-per-request before adding retry/fallback).

---

## 5. Noise Suppression Without Killing Speech Quality

### Context in VoxAgent

VoxAgent uses Silero VAD with energy fallback for voice activity detection. There is no noise suppression in the audio pipeline. The audio goes raw from the mic to VAD to STT.

### Pitfall 5.1: Applying Aggressive Noise Gate That Clips Speech Onsets

**What goes wrong:** A simple noise gate (mute below threshold, pass above) clips the first 50-100ms of each speech onset because the amplitude ramps up from silence. The first syllable of every word is lost, making Whisper transcription significantly worse.

**Warning signs:** Transcription accuracy drops after adding noise suppression. First words of utterances are garbled. "Hey Vox" sometimes not recognized.

**Prevention:**
- Use spectral noise suppression (e.g., RNNoise, nsnet2) instead of amplitude-based gating. These preserve speech onsets while removing stationary noise.
- If using a noise gate, add a look-ahead buffer (20-40ms) that keeps audio before the gate opens.
- Always A/B test: transcription accuracy BEFORE noise suppression vs. AFTER. If WER increases, the suppression is doing more harm than good.

**Phase:** Noise suppression and adaptive VAD.

### Pitfall 5.2: RNNoise/NSNet2 Adds Processing Latency That Breaks Real-Time

**What goes wrong:** ML-based noise suppression (RNNoise, NSNet2) adds per-frame processing latency. VoxAgent uses 80ms chunks (`CHUNK_DURATION_MS = 80`). If noise suppression takes >80ms per chunk, the pipeline falls behind. Audio queue grows unboundedly (CONCERNS 3.6: unbounded queue).

**Warning signs:** `AudioRecorder._audio_queue` grows over time. Latency between speaking and transcription increases progressively. CPU usage spikes.

**Prevention:**
- Benchmark noise suppression per-chunk on the target hardware. RNNoise processes 10ms frames in <1ms on modern CPUs; it's fine. NSNet2 (ONNX) varies.
- Process noise suppression in the `_on_audio_chunk` callback thread (not on the event loop), so it runs in parallel with other async work.
- Add a queue maxsize (e.g., `asyncio.Queue(maxsize=500)` = 40 seconds). If the queue fills, drop old chunks rather than growing unboundedly.

**Phase:** Noise suppression and adaptive VAD.

### Pitfall 5.3: Noise Suppression Frequency Band Mismatch

**What goes wrong:** RNNoise expects 48kHz input. VoxAgent records at 16kHz. Feeding 16kHz audio to a 48kHz-trained model produces garbage output. Some wrappers silently resample; others don't.

**Warning signs:** Noise suppression produces robotic/distorted output. Audio sounds worse than without suppression.

**Prevention:**
- Match the model to the sample rate. Use `rnnoise` compiled for 48kHz and resample 16kHz -> 48kHz -> process -> 48kHz -> 16kHz. Or use a model trained on 16kHz (many Whisper-optimized preprocessors work at 16kHz).
- `noisereduce` (Python library) works at any sample rate. Less aggressive than RNNoise but no resampling needed. Good starting point.
- Test with actual VoxAgent wake word detection and STT, not just listening tests. What sounds fine to humans may confuse Whisper.

**Phase:** Noise suppression and adaptive VAD.

### Pitfall 5.4: Adaptive VAD Thresholds That Oscillate

**What goes wrong:** Adaptive VAD adjusts its energy/probability threshold based on ambient noise level. If the adaptation window is too short, the threshold oscillates: a loud noise raises it, then quiet period lowers it, then the next speech burst is missed because the threshold just rose again.

**Warning signs:** VAD intermittently fails to detect speech starts. Works fine in silence, unreliable in noisy environments. Threshold logs show rapid oscillation.

**Prevention:**
- Use asymmetric adaptation: slow rise (seconds) and fast fall (hundreds of ms). Noise floors rise slowly; speech onsets are preserved.
- Apply a minimum hold time: once speech is detected, keep the threshold stable for at least 500ms regardless of amplitude changes.
- Silero VAD is probability-based, not energy-based. If using Silero as primary, adaptive energy thresholds are only relevant for the fallback path.

**Phase:** Noise suppression and adaptive VAD.

---

## 6. Retrofitting Error Handling Into an Existing Async Codebase

### Context in VoxAgent

CONCERNS.md (4.4) documents silent failures throughout the pipeline. The main loop catches `(RuntimeError, OSError, KeyError)` broadly. Skills return errors in three different formats (CONCERNS 7.4). No error hierarchy exists.

### Pitfall 6.1: Exception Hierarchy That Nobody Uses

**What goes wrong:** Teams create a beautiful error hierarchy (`VoxAgentError` -> `ProviderError` -> `LLMTimeoutError`, etc.) but don't update existing code to use it. The new exceptions are defined but never raised. Existing bare `except Exception` blocks catch everything regardless of type. The hierarchy exists in `core/errors.py` but has zero callers.

**Warning signs:** The error module has 100+ lines of class definitions but `grep -r "raise VoxAgentError"` returns zero results outside tests. Old code still uses `RuntimeError` and `OSError`.

**Prevention:**
- Introduce the hierarchy incrementally, one module at a time. Start with the most-touched module (Brain).
- For each module: (1) define specific exceptions, (2) update raises, (3) update callers' catch blocks, (4) verify with tests. All four steps for one module before moving to the next.
- Add a ruff/lint rule that flags bare `except Exception` catches. Make it a warning first, then an error once migration is complete.

**Phase:** Robust error handling.

### Pitfall 6.2: Wrapping Every Await in try/except Creates Noise

**What goes wrong:** "Robust error handling" gets interpreted as "wrap every await in try/except." Result: 80% of the code is try/except boilerplate. Errors are caught, logged, and re-raised — or worse, caught and swallowed at every level. The actual error origin is buried in log noise.

**Warning signs:** Every function has a try/except block. Log files show the same error logged 4-5 times as it propagates through layers. Developers add `except Exception: pass` to "fix" errors.

**Prevention:**
- Catch errors at BOUNDARY POINTS only: (1) the main loop in `_run_loop()`, (2) provider HTTP calls, (3) system I/O (audio, filesystem). Let errors propagate naturally through intermediate functions.
- Define a clear rule: "If you can meaningfully recover or translate the error, catch it. If you can only log it, let it propagate."
- The `_run_loop()` already has a top-level catch. That's the right place. Intermediate functions (Brain.process, Hands.execute) should catch only domain-specific errors and translate them to domain exceptions.

**Phase:** Robust error handling.

### Pitfall 6.3: Async Cleanup That Doesn't Run (Missing finally/aexit)

**What goes wrong:** When an async task is cancelled (e.g., during shutdown), `asyncio.CancelledError` bypasses `except Exception`. Resources opened in the task (database connections, audio streams, file handles) are never cleaned up. The `VoxAgentApp.stop()` method exists but if the main task is cancelled before `stop()` runs, cleanup is partial.

**Warning signs:** `ResourceWarning` on shutdown. Database files locked after crash. Audio device busy on restart. `"Error closing audio stream"` in logs.

**Prevention:**
- Use `async with` (context managers) for all resources that need cleanup: database connections, httpx clients, audio streams.
- Catch `CancelledError` explicitly in long-running loops if cleanup is needed: `except asyncio.CancelledError: await self._cleanup(); raise`.
- In `VoxAgentApp.start()`, the `finally: await self.stop()` pattern is already correct. Ensure the same pattern exists in all background tasks.

**Phase:** Robust error handling.

### Pitfall 6.4: Silent Degradation Without User Notification

**What goes wrong:** CONCERNS.md (4.4) documents this: Eyes returns empty WindowInfo on failure, Mouth silently skips, STT returns None. The system appears to work but half its capabilities are broken. The user says "Hey Vox, read my screen" and gets silence with no explanation.

**Warning signs:** User reports "it doesn't work" but logs show no errors. All failures are caught and result in graceful degradation that the user perceives as ignoring them.

**Prevention:**
- Distinguish between "degraded" (module unavailable, tell user) and "failed" (unexpected error, log and recover).
- When a module is unavailable at init time, speak a one-time notification: "Vision is not available in this session."
- When a module fails at runtime, use the TTS error template: `RESPONSE_TEMPLATES["error"]` already exists but is rarely used.
- Track degraded modules in a health registry. Surface it in the dashboard.

**Phase:** Robust error handling + progress feedback.

### Pitfall 6.5: Error Handling in sounddevice Callbacks

**What goes wrong:** The `_on_audio_chunk` callback runs on PortAudio's C thread. Raising an exception in this callback crashes the entire audio subsystem silently (PortAudio aborts the stream). The current code has `contextlib.suppress(asyncio.QueueFull)` which is correct for queue overflow, but any other exception (e.g., numpy error from malformed indata) kills the stream with no recovery.

**Warning signs:** Audio stream silently stops. No more chunks appear in the queue. No error in logs because the exception happened on a C thread that Python can't catch.

**Prevention:**
- Wrap the ENTIRE callback body in a broad try/except that logs but never raises. A callback must never throw.
- Add a heartbeat: if `read_chunk()` returns None more than N consecutive times, the recorder should check `self._stream.active` and attempt to restart.
- Test with malformed audio data (e.g., device unplugged mid-recording) to verify the callback doesn't crash.

**Phase:** Audio pipeline resilience.

---

## 7. Terminal / Shell Command Sandboxing

### Context in VoxAgent

CONCERNS.md (1.5) documents the terminal allowlist bypass: `python`, `pip`, `git`, `node`, `npm` are in `ALLOWED_COMMAND_PREFIXES` but are themselves code execution vectors. `DANGEROUS_SHELL_CHARS` catches metacharacters but not the inherent danger of the allowed commands. PROJECT.md lists "Terminal skill semantic safety (AST-based validation, not regex)" as an active requirement.

### Pitfall 7.1: AST Parsing That Doesn't Cover All Attack Vectors

**What goes wrong:** Teams implement AST-based validation for `python -c "code"` but forget that `python script.py` can execute arbitrary code too. They parse the `-c` argument as Python AST, block `os.system` and `subprocess`, but miss:
- `__import__('os').system('rm -rf /')` — dynamic import
- `eval()`, `exec()`, `compile()` — runtime code generation
- `python -m` — module execution
- `.py` files that import dangerous modules

**Warning signs:** AST checker blocks `import os` but `python -c "__import__('os').system('whoami')"` passes.

**Prevention:**
- Don't try to make `python -c` safe. It's impossible. Remove `python` and `node` from the allowlist entirely. They are arbitrary code execution by definition.
- If Python execution is needed, sandbox it: `--isolated` mode, `--safe-path`, or a separate restricted interpreter.
- AST validation is appropriate for SIMPLE commands (file paths, grep patterns). Not for Turing-complete language subsets.

**Phase:** Terminal safety.

### Pitfall 7.2: Allowlist Approach Is Inherently Fragile

**What goes wrong:** The current approach is a prefix allowlist + blocklist. Every new "safe" command added to the allowlist might have dangerous subcommands. `git` can run hooks (`git clone` + post-checkout hook = RCE). `pip install` can run `setup.py` (arbitrary code). The allowlist gives a false sense of security.

**Warning signs:** Security review reveals that 5 of 18 "allowed" commands can execute arbitrary code. New commands are added to the allowlist without security review.

**Prevention:**
- Invert the model: instead of "allow these commands," define "allow these SPECIFIC command patterns." E.g., `ls [path]`, `cat [path]`, `grep [pattern] [path]` — with argument validation.
- For commands that inherently execute code (`python`, `node`, `pip`, `git`), require explicit user voice confirmation (which VoxAgent's permission system already supports).
- Consider a semantic approach: parse the command into a structured intent (`{action: "list_files", path: "/home"}`) and execute it via Python APIs (pathlib, shutil) instead of shelling out. This eliminates shell injection entirely.

**Phase:** Terminal safety.

### Pitfall 7.3: Unicode Normalization Bypass

**What goes wrong:** The current code does `unicodedata.normalize('NFKC', command)` which is good, but there are Unicode tricks that survive NFKC:
- Right-to-left override characters (`U+202E`) can visually reorder characters while the actual string is malicious.
- Zero-width joiners/non-joiners can break shlex parsing.
- Homoglyphs (Cyrillic 'а' vs Latin 'a') can bypass exact-match blocklists.

**Warning signs:** A command that looks safe in logs but executes something different. shlex.split produces unexpected tokens.

**Prevention:**
- After NFKC normalization, strip ALL characters outside printable ASCII (0x20-0x7E) for command strings. Commands don't need Unicode.
- Validate that `shlex.split()` output matches expected patterns AFTER normalization, not before.
- Add adversarial test cases with RTL overrides, zero-width characters, and homoglyphs.

**Phase:** Terminal safety.

### Pitfall 7.4: subprocess.run Without Resource Limits

**What goes wrong:** A command passes the safety filter but forks uncontrollably (`:(){ :|:& };:` is blocked by shell chars, but `python -c "while True: pass"` is an infinite loop). `COMMAND_TIMEOUT_S = 30` limits wall time but not CPU, memory, or child processes. A command can consume all RAM or spawn 10,000 processes before the timeout kills it.

**Warning signs:** A "safe" command (e.g., `find / -name "*.py"`) consumes excessive CPU for 30 seconds. System becomes unresponsive during command execution.

**Prevention:**
- On Linux: use `subprocess.run` with `preexec_fn` that sets `resource.setrlimit()` for CPU time, memory, and number of processes.
- On Windows: use job objects (`win32job`) to limit the process tree, or use `CREATE_BREAKAWAY_FROM_JOB` with resource limits.
- Reduce `COMMAND_TIMEOUT_S` to 10 seconds for most commands. 30 seconds is too long for a voice assistant where the user is waiting.
- Add a `COMMAND_MEMORY_LIMIT_MB = 256` constant and enforce it.

**Phase:** Terminal safety.

---

## 8. Cross-Cutting Pitfalls

### Pitfall 8.1: Testing Hardening Features With Mocks Instead of Real Audio

**What goes wrong:** All streaming TTS, barge-in, echo cancellation, and noise suppression tests use mocked audio data (synthetic sine waves or silence). They pass, but real-world audio has background noise, mic bleed, codec artifacts, and timing jitter that mocks don't reproduce.

**Warning signs:** 100% test pass rate but the first real-world test fails. "Works in CI, broken on my desk."

**Prevention:**
- Create a `test_fixtures/audio/` directory with real recorded samples: speech with background noise, mic feedback, overlapping speech.
- Integration tests should use real sounddevice with loopback (where available) or recorded audio files fed through the pipeline.
- Unit tests can mock providers, but integration tests for audio features MUST use real audio data.

**Phase:** All audio-related phases.

### Pitfall 8.2: Implementing Features Independently That Must Interact

**What goes wrong:** Streaming TTS, barge-in, and echo cancellation are implemented in three separate phases by treating them as independent features. But they share the same audio I/O layer. Streaming TTS changes the playback from `sd.play()` to `sd.OutputStream`. Barge-in needs to stop that OutputStream. Echo cancellation needs the OutputStream's reference signal. Implementing them independently means refactoring the audio layer three times.

**Warning signs:** Phase 2 (barge-in) requires rewriting Phase 1's (streaming TTS) playback layer. Phase 3 (echo cancellation) requires rewriting Phase 2's barge-in detection. Each phase invalidates the previous.

**Prevention:**
- Design the audio I/O layer ONCE upfront to support all three features, even if only streaming TTS is implemented first.
- The audio layer should be: `AudioOutput` class with `sd.OutputStream`, a chunk queue, a stop signal, and a reference signal tap. This single design serves streaming (queue), barge-in (stop signal), and AEC (reference tap).
- Implement the full `AudioOutput` skeleton in Phase 1, populate barge-in in Phase 2, wire AEC in Phase 3.

**Phase:** Architecture design before Phase 1.

### Pitfall 8.3: Memory DB Cleanup That Breaks Active References

**What goes wrong:** The memory cleanup policy deletes old conversations to bound growth. But the Brain module may hold references to recent conversation context for multi-turn dialogues. If cleanup runs while Brain is building a context window, the conversation history is truncated mid-interaction.

**Warning signs:** The assistant "forgets" context mid-conversation. Multi-turn dialogues break after cleanup runs.

**Prevention:**
- Cleanup only deletes records older than a safe horizon (e.g., 7 days). Never delete within the current session.
- Use soft deletes (mark as archived) rather than hard deletes. Hard delete on a separate schedule.
- Coordinate with Brain's context window: never delete conversations that are in the active context.

**Phase:** Memory DB bounded growth.

### Pitfall 8.4: Progress Feedback That Blocks the Voice Pipeline

**What goes wrong:** Long-running skills need to report progress ("Downloading... 50%"). If progress feedback goes through the normal `Mouth.speak()` path, it blocks the main loop. The user can't interrupt a long skill because the pipeline is stuck waiting for the progress TTS to finish.

**Warning signs:** Progress announcements queue up and play back-to-back. User can't cancel a long operation because the pipeline is blocked on speaking progress updates.

**Prevention:**
- Progress feedback should use earcons (short beeps) rather than TTS for intermediate updates. TTS only for start and completion.
- Progress TTS should be interruptible (requires barge-in to be implemented first).
- Use a separate low-priority TTS queue for progress messages. If a new progress update arrives before the old one finishes, drop the old one.

**Phase:** Progress feedback (depends on TTS interruption being done first).

---

## Summary: Phase Dependency Map

```
                    ┌─────────────────────────┐
                    │  Audio I/O Layer Design  │
                    │  (shared architecture)   │
                    └─────────┬───────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              v               v               v
     ┌────────────┐  ┌──────────────┐  ┌─────────────┐
     │ Streaming   │  │ Noise        │  │ Error       │
     │ TTS         │  │ Suppression  │  │ Hierarchy   │
     └──────┬─────┘  └──────┬───────┘  └──────┬──────┘
            │               │                  │
            v               │                  v
     ┌────────────┐         │          ┌─────────────┐
     │ Barge-in   │◄────────┘          │ Provider    │
     │ + Echo AEC │                    │ Fallback    │
     └──────┬─────┘                    └──────┬──────┘
            │                                 │
            v                                 v
     ┌────────────┐                    ┌─────────────┐
     │ Progress   │                    │ Retry Logic │
     │ Feedback   │                    └─────────────┘
     └────────────┘

     ┌────────────┐                    ┌─────────────┐
     │ Terminal   │                    │ Memory      │
     │ Safety     │ (independent)      │ Cleanup     │
     └────────────┘                    └─────────────┘
```

### Critical Ordering Constraints

1. **Audio I/O redesign MUST precede streaming TTS, barge-in, and echo cancellation.** Otherwise each phase rewrites the previous.
2. **Barge-in and echo cancellation MUST be designed together.** They are architecturally inseparable.
3. **Error hierarchy MUST precede provider fallback.** Fallback logic needs typed errors to distinguish transient vs. permanent failures.
4. **httpx client sharing MUST precede retry logic.** Retry on a per-request client creates new connections on each retry.
5. **Streaming TTS MUST precede barge-in.** You can't interrupt a blocking `sd.play()` + `sd.wait()` cleanly.
6. **Barge-in MUST precede progress feedback.** Progress messages must be interruptible.
7. **Terminal safety and memory cleanup are independent** and can be implemented in any phase.

---

*This document should be reviewed after the architecture design phase and updated as implementation reveals new pitfalls.*
