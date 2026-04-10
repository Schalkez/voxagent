"""AdaptiveVAD: Ambient-aware speech detection with hysteresis.

Wraps the existing VoiceActivityDetector with:
1. Running ambient noise estimator (exponential moving average of RMS during silence)
2. Dynamic energy threshold = ambient_rms * multiplier
3. Hysteresis state machine: require N consecutive speech frames to start,
   M consecutive silence frames to stop

AUDR-02: VAD thresholds adapt to ambient noise level
AUDR-03: VAD hysteresis prevents premature start/stop
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

import numpy as np

from core.audio.vad import VoiceActivityDetector
from core.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(module="adaptive_vad")

# -- Named Constants --

DEFAULT_AMBIENT_MULTIPLIER: float = 3.0
DEFAULT_EMA_ALPHA: float = 0.04  # ~25 frames to converge at 80ms = ~2s
DEFAULT_SPEECH_START_FRAMES: int = 3
DEFAULT_SILENCE_END_FRAMES: int = 15  # 15 * 80ms = 1.2s
INITIAL_AMBIENT_RMS: float = 300.0
MIN_ENERGY_THRESHOLD: float = 100.0
MAX_ENERGY_THRESHOLD: float = 5000.0
AMBIENT_UPDATE_CEILING: float = 3000.0  # don't learn from extremely loud silence


class HysteresisState(Enum):
    """State of the hysteresis speech detector."""

    SILENCE = auto()
    PENDING_SPEECH = auto()
    SPEECH = auto()
    PENDING_SILENCE = auto()


@dataclass(frozen=True)
class AdaptiveVADConfig:
    """Configuration for AdaptiveVAD.

    Attributes:
        ambient_multiplier: Dynamic threshold = ambient_rms * multiplier.
        ema_alpha: Smoothing factor for exponential moving average (0..1).
            Lower = slower adaptation. ~0.04 adapts in ~2s window.
        speech_start_frames: Consecutive speech frames to trigger start.
        silence_end_frames: Consecutive silence frames to trigger stop.
    """

    ambient_multiplier: float = DEFAULT_AMBIENT_MULTIPLIER
    ema_alpha: float = DEFAULT_EMA_ALPHA
    speech_start_frames: int = DEFAULT_SPEECH_START_FRAMES
    silence_end_frames: int = DEFAULT_SILENCE_END_FRAMES


class AdaptiveVAD:
    """Ambient-aware VAD with hysteresis state machine.

    Wraps VoiceActivityDetector and adds:
    - Dynamic energy threshold based on running ambient noise estimate
    - Hysteresis: N consecutive speech frames to start, M silence frames to stop

    The ambient noise estimator uses an exponential moving average (EMA)
    of RMS energy during silence periods. The dynamic threshold is
    ``ambient_rms * multiplier``, clamped to [MIN, MAX] bounds.

    State machine::

        SILENCE --[speech_count >= N]--> SPEECH
        SILENCE --[speech_count < N]--> PENDING_SPEECH --> SILENCE (on silence reset)
        SPEECH  --[silence_count >= M]--> SILENCE
        SPEECH  --[silence_count < M]--> PENDING_SILENCE --> SPEECH (on speech reset)

    Args:
        vad: Underlying VoiceActivityDetector instance.
        config: Adaptive VAD configuration.
    """

    def __init__(
        self,
        vad: VoiceActivityDetector,
        config: AdaptiveVADConfig | None = None,
    ) -> None:
        self._vad = vad
        self._config = config or AdaptiveVADConfig()

        # Ambient noise estimator
        self._ambient_rms: float = INITIAL_AMBIENT_RMS

        # Hysteresis counters
        self._consecutive_speech: int = 0
        self._consecutive_silence: int = 0
        self._state = HysteresisState.SILENCE

    # -- Public Properties --

    @property
    def state(self) -> HysteresisState:
        """Current hysteresis state."""
        return self._state

    @property
    def ambient_rms(self) -> float:
        """Current estimated ambient noise RMS level."""
        return self._ambient_rms

    @property
    def dynamic_threshold(self) -> float:
        """Current dynamic energy threshold based on ambient noise."""
        raw = self._ambient_rms * self._config.ambient_multiplier
        return _clamp(raw, MIN_ENERGY_THRESHOLD, MAX_ENERGY_THRESHOLD)

    @property
    def is_speech_active(self) -> bool:
        """Whether the hysteresis state machine considers speech active."""
        return self._state in (HysteresisState.SPEECH, HysteresisState.PENDING_SILENCE)

    # -- Core Detection --

    def process_chunk(self, audio_chunk: np.ndarray) -> bool:
        """Process an audio chunk through adaptive VAD with hysteresis.

        Updates ambient noise estimate during silence, applies dynamic
        threshold, and runs the hysteresis state machine.

        Args:
            audio_chunk: Audio frame (int16 numpy array).

        Returns:
            True if the hysteresis state machine considers speech active
            (i.e., enough consecutive speech frames have been seen to start,
            and not enough silence frames to stop).
        """
        rms = _compute_rms(audio_chunk)
        is_speech = self._detect_with_adaptive_threshold(audio_chunk, rms)
        self._update_hysteresis(is_speech)
        self._update_ambient_estimate(rms)
        return self.is_speech_active

    def reset(self) -> None:
        """Reset hysteresis state and ambient estimate.

        Call when the pipeline transitions to a new listening session.
        """
        self._consecutive_speech = 0
        self._consecutive_silence = 0
        self._state = HysteresisState.SILENCE
        self._ambient_rms = INITIAL_AMBIENT_RMS
        logger.debug("adaptive VAD reset")

    # -- Internal: Detection --

    def _detect_with_adaptive_threshold(
        self, audio_chunk: np.ndarray, rms: float
    ) -> bool:
        """Run VAD with dynamically adjusted energy threshold.

        If Silero VAD is loaded, uses it directly (it has its own internal
        thresholds). For energy-based fallback, applies the dynamic threshold.

        Args:
            audio_chunk: Audio frame (int16 numpy array).
            rms: Pre-computed RMS energy of the chunk.

        Returns:
            True if the underlying detector considers this chunk speech.
        """
        if self._vad.is_loaded:
            return self._vad.detect_speech(audio_chunk)

        # Energy-based fallback with adaptive threshold
        return rms > self.dynamic_threshold

    # -- Internal: Hysteresis State Machine --

    def _update_hysteresis(self, is_speech: bool) -> None:
        """Update hysteresis counters and transition state.

        Args:
            is_speech: Raw detection result from the underlying VAD.
        """
        if is_speech:
            self._consecutive_speech += 1
            self._consecutive_silence = 0
        else:
            self._consecutive_silence += 1
            self._consecutive_speech = 0

        self._state = self._next_state(is_speech)

    def _next_state(self, is_speech: bool) -> HysteresisState:
        """Compute the next hysteresis state based on current counters.

        Args:
            is_speech: Raw detection result from the underlying VAD.

        Returns:
            The next HysteresisState.
        """
        if self._state in (HysteresisState.SILENCE, HysteresisState.PENDING_SPEECH):
            return self._transition_from_silence(is_speech)
        return self._transition_from_speech(is_speech)

    def _transition_from_silence(self, is_speech: bool) -> HysteresisState:
        """Handle state transitions when currently in SILENCE/PENDING_SPEECH.

        Args:
            is_speech: Raw detection result.

        Returns:
            Next state.
        """
        if not is_speech:
            return HysteresisState.SILENCE

        if self._consecutive_speech >= self._config.speech_start_frames:
            logger.debug(
                "speech started",
                consecutive_frames=self._consecutive_speech,
                ambient_rms=round(self._ambient_rms, 1),
                threshold=round(self.dynamic_threshold, 1),
            )
            return HysteresisState.SPEECH

        return HysteresisState.PENDING_SPEECH

    def _transition_from_speech(self, is_speech: bool) -> HysteresisState:
        """Handle state transitions when currently in SPEECH/PENDING_SILENCE.

        Args:
            is_speech: Raw detection result.

        Returns:
            Next state.
        """
        if is_speech:
            return HysteresisState.SPEECH

        if self._consecutive_silence >= self._config.silence_end_frames:
            logger.debug(
                "speech ended",
                consecutive_silence=self._consecutive_silence,
                ambient_rms=round(self._ambient_rms, 1),
            )
            return HysteresisState.SILENCE

        return HysteresisState.PENDING_SILENCE

    # -- Internal: Ambient Noise Estimation --

    def _update_ambient_estimate(self, rms: float) -> None:
        """Update ambient noise RMS using exponential moving average.

        Updates during SILENCE and PENDING_SPEECH states. The PENDING_SPEECH
        inclusion is critical: when ambient noise suddenly increases (e.g.,
        fan turns on), the detector temporarily sees it as potential speech.
        Since it hasn't been confirmed yet, we keep adapting — allowing the
        threshold to catch up before the noise is wrongly confirmed as speech.

        Freezes during confirmed SPEECH and PENDING_SILENCE to avoid
        contaminating the ambient estimate with actual speech energy.

        Ignores extremely loud samples that might be transient non-speech.

        Args:
            rms: RMS energy of the current chunk.
        """
        if self._state in (HysteresisState.SPEECH, HysteresisState.PENDING_SILENCE):
            return

        if rms > AMBIENT_UPDATE_CEILING:
            return

        alpha = self._config.ema_alpha
        self._ambient_rms = alpha * rms + (1.0 - alpha) * self._ambient_rms


# -- Module-Level Helpers --


def _compute_rms(audio_chunk: np.ndarray) -> float:
    """Compute RMS energy of an int16 audio chunk.

    Args:
        audio_chunk: Audio frame (int16 numpy array).

    Returns:
        RMS energy as a float.
    """
    return float(np.sqrt(np.mean(audio_chunk.astype(np.float32) ** 2)))


def _clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp a value to [minimum, maximum] range.

    Args:
        value: Value to clamp.
        minimum: Lower bound.
        maximum: Upper bound.

    Returns:
        Clamped value.
    """
    return max(minimum, min(value, maximum))
