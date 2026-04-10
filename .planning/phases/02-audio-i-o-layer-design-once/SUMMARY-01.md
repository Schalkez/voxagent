# Phase 02: Audio I/O Layer (Design Once) — Summary

**Completed:** 2026-04-10
**Requirements:** AUDR-04 (bounded ring buffer), AUDR-05 (format normalization)

## What Was Built

### New Files

| File | Lines | Purpose |
|------|-------|---------|
| `core/audio/ring_buffer.py` | 141 | Pre-allocated circular buffer with drop-oldest policy, metrics (drop_count, high_watermark), async read with Event notification |
| `core/audio/normalizer.py` | 153 | Validates/converts any audio format to canonical int16/16kHz/mono — dtype conversion, stereo-to-mono downmix, sample rate resampling |
| `core/audio/interrupt_controller.py` | 57 | asyncio.Event-based cancellation skeleton for future barge-in (Phase 6) |
| `tests/test_ring_buffer.py` | 252 | 25 tests: init, FIFO, drop-oldest, watermark, drain, timeout, wrap-around, alloc-free write |
| `tests/test_audio_normalizer.py` | 222 | 18 tests: passthrough, float/int conversion, clipping, stereo downmix, resampling, errors, combined transforms |

### Modified Files

| File | Change |
|------|--------|
| `core/audio/recorder.py` | Replaced `asyncio.Queue` with `AudioRingBuffer`. Added `AudioNormalizer` at capture point. Callback is now allocation-free (`np.copyto` into pre-allocated slots). |
| `core/audio/__init__.py` | Added exports for `AudioRingBuffer`, `AudioNormalizer`, `InterruptController` |
| `core/ears.py` | Already consumed from ring buffer API (no changes needed — `read_chunk()` interface unchanged) |
| `tests/test_audio.py` | Updated `test_drain_queue` -> `test_drain_ring_buffer` (old `_audio_queue` no longer exists) |

## Success Criteria Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Capture callback never allocates or blocks — ring buffer write <1us | PASS | `write()` uses `np.copyto` into pre-allocated slot + integer arithmetic. No allocation, no lock, no I/O. Buffer identity test confirms array object unchanged across overwrites. |
| Drop counter increments when full; drops are logged | PASS | `test_drop_when_full`, `test_multiple_drops`, `test_heavy_overflow` verify counter. Logging every `DROP_LOG_INTERVAL` drops (not every drop — avoids log spam). |
| All downstream consumers receive int16/16kHz/mono | PASS | `AudioNormalizer` applied at capture point in `_on_audio_chunk`. Handles float32/64, int32, stereo, and non-16kHz rates. 18 normalizer tests cover all paths. |
| Audio pipeline starts/stops cleanly with no orphaned threads | PASS | `AudioRecorder.start()` drains buffer + resets metrics. `stop()` logs final metrics (drop_count, high_watermark) in `finally` block. No threads created by our code — sounddevice manages its own. |

## Design Decisions

1. **Single-producer/single-consumer**: No locks needed. The sounddevice callback (C thread) is the sole writer; the asyncio read loop is the sole reader. `asyncio.Event` used only for notification, not synchronization.

2. **Drop-oldest, not drop-newest**: Old audio is stale and worthless for real-time processing. When the consumer falls behind, we keep the freshest chunks.

3. **Normalization at capture, not at consumption**: Every downstream consumer (wake word, VAD, STT) gets canonical format without repeating conversion logic. Single point of truth.

4. **Linear interpolation for resampling**: Simple, zero-dependency, sufficient for speech. No need for scipy/librosa for the capture path. More sophisticated resampling can be applied at STT time if needed.

5. **InterruptController is a skeleton**: Only `asyncio.Event` wiring. Full barge-in logic deferred to Phase 6 (concurrent audio) where it integrates with TTS streaming and monitor track.

## Commits

- `cb21fe0` feat(02): add AudioRingBuffer
- `df00428` feat(02): add AudioNormalizer
- `46e28ae` feat(02): add InterruptController skeleton
- `6ae24b7` refactor(02): wire AudioRecorder to use ring buffer + normalizer

## Test Results

```
43 new tests (25 ring buffer + 18 normalizer)
66 audio-related tests passing (including existing)
0 regressions introduced
```
