# Phase 08: VAD Hardening — Summary

**Date:** 2026-04-10
**Commit:** `675c639` feat(08): add AdaptiveVAD with ambient noise estimation and hysteresis state machine

---

## Requirements Addressed

| ID | Requirement | Status |
|----|-------------|--------|
| AUDR-02 | VAD thresholds adapt to ambient noise level (not hardcoded RMS 500.0) | Done |
| AUDR-03 | VAD hysteresis — require N consecutive speech frames to start, M silence frames to stop | Done |

---

## What Was Built

### 1. `agent/core/audio/adaptive_vad.py` (new)

**AdaptiveVAD** — wraps the existing `VoiceActivityDetector` with two capabilities:

**Ambient Noise Estimator (AUDR-02):**
- Exponential Moving Average (EMA) of RMS energy during silence/pending periods
- `dynamic_threshold = ambient_rms * multiplier` (default multiplier: 3.0)
- EMA alpha of 0.04 converges within ~25 frames (~2s at 80ms chunks)
- Clamped to `[MIN_ENERGY_THRESHOLD=100, MAX_ENERGY_THRESHOLD=5000]`
- Updates during SILENCE and PENDING_SPEECH states (critical for handling sudden noise increases)
- Freezes during confirmed SPEECH and PENDING_SILENCE (avoids speech contamination)
- Ignores extreme spikes above `AMBIENT_UPDATE_CEILING=3000` (transient non-speech noise)

**Hysteresis State Machine (AUDR-03):**
- 4-state machine: `SILENCE → PENDING_SPEECH → SPEECH → PENDING_SILENCE → SILENCE`
- `speech_start_frames=3` consecutive speech frames required to confirm speech start
- `silence_end_frames=15` consecutive silence frames (~1.2s) required to confirm speech end
- Short pauses (<500ms = ~6 frames) within sentences do NOT trigger end-of-speech
- Single noise bursts do NOT trigger false speech starts

**Configuration:**
- `AdaptiveVADConfig` frozen dataclass with all tunable parameters
- Fully configurable multiplier, EMA alpha, and frame thresholds

### 2. `agent/core/audio/vad.py` (modified)

- Added `detect_speech_with_energy()` method for custom energy thresholds (integration point for AdaptiveVAD)
- Preserved full backward compatibility — existing `detect_speech()` unchanged
- Updated docstrings to reference AdaptiveVAD wrapper pattern

### 3. `agent/core/ears.py` (modified)

- Replaced raw `VoiceActivityDetector` usage with `AdaptiveVAD` wrapper
- `_wait_for_wake_word()` now feeds chunks to AdaptiveVAD during idle — calibrates ambient noise continuously
- `_record_until_silence()` rewritten to use hysteresis-aware state machine:
  - Tracks `speech_confirmed` flag — only stops after speech has been confirmed at least once
  - Checks `HysteresisState.SILENCE` (not raw frame count) for end-of-speech
  - Trims trailing silence frames with small buffer (keeps 2 frames)
- `AdaptiveVAD.reset()` called at recording start for fresh session
- Exposed `adaptive_vad` property for metric inspection

### 4. `agent/core/audio/__init__.py` (modified)

- Added `AdaptiveVAD` and `AdaptiveVADConfig` to barrel exports

### 5. `agent/tests/test_adaptive_vad.py` (new, 44 tests)

- `TestComputeRms` — RMS computation correctness (3 tests)
- `TestClamp` — clamp helper (4 tests)
- `TestAdaptiveVADConfig` — config defaults, custom values, frozen (3 tests)
- `TestAdaptiveVADInit` — initial state, thresholds, clamping (6 tests)
- `TestAmbientNoiseEstimation` — AUDR-02 (5 tests):
  - Ambient adapts during silence
  - Ambient freezes during confirmed speech
  - Extreme noise spikes ignored
  - Adapts within 2s window
  - Threshold decreases in quiet room
- `TestHysteresis` — AUDR-03 (7 tests):
  - Single frame doesn't trigger
  - N consecutive frames trigger start
  - Interrupted speech resets counter
  - Short pause doesn't end speech
  - Long silence ends speech
  - Speech resumes after short pause
  - 500ms pause preserves recording
- `TestReset` — reset behavior (2 tests)
- `TestCustomConfig` — non-default configurations (3 tests)
- `TestNoisyEnvironments` — realistic scenarios (3 tests):
  - Fan noise calibration
  - Quiet room false trigger rate
  - Environment transition adaptation
- `TestStateTransitions` — all valid state transitions (6 tests)
- `TestHysteresisStateEnum` — enum completeness (2 tests)

---

## Success Criteria Verification

| # | Criterion | Verified By |
|---|-----------|-------------|
| 1 | VAD detects speech with ambient noise up to 60dB without false triggers | `test_fan_noise_calibration`, `test_quiet_room_no_false_triggers` |
| 2 | Short pauses (<500ms) don't prematurely end recording | `test_500ms_pause_does_not_end_recording`, `test_short_pause_does_not_end_speech` |
| 3 | VAD adapts within 2s of environment change | `test_threshold_adapts_within_2s`, `test_environment_transition` |
| 4 | No regression in quiet-room accuracy (false trigger rate <1%) | `test_quiet_room_no_false_triggers` (0 triggers in 100 frames) |

---

## Design Decisions

1. **PENDING_SPEECH ambient updates**: When ambient noise suddenly increases (fan turns on), the adaptive VAD temporarily sees noise as potential speech. By updating ambient during PENDING_SPEECH (not just SILENCE), the threshold catches up before false-confirming noise as speech. Only confirmed SPEECH freezes ambient updates.

2. **Wrapper pattern over modification**: AdaptiveVAD wraps VoiceActivityDetector rather than modifying it. This preserves backward compatibility — existing code using `VoiceActivityDetector.detect_speech()` directly is unaffected.

3. **Configurable everything**: All thresholds are exposed via `AdaptiveVADConfig` frozen dataclass, allowing per-environment tuning without code changes.

4. **Hysteresis in ears.py**: The `_record_until_silence()` method tracks a `speech_confirmed` flag independently of the state machine. This prevents premature termination when the user pauses before starting to speak (post-wake-word silence).

---

## Regression Status

- **408/408 tests pass** (excluding pre-existing `test_mouth.py` Vietnamese encoding failure)
- **0 regressions** from Phase 8 changes
- Existing `test_audio.py` VAD tests continue passing (backward compatible)
