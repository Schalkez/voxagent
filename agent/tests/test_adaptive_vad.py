"""Tests for AdaptiveVAD: ambient-aware speech detection with hysteresis.

Tests AUDR-02 (adaptive thresholds) and AUDR-03 (hysteresis) requirements.
"""

from __future__ import annotations

import numpy as np
import pytest

from core.audio.adaptive_vad import (
    AMBIENT_UPDATE_CEILING,
    DEFAULT_AMBIENT_MULTIPLIER,
    DEFAULT_EMA_ALPHA,
    DEFAULT_SILENCE_END_FRAMES,
    DEFAULT_SPEECH_START_FRAMES,
    INITIAL_AMBIENT_RMS,
    MAX_ENERGY_THRESHOLD,
    MIN_ENERGY_THRESHOLD,
    AdaptiveVAD,
    AdaptiveVADConfig,
    HysteresisState,
    _clamp,
    _compute_rms,
)
from core.audio.vad import VoiceActivityDetector


# -- Helpers --


def _silence_chunk(rms_level: float = 50.0, samples: int = 1280) -> np.ndarray:
    """Create an audio chunk with a specific RMS level (quiet)."""
    # RMS = sqrt(mean(x^2)), so for constant signal: value = rms
    return np.full(samples, int(rms_level), dtype=np.int16)


def _speech_chunk(rms_level: float = 5000.0, samples: int = 1280) -> np.ndarray:
    """Create an audio chunk with high RMS (speech-like)."""
    return np.full(samples, int(rms_level), dtype=np.int16)


def _zero_chunk(samples: int = 1280) -> np.ndarray:
    """Create a silent (zero) audio chunk."""
    return np.zeros(samples, dtype=np.int16)


def _make_vad(energy_threshold: float = 100.0) -> VoiceActivityDetector:
    """Create a VoiceActivityDetector in energy-fallback mode (no Silero)."""
    return VoiceActivityDetector(energy_threshold=energy_threshold)


def _make_adaptive_vad(
    energy_threshold: float = 100.0,
    config: AdaptiveVADConfig | None = None,
) -> AdaptiveVAD:
    """Create an AdaptiveVAD with energy-fallback VAD."""
    vad = _make_vad(energy_threshold)
    return AdaptiveVAD(vad=vad, config=config)


# -- Module-Level Helper Tests --


class TestComputeRms:
    """Test _compute_rms helper function."""

    def test_zero_signal(self) -> None:
        """Zero signal has zero RMS."""
        chunk = np.zeros(1280, dtype=np.int16)
        assert _compute_rms(chunk) == 0.0

    def test_constant_signal(self) -> None:
        """Constant signal: RMS equals absolute value."""
        chunk = np.full(1280, 1000, dtype=np.int16)
        rms = _compute_rms(chunk)
        assert abs(rms - 1000.0) < 1.0

    def test_negative_signal(self) -> None:
        """Negative constant: RMS equals absolute value."""
        chunk = np.full(1280, -500, dtype=np.int16)
        rms = _compute_rms(chunk)
        assert abs(rms - 500.0) < 1.0


class TestClamp:
    """Test _clamp helper function."""

    def test_within_range(self) -> None:
        assert _clamp(50.0, 0.0, 100.0) == 50.0

    def test_below_minimum(self) -> None:
        assert _clamp(-10.0, 0.0, 100.0) == 0.0

    def test_above_maximum(self) -> None:
        assert _clamp(200.0, 0.0, 100.0) == 100.0

    def test_at_boundary(self) -> None:
        assert _clamp(0.0, 0.0, 100.0) == 0.0
        assert _clamp(100.0, 0.0, 100.0) == 100.0


# -- Config Tests --


class TestAdaptiveVADConfig:
    """Test AdaptiveVADConfig defaults."""

    def test_defaults(self) -> None:
        config = AdaptiveVADConfig()
        assert config.ambient_multiplier == DEFAULT_AMBIENT_MULTIPLIER
        assert config.ema_alpha == DEFAULT_EMA_ALPHA
        assert config.speech_start_frames == DEFAULT_SPEECH_START_FRAMES
        assert config.silence_end_frames == DEFAULT_SILENCE_END_FRAMES

    def test_custom_values(self) -> None:
        config = AdaptiveVADConfig(
            ambient_multiplier=4.0,
            ema_alpha=0.1,
            speech_start_frames=5,
            silence_end_frames=20,
        )
        assert config.ambient_multiplier == 4.0
        assert config.ema_alpha == 0.1
        assert config.speech_start_frames == 5
        assert config.silence_end_frames == 20

    def test_frozen(self) -> None:
        config = AdaptiveVADConfig()
        with pytest.raises(AttributeError):
            config.ambient_multiplier = 5.0  # type: ignore[misc]


# -- AdaptiveVAD Initialization --


class TestAdaptiveVADInit:
    """Test AdaptiveVAD initialization and properties."""

    def test_initial_state_is_silence(self) -> None:
        avad = _make_adaptive_vad()
        assert avad.state == HysteresisState.SILENCE

    def test_initial_ambient_rms(self) -> None:
        avad = _make_adaptive_vad()
        assert avad.ambient_rms == INITIAL_AMBIENT_RMS

    def test_initial_is_speech_active_false(self) -> None:
        avad = _make_adaptive_vad()
        assert avad.is_speech_active is False

    def test_dynamic_threshold_initial(self) -> None:
        avad = _make_adaptive_vad()
        expected = INITIAL_AMBIENT_RMS * DEFAULT_AMBIENT_MULTIPLIER
        assert avad.dynamic_threshold == expected

    def test_dynamic_threshold_clamped_min(self) -> None:
        """When ambient is very low, threshold is clamped to minimum."""
        avad = _make_adaptive_vad()
        avad._ambient_rms = 1.0  # very quiet
        assert avad.dynamic_threshold == MIN_ENERGY_THRESHOLD

    def test_dynamic_threshold_clamped_max(self) -> None:
        """When ambient is very high, threshold is clamped to maximum."""
        avad = _make_adaptive_vad()
        avad._ambient_rms = 10000.0  # unrealistically loud
        assert avad.dynamic_threshold == MAX_ENERGY_THRESHOLD


# -- AUDR-02: Adaptive Thresholds --


class TestAmbientNoiseEstimation:
    """AUDR-02: VAD thresholds adapt to ambient noise level."""

    def test_ambient_adapts_during_silence(self) -> None:
        """Ambient RMS converges toward actual noise floor during silence."""
        avad = _make_adaptive_vad()
        target_noise = 200.0
        quiet_chunk = _silence_chunk(rms_level=target_noise)

        # Feed 50 silence frames (~4s at 80ms) — should converge
        for _ in range(50):
            avad.process_chunk(quiet_chunk)

        # Should be close to target (EMA converges within ~25 frames)
        assert abs(avad.ambient_rms - target_noise) < 20.0

    def test_ambient_does_not_adapt_during_confirmed_speech(self) -> None:
        """Ambient RMS is frozen while confirmed speech is active.

        Note: ambient DOES update during PENDING_SPEECH (to handle noise
        ramp-ups), but freezes once speech is confirmed.
        """
        avad = _make_adaptive_vad()

        # Get into confirmed speech state
        loud = _speech_chunk(rms_level=5000.0)
        for _ in range(DEFAULT_SPEECH_START_FRAMES):
            avad.process_chunk(loud)
        assert avad.state == HysteresisState.SPEECH
        ambient_at_speech_start = avad.ambient_rms

        # Feed 20 more loud speech frames
        for _ in range(20):
            avad.process_chunk(loud)

        # Ambient should NOT have changed during confirmed speech
        assert avad.ambient_rms == ambient_at_speech_start

    def test_ambient_ignores_extreme_noise_spikes(self) -> None:
        """Transient loud non-speech noise does not pollute ambient estimate."""
        avad = _make_adaptive_vad()

        # Calibrate to quiet
        quiet = _silence_chunk(rms_level=100.0)
        for _ in range(30):
            avad.process_chunk(quiet)
        ambient_before = avad.ambient_rms

        # Single extreme spike (above AMBIENT_UPDATE_CEILING)
        extreme = _silence_chunk(rms_level=AMBIENT_UPDATE_CEILING + 500)
        avad._state = HysteresisState.SILENCE  # ensure in silence state
        avad._consecutive_speech = 0
        avad.process_chunk(extreme)

        # Ambient should not have jumped
        assert abs(avad.ambient_rms - ambient_before) < 10.0

    def test_threshold_adapts_within_2s(self) -> None:
        """AUDR-02 success criterion: adapts within ~2s (~25 frames at 80ms)."""
        avad = _make_adaptive_vad()

        # Start with default ambient, switch to noisy environment
        noisy = _silence_chunk(rms_level=800.0)
        for i in range(25):
            avad.process_chunk(noisy)

        # After 25 frames of noise at RMS 800, threshold should be
        # significantly higher than the initial threshold
        initial_threshold = INITIAL_AMBIENT_RMS * DEFAULT_AMBIENT_MULTIPLIER
        assert avad.dynamic_threshold > initial_threshold * 1.2

    def test_threshold_decreases_in_quiet_room(self) -> None:
        """Threshold drops when moving to a quieter environment."""
        avad = _make_adaptive_vad()
        avad._ambient_rms = 800.0  # start in noisy room

        # Move to quiet room
        quiet = _silence_chunk(rms_level=50.0)
        for _ in range(50):
            avad.process_chunk(quiet)

        assert avad.dynamic_threshold < 800.0 * DEFAULT_AMBIENT_MULTIPLIER


# -- AUDR-03: Hysteresis --


class TestHysteresis:
    """AUDR-03: VAD hysteresis prevents premature start/stop."""

    def test_single_speech_frame_does_not_trigger(self) -> None:
        """One loud frame is not enough to trigger speech start."""
        avad = _make_adaptive_vad()
        loud = _speech_chunk(rms_level=5000.0)

        avad.process_chunk(loud)

        assert avad.state == HysteresisState.PENDING_SPEECH
        assert avad.is_speech_active is False

    def test_n_consecutive_speech_frames_trigger_start(self) -> None:
        """N consecutive speech frames trigger speech start."""
        avad = _make_adaptive_vad()
        loud = _speech_chunk(rms_level=5000.0)

        for _ in range(DEFAULT_SPEECH_START_FRAMES):
            avad.process_chunk(loud)

        assert avad.state == HysteresisState.SPEECH
        assert avad.is_speech_active is True

    def test_speech_interrupted_by_silence_resets_counter(self) -> None:
        """If speech frames are interrupted by silence, counter resets."""
        avad = _make_adaptive_vad()
        loud = _speech_chunk(rms_level=5000.0)
        quiet = _zero_chunk()

        # Almost enough speech frames
        for _ in range(DEFAULT_SPEECH_START_FRAMES - 1):
            avad.process_chunk(loud)

        # Silence interrupts
        avad.process_chunk(quiet)

        # Not enough consecutive speech
        assert avad.state == HysteresisState.SILENCE

    def test_short_pause_does_not_end_speech(self) -> None:
        """Short silence during speech does not trigger end (AUDR-03).

        A pause of < silence_end_frames should NOT end recording.
        This tests the core hysteresis requirement.
        """
        avad = _make_adaptive_vad()
        loud = _speech_chunk(rms_level=5000.0)
        quiet = _zero_chunk()

        # Start speech
        for _ in range(DEFAULT_SPEECH_START_FRAMES):
            avad.process_chunk(loud)
        assert avad.is_speech_active is True

        # Short pause (less than silence_end_frames)
        short_pause = DEFAULT_SILENCE_END_FRAMES - 5
        for _ in range(short_pause):
            avad.process_chunk(quiet)

        # Should still be in speech/pending_silence, NOT silence
        assert avad.is_speech_active is True
        assert avad.state == HysteresisState.PENDING_SILENCE

    def test_long_silence_ends_speech(self) -> None:
        """M consecutive silence frames after speech triggers end."""
        avad = _make_adaptive_vad()
        loud = _speech_chunk(rms_level=5000.0)
        quiet = _zero_chunk()

        # Start speech
        for _ in range(DEFAULT_SPEECH_START_FRAMES):
            avad.process_chunk(loud)
        assert avad.is_speech_active is True

        # Long silence
        for _ in range(DEFAULT_SILENCE_END_FRAMES):
            avad.process_chunk(quiet)

        assert avad.state == HysteresisState.SILENCE
        assert avad.is_speech_active is False

    def test_speech_resumes_after_short_pause(self) -> None:
        """Speech can resume after a short pause without re-triggering start."""
        avad = _make_adaptive_vad()
        loud = _speech_chunk(rms_level=5000.0)
        quiet = _zero_chunk()

        # Start speech
        for _ in range(DEFAULT_SPEECH_START_FRAMES):
            avad.process_chunk(loud)

        # Short pause
        for _ in range(5):
            avad.process_chunk(quiet)
        assert avad.is_speech_active is True

        # Resume speech — should immediately go back to SPEECH
        avad.process_chunk(loud)
        assert avad.state == HysteresisState.SPEECH

    def test_500ms_pause_does_not_end_recording(self) -> None:
        """Success criterion: <500ms pauses within a sentence don't end recording.

        At 80ms per chunk, 500ms = ~6 frames. Default silence_end_frames=15.
        """
        avad = _make_adaptive_vad()
        loud = _speech_chunk(rms_level=5000.0)
        quiet = _zero_chunk()
        frames_for_500ms = int(500 / 80)  # 6 frames

        # Start speech
        for _ in range(DEFAULT_SPEECH_START_FRAMES + 5):
            avad.process_chunk(loud)

        # 500ms pause
        for _ in range(frames_for_500ms):
            avad.process_chunk(quiet)

        assert avad.is_speech_active is True, "500ms pause should NOT end recording"


# -- Reset --


class TestReset:
    """Test AdaptiveVAD reset behavior."""

    def test_reset_clears_state(self) -> None:
        avad = _make_adaptive_vad()
        loud = _speech_chunk(rms_level=5000.0)

        # Get into speech state
        for _ in range(DEFAULT_SPEECH_START_FRAMES):
            avad.process_chunk(loud)
        assert avad.is_speech_active is True

        avad.reset()

        assert avad.state == HysteresisState.SILENCE
        assert avad.is_speech_active is False
        assert avad.ambient_rms == INITIAL_AMBIENT_RMS

    def test_reset_allows_new_session(self) -> None:
        """After reset, can start a new detection session normally."""
        avad = _make_adaptive_vad()
        loud = _speech_chunk(rms_level=5000.0)

        # First session
        for _ in range(DEFAULT_SPEECH_START_FRAMES):
            avad.process_chunk(loud)
        assert avad.is_speech_active is True

        # Reset
        avad.reset()

        # New session requires fresh N speech frames
        avad.process_chunk(loud)
        assert avad.state == HysteresisState.PENDING_SPEECH


# -- Custom Configuration --


class TestCustomConfig:
    """Test AdaptiveVAD with non-default configuration."""

    def test_high_multiplier_reduces_false_triggers(self) -> None:
        """Higher multiplier makes detection less sensitive."""
        config = AdaptiveVADConfig(ambient_multiplier=5.0)
        avad = _make_adaptive_vad(config=config)
        avad._ambient_rms = 200.0

        # Threshold should be 200 * 5.0 = 1000
        assert avad.dynamic_threshold == 1000.0

    def test_more_start_frames_delays_activation(self) -> None:
        """More required start frames means slower activation."""
        config = AdaptiveVADConfig(speech_start_frames=10)
        avad = _make_adaptive_vad(config=config)
        loud = _speech_chunk(rms_level=5000.0)

        # Default 3 frames is not enough
        for _ in range(3):
            avad.process_chunk(loud)
        assert avad.is_speech_active is False

        # Need 10 total
        for _ in range(7):
            avad.process_chunk(loud)
        assert avad.is_speech_active is True

    def test_fewer_silence_frames_enables_faster_cutoff(self) -> None:
        """Fewer silence frames = faster end-of-speech detection."""
        config = AdaptiveVADConfig(silence_end_frames=5)
        avad = _make_adaptive_vad(config=config)
        loud = _speech_chunk(rms_level=5000.0)
        quiet = _zero_chunk()

        # Start speech
        for _ in range(DEFAULT_SPEECH_START_FRAMES):
            avad.process_chunk(loud)

        # Only 5 silence frames needed
        for _ in range(5):
            avad.process_chunk(quiet)

        assert avad.is_speech_active is False


# -- Noisy Environment Scenarios --


class TestNoisyEnvironments:
    """Integration tests for realistic noisy environments."""

    def test_fan_noise_calibration(self) -> None:
        """Simulates fan noise (~200 RMS) then speech (~5000 RMS).

        After calibrating to fan noise, VAD should detect speech
        but not false-trigger on the fan.
        """
        avad = _make_adaptive_vad()
        fan_noise = _silence_chunk(rms_level=200.0)
        speech = _speech_chunk(rms_level=5000.0)

        # Calibrate to fan noise (2s = 25 frames)
        for _ in range(25):
            avad.process_chunk(fan_noise)

        # Fan should NOT trigger speech
        assert avad.is_speech_active is False

        # Now speech should trigger
        for _ in range(DEFAULT_SPEECH_START_FRAMES):
            avad.process_chunk(speech)
        assert avad.is_speech_active is True

    def test_quiet_room_no_false_triggers(self) -> None:
        """In a quiet room (RMS ~20), no false triggers over many frames."""
        avad = _make_adaptive_vad()
        quiet = _silence_chunk(rms_level=20.0)

        # Run for 100 frames (~8s)
        false_triggers = 0
        for _ in range(100):
            if avad.process_chunk(quiet):
                false_triggers += 1

        assert false_triggers == 0, f"Expected 0 false triggers, got {false_triggers}"

    def test_environment_transition(self) -> None:
        """Transitioning from quiet to noisy environment re-calibrates.

        Success criterion: adapts within 2s of environment change.
        """
        avad = _make_adaptive_vad()

        # Quiet room calibration
        quiet = _silence_chunk(rms_level=30.0)
        for _ in range(25):
            avad.process_chunk(quiet)
        quiet_threshold = avad.dynamic_threshold

        # Fan turns on (400 RMS noise)
        noisy = _silence_chunk(rms_level=400.0)
        for _ in range(25):  # 2s worth of frames
            avad.process_chunk(noisy)
        noisy_threshold = avad.dynamic_threshold

        # Threshold should have increased significantly
        assert noisy_threshold > quiet_threshold * 2.0, (
            f"Threshold didn't adapt: quiet={quiet_threshold}, noisy={noisy_threshold}"
        )


# -- State Machine Transitions --


class TestStateTransitions:
    """Test all valid state transitions in the hysteresis machine."""

    def test_silence_to_pending_speech(self) -> None:
        avad = _make_adaptive_vad()
        loud = _speech_chunk(rms_level=5000.0)

        avad.process_chunk(loud)
        assert avad.state == HysteresisState.PENDING_SPEECH

    def test_pending_speech_to_silence(self) -> None:
        avad = _make_adaptive_vad()
        loud = _speech_chunk(rms_level=5000.0)
        quiet = _zero_chunk()

        avad.process_chunk(loud)
        assert avad.state == HysteresisState.PENDING_SPEECH

        avad.process_chunk(quiet)
        assert avad.state == HysteresisState.SILENCE

    def test_pending_speech_to_speech(self) -> None:
        avad = _make_adaptive_vad()
        loud = _speech_chunk(rms_level=5000.0)

        for _ in range(DEFAULT_SPEECH_START_FRAMES):
            avad.process_chunk(loud)
        assert avad.state == HysteresisState.SPEECH

    def test_speech_to_pending_silence(self) -> None:
        avad = _make_adaptive_vad()
        loud = _speech_chunk(rms_level=5000.0)
        quiet = _zero_chunk()

        for _ in range(DEFAULT_SPEECH_START_FRAMES):
            avad.process_chunk(loud)
        avad.process_chunk(quiet)
        assert avad.state == HysteresisState.PENDING_SILENCE

    def test_pending_silence_to_speech(self) -> None:
        avad = _make_adaptive_vad()
        loud = _speech_chunk(rms_level=5000.0)
        quiet = _zero_chunk()

        for _ in range(DEFAULT_SPEECH_START_FRAMES):
            avad.process_chunk(loud)
        avad.process_chunk(quiet)
        assert avad.state == HysteresisState.PENDING_SILENCE

        avad.process_chunk(loud)
        assert avad.state == HysteresisState.SPEECH

    def test_pending_silence_to_silence(self) -> None:
        avad = _make_adaptive_vad()
        loud = _speech_chunk(rms_level=5000.0)
        quiet = _zero_chunk()

        for _ in range(DEFAULT_SPEECH_START_FRAMES):
            avad.process_chunk(loud)

        for _ in range(DEFAULT_SILENCE_END_FRAMES):
            avad.process_chunk(quiet)
        assert avad.state == HysteresisState.SILENCE


# -- HysteresisState Enum --


class TestHysteresisStateEnum:
    """Test HysteresisState enum values."""

    def test_all_states_exist(self) -> None:
        assert hasattr(HysteresisState, "SILENCE")
        assert hasattr(HysteresisState, "PENDING_SPEECH")
        assert hasattr(HysteresisState, "SPEECH")
        assert hasattr(HysteresisState, "PENDING_SILENCE")

    def test_states_are_distinct(self) -> None:
        states = [
            HysteresisState.SILENCE,
            HysteresisState.PENDING_SPEECH,
            HysteresisState.SPEECH,
            HysteresisState.PENDING_SILENCE,
        ]
        assert len(set(states)) == 4
