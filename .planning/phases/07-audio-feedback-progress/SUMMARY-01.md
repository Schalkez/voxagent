# Phase 07: Audio Feedback & Progress — Summary

**Status:** Complete
**Date:** 2026-04-10

## Requirements Delivered

| ID | Requirement | Status |
|----|-------------|--------|
| ERRH-03 | Error earcon plays before spoken error (distinct beep for errors vs success) | Done |
| PROG-01 | Immediate acknowledgment earcon when wake word detected | Done |
| PROG-02 | Timeout-based progress update — if skill >3s, speak "Dang xu ly..." with periodic updates | Done |

## Files Created

| File | Purpose |
|------|---------|
| `agent/core/audio/earcons.py` | Earcon system: programmatic tone generation, caching, async playback |
| `agent/tests/test_earcons.py` | 24 tests covering tone generation, caching, playback, and Mouth integration |
| `agent/tests/test_progress.py` | 11 tests covering progress monitor timing, cancellation, and edge cases |

## Files Modified

| File | Change |
|------|--------|
| `agent/core/audio/__init__.py` | Added `EarconType`, `play_earcon` to audio sub-package exports |
| `agent/core/mouth.py` | Replaced `play_earcon(str)` TODO stub with `play_earcon(EarconType)` using earcon system |
| `agent/core/ears.py` | PROG-01: Fire acknowledge earcon as background task immediately after wake word detection |
| `agent/core/app.py` | ERRH-03: Play error earcon before spoken errors in pipeline loop and VoxError handler |
| `agent/core/hands.py` | PROG-02: Added `_run_with_progress()` and `_announce_progress()` for long-running skills |
| `agent/tests/test_coverage_boost.py` | Updated existing tests to use `EarconType` enum instead of old string API |

## Architecture Decisions

### Earcon Generation (earcons.py)
- **Programmatic tones** via numpy sine waves — no bundled WAV files needed
- **Pre-generated cache**: Tones built lazily on first access, then reused (zero allocation at playback)
- **Three distinct sounds**:
  - ACKNOWLEDGE: Rising two-tone sweep (800Hz->1200Hz, 200ms) — cheerful, confirms detection
  - ERROR: Descending sweep (600Hz->300Hz, 300ms) — harsh, signals problem
  - PROGRESS: Soft single tone (1000Hz, 150ms) — neutral, non-intrusive
- **Anti-click fades**: 5ms fade-in/out on all tones prevents audible pops
- **Non-blocking playback**: `asyncio.to_thread()` wraps `sounddevice.play()` so pipeline isn't stalled

### Wake Word Earcon (PROG-01)
- Fired as `asyncio.create_task()` in `ears.py` immediately after `_wait_for_wake_word()` returns
- Background task means recording starts in parallel — earcon does not add latency to speech capture
- Latency target: <200ms from wake word detection to audio output

### Error Earcon (ERRH-03)
- Wired into three locations in `app.py._run_loop()`:
  1. Before speaking `result.tts_response` when `result.success is False`
  2. Before speaking `result.error` fallback message
  3. Before speaking `VoxError.user_message` in the exception handler
- Earcon plays via `await` (blocking) to ensure it completes before TTS starts

### Progress Monitor (PROG-02)
- `Hands._run_with_progress()` spawns a background `_announce_progress()` task alongside skill execution
- Initial delay: 3 seconds — fast skills never trigger progress
- Repeat interval: 5 seconds between updates
- Rotating messages: "Dang xu ly...", "Van dang xu ly...", "Gan xong roi...", "Van dang thuc hien, xin cho..."
- Progress task is always cancelled when skill completes (via `try/finally`)
- Gracefully handles missing Mouth (no-op) and Mouth failures (logs warning, continues)

## Test Results

```
35 new tests (24 earcon + 11 progress)
525 total tests passing
0 regressions introduced
```

## Commits

1. `5d27efb` — feat(07): add earcon audio feedback system with tone generation
2. `33a36e5` — feat(07): wire earcon into mouth.py replacing TODO stub
3. `805d3e1` — feat(07): PROG-01 acknowledge earcon on wake word detection
4. `9904160` — feat(07): ERRH-03 error earcon before spoken errors in pipeline
5. `ab36bd0` — feat(07): PROG-02 progress monitor for long-running skills
6. `b174537` — test(07): add earcon and progress monitor tests
