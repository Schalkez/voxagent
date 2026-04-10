"""Earcon system: Programmatic audio feedback tones.

Generates short notification sounds (earcons) using numpy sine waves.
Earcons are pre-generated at module load and cached as int16 numpy arrays
so playback is allocation-free at runtime.

ERRH-03: Error earcon is audibly distinct from acknowledgment (different frequency/pattern).
PROG-01: Acknowledge earcon plays within 200ms of wake word detection.
"""

from __future__ import annotations

import asyncio
from enum import Enum, auto

import numpy as np

from core.logging import get_logger

logger = get_logger(module="earcons")

# -- Constants --

EARCON_SAMPLE_RATE = 16_000
EARCON_AMPLITUDE = 0.6
FADE_MS = 5  # Anti-click fade in/out

# Acknowledge: rising two-tone beep (~200ms, 800Hz -> 1200Hz)
ACK_FREQ_START_HZ = 800
ACK_FREQ_END_HZ = 1200
ACK_DURATION_MS = 200

# Error: descending harsh tone (~300ms, 600Hz -> 300Hz)
ERR_FREQ_START_HZ = 600
ERR_FREQ_END_HZ = 300
ERR_DURATION_MS = 300

# Progress: soft single tone (~150ms, 1000Hz)
PROG_FREQ_HZ = 1000
PROG_DURATION_MS = 150


class EarconType(Enum):
    """Types of audio feedback tones.

    Attributes:
        ACKNOWLEDGE: Short rising beep for wake word detection.
        ERROR: Descending harsh tone before spoken error messages.
        PROGRESS: Soft single tone for long-running task updates.
    """

    ACKNOWLEDGE = auto()
    ERROR = auto()
    PROGRESS = auto()


# -- Tone Generation --


def _generate_sweep(
    freq_start: float,
    freq_end: float,
    duration_ms: int,
    sample_rate: int = EARCON_SAMPLE_RATE,
    amplitude: float = EARCON_AMPLITUDE,
) -> np.ndarray:
    """Generate a frequency sweep (chirp) tone as int16 PCM.

    Args:
        freq_start: Starting frequency in Hz.
        freq_end: Ending frequency in Hz.
        duration_ms: Duration in milliseconds.
        sample_rate: Sample rate in Hz.
        amplitude: Peak amplitude (0.0 to 1.0).

    Returns:
        PCM audio as int16 numpy array.
    """
    num_samples = int(sample_rate * duration_ms / 1000)
    t = np.linspace(0, duration_ms / 1000, num_samples, endpoint=False, dtype=np.float64)

    # Linear frequency sweep
    freq = np.linspace(freq_start, freq_end, num_samples, dtype=np.float64)
    phase = 2 * np.pi * np.cumsum(freq) / sample_rate
    signal = amplitude * np.sin(phase)

    return _apply_fade_and_convert(signal, sample_rate)


def _generate_tone(
    freq: float,
    duration_ms: int,
    sample_rate: int = EARCON_SAMPLE_RATE,
    amplitude: float = EARCON_AMPLITUDE,
) -> np.ndarray:
    """Generate a pure sine tone as int16 PCM.

    Args:
        freq: Frequency in Hz.
        duration_ms: Duration in milliseconds.
        sample_rate: Sample rate in Hz.
        amplitude: Peak amplitude (0.0 to 1.0).

    Returns:
        PCM audio as int16 numpy array.
    """
    num_samples = int(sample_rate * duration_ms / 1000)
    t = np.linspace(0, duration_ms / 1000, num_samples, endpoint=False, dtype=np.float64)
    signal = amplitude * np.sin(2 * np.pi * freq * t)

    return _apply_fade_and_convert(signal, sample_rate)


def _apply_fade_and_convert(
    signal: np.ndarray,
    sample_rate: int = EARCON_SAMPLE_RATE,
) -> np.ndarray:
    """Apply anti-click fade in/out and convert to int16.

    Args:
        signal: Float64 audio signal (-1.0 to 1.0).
        sample_rate: Sample rate for fade calculation.

    Returns:
        PCM audio as int16 numpy array.
    """
    fade_samples = int(sample_rate * FADE_MS / 1000)
    fade_samples = min(fade_samples, len(signal) // 2)

    if fade_samples > 0:
        fade_in = np.linspace(0, 1, fade_samples, dtype=np.float64)
        fade_out = np.linspace(1, 0, fade_samples, dtype=np.float64)
        signal[:fade_samples] *= fade_in
        signal[-fade_samples:] *= fade_out

    return (signal * 32767).astype(np.int16)


# -- Pre-generated Earcon Cache --

_EARCON_CACHE: dict[EarconType, np.ndarray] = {}


def _build_cache() -> dict[EarconType, np.ndarray]:
    """Generate all earcon tones and cache them.

    Returns:
        Dict mapping EarconType to pre-generated int16 arrays.
    """
    return {
        EarconType.ACKNOWLEDGE: _generate_sweep(
            ACK_FREQ_START_HZ, ACK_FREQ_END_HZ, ACK_DURATION_MS,
        ),
        EarconType.ERROR: _generate_sweep(
            ERR_FREQ_START_HZ, ERR_FREQ_END_HZ, ERR_DURATION_MS,
        ),
        EarconType.PROGRESS: _generate_tone(
            PROG_FREQ_HZ, PROG_DURATION_MS,
        ),
    }


def get_earcon(earcon_type: EarconType) -> np.ndarray:
    """Get a pre-generated earcon tone by type.

    Lazily builds the cache on first access to avoid import-time
    numpy computation if earcons are never used.

    Args:
        earcon_type: Which earcon to retrieve.

    Returns:
        Pre-generated int16 numpy array ready for playback.
    """
    if not _EARCON_CACHE:
        _EARCON_CACHE.update(_build_cache())
    return _EARCON_CACHE[earcon_type]


# -- Playback --


async def play_earcon(earcon_type: EarconType) -> None:
    """Play an earcon through the default audio device.

    Non-blocking: runs sounddevice playback in a thread so the
    pipeline is not stalled. Plays through the system output
    without interfering with StreamingPlayer.

    Args:
        earcon_type: Which earcon to play.
    """
    pcm = get_earcon(earcon_type)
    logger.debug("playing earcon", type=earcon_type.name, samples=len(pcm))

    try:
        await asyncio.to_thread(_play_pcm_blocking, pcm)
    except (OSError, RuntimeError):
        logger.warning("earcon playback failed", type=earcon_type.name)


def _play_pcm_blocking(pcm: np.ndarray) -> None:
    """Play int16 PCM audio synchronously via sounddevice.

    Args:
        pcm: Int16 mono audio samples at EARCON_SAMPLE_RATE.
    """
    try:
        import sounddevice as sd  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("sounddevice not installed -- cannot play earcon")
        return

    sd.play(pcm, samplerate=EARCON_SAMPLE_RATE)
    sd.wait()
