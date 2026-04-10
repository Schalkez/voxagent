"""Tests for AudioNormalizer — validates and converts audio to int16/16kHz/mono.

Covers:
- Passthrough when already canonical (int16/16kHz/mono)
- Float32/float64 to int16 conversion with proper scaling
- Integer dtype conversion (int32 -> int16)
- Stereo to mono downmix
- Sample rate conversion (up/down)
- Empty chunk raises AudioError
- Unsupported dtype raises AudioError
- Clipping on float overflow
"""

from __future__ import annotations

import numpy as np
import pytest

from core.audio.normalizer import (
    MAX_INT16,
    MIN_INT16,
    TARGET_CHANNELS,
    TARGET_SAMPLE_RATE,
    AudioNormalizer,
)
from core.errors import AudioError


# ── Named Constants ───────────────────────────────

SAMPLES: int = 160  # 10ms at 16kHz


# ── Helpers ───────────────────────────────────────


def _make_int16(value: int = 1000, samples: int = SAMPLES) -> np.ndarray:
    """Create a mono int16 chunk filled with a single value."""
    return np.full(samples, value, dtype=np.int16)


def _make_float32(value: float = 0.5, samples: int = SAMPLES) -> np.ndarray:
    """Create a mono float32 chunk (range -1.0 to 1.0)."""
    return np.full(samples, value, dtype=np.float32)


def _make_stereo_int16(left: int = 100, right: int = 200, samples: int = SAMPLES) -> np.ndarray:
    """Create a stereo int16 chunk with interleaved L/R samples."""
    stereo = np.empty(samples * 2, dtype=np.int16)
    stereo[0::2] = left
    stereo[1::2] = right
    return stereo


# ── Tests: Passthrough ───────────────────────────


class TestPassthrough:
    """When input already matches canonical format, output should be equivalent."""

    def test_int16_mono_16k_passthrough(self) -> None:
        normalizer = AudioNormalizer()
        chunk = _make_int16(500)

        result = normalizer.normalize(chunk, source_rate=TARGET_SAMPLE_RATE, source_channels=1)

        assert result.dtype == np.int16
        assert len(result) == SAMPLES
        np.testing.assert_array_equal(result, chunk.ravel())


# ── Tests: Dtype Conversion ──────────────────────


class TestDtypeConversion:
    """Verify conversion from various numeric dtypes to int16."""

    def test_float32_to_int16(self) -> None:
        normalizer = AudioNormalizer()
        chunk = _make_float32(0.5)

        result = normalizer.normalize(chunk, source_rate=TARGET_SAMPLE_RATE, source_channels=1)

        assert result.dtype == np.int16
        # 0.5 * MAX_INT16 = 16383
        expected = int(0.5 * MAX_INT16)
        assert abs(int(result[0]) - expected) <= 1

    def test_float64_to_int16(self) -> None:
        normalizer = AudioNormalizer()
        chunk = np.full(SAMPLES, 0.25, dtype=np.float64)

        result = normalizer.normalize(chunk, source_rate=TARGET_SAMPLE_RATE, source_channels=1)

        assert result.dtype == np.int16
        expected = int(0.25 * MAX_INT16)
        assert abs(int(result[0]) - expected) <= 1

    def test_int32_to_int16(self) -> None:
        normalizer = AudioNormalizer()
        chunk = np.full(SAMPLES, 1000, dtype=np.int32)

        result = normalizer.normalize(chunk, source_rate=TARGET_SAMPLE_RATE, source_channels=1)

        assert result.dtype == np.int16
        assert result[0] == 1000

    def test_float_clipping_positive(self) -> None:
        """Values > 1.0 should be clipped to MAX_INT16."""
        normalizer = AudioNormalizer()
        chunk = np.full(SAMPLES, 2.0, dtype=np.float32)

        result = normalizer.normalize(chunk, source_rate=TARGET_SAMPLE_RATE, source_channels=1)

        assert result.dtype == np.int16
        assert result[0] == MAX_INT16

    def test_float_clipping_negative(self) -> None:
        """Values < -1.0 should be clipped to MIN_INT16."""
        normalizer = AudioNormalizer()
        chunk = np.full(SAMPLES, -2.0, dtype=np.float32)

        result = normalizer.normalize(chunk, source_rate=TARGET_SAMPLE_RATE, source_channels=1)

        assert result.dtype == np.int16
        assert result[0] == MIN_INT16

    def test_unsupported_dtype_raises(self) -> None:
        normalizer = AudioNormalizer()
        chunk = np.full(SAMPLES, True, dtype=np.bool_)

        with pytest.raises(AudioError, match="Unsupported audio dtype"):
            normalizer.normalize(chunk, source_rate=TARGET_SAMPLE_RATE, source_channels=1)


# ── Tests: Channel Conversion ────────────────────


class TestChannelConversion:
    """Verify stereo-to-mono downmix."""

    def test_stereo_to_mono(self) -> None:
        normalizer = AudioNormalizer()
        stereo = _make_stereo_int16(left=100, right=200)

        result = normalizer.normalize(
            stereo,
            source_rate=TARGET_SAMPLE_RATE,
            source_channels=2,
        )

        assert result.dtype == np.int16
        assert len(result) == SAMPLES
        # Average of 100 and 200 = 150
        assert result[0] == 150

    def test_mono_stays_mono(self) -> None:
        normalizer = AudioNormalizer()
        mono = _make_int16(500)

        result = normalizer.normalize(
            mono,
            source_rate=TARGET_SAMPLE_RATE,
            source_channels=1,
        )

        assert len(result) == SAMPLES
        assert result[0] == 500


# ── Tests: Sample Rate Conversion ────────────────


class TestSampleRateConversion:
    """Verify resampling to target rate."""

    def test_downsample_48k_to_16k(self) -> None:
        normalizer = AudioNormalizer()
        # 480 samples at 48kHz = 10ms -> should become 160 at 16kHz
        source_samples = 480
        chunk = np.full(source_samples, 1000, dtype=np.int16)

        result = normalizer.normalize(
            chunk,
            source_rate=48_000,
            source_channels=1,
        )

        expected_length = int(source_samples * (TARGET_SAMPLE_RATE / 48_000))
        assert len(result) == expected_length
        assert result.dtype == np.int16

    def test_upsample_8k_to_16k(self) -> None:
        normalizer = AudioNormalizer()
        # 80 samples at 8kHz = 10ms -> should become 160 at 16kHz
        source_samples = 80
        chunk = np.full(source_samples, 500, dtype=np.int16)

        result = normalizer.normalize(
            chunk,
            source_rate=8_000,
            source_channels=1,
        )

        expected_length = int(source_samples * (TARGET_SAMPLE_RATE / 8_000))
        assert len(result) == expected_length
        assert result.dtype == np.int16

    def test_same_rate_no_resample(self) -> None:
        normalizer = AudioNormalizer()
        chunk = _make_int16(777)

        result = normalizer.normalize(
            chunk,
            source_rate=TARGET_SAMPLE_RATE,
            source_channels=1,
        )

        assert len(result) == SAMPLES
        np.testing.assert_array_equal(result, chunk.ravel())

    def test_resample_preserves_approximate_values(self) -> None:
        """Constant-value signal should remain approximately constant after resampling."""
        normalizer = AudioNormalizer()
        chunk = np.full(480, 3000, dtype=np.int16)

        result = normalizer.normalize(chunk, source_rate=48_000, source_channels=1)

        # All values should be close to 3000
        assert np.all(np.abs(result.astype(np.int32) - 3000) <= 1)


# ── Tests: Error Cases ───────────────────────────


class TestErrors:
    """Verify proper error handling for invalid input."""

    def test_empty_chunk_raises(self) -> None:
        normalizer = AudioNormalizer()
        chunk = np.array([], dtype=np.int16)

        with pytest.raises(AudioError, match="Empty audio chunk"):
            normalizer.normalize(chunk, source_rate=TARGET_SAMPLE_RATE, source_channels=1)


# ── Tests: Combined Transformations ──────────────


class TestCombined:
    """Verify multiple transformations applied together."""

    def test_float32_stereo_48k_to_int16_mono_16k(self) -> None:
        """Full conversion pipeline: float32/stereo/48kHz -> int16/mono/16kHz."""
        normalizer = AudioNormalizer()
        # 480 stereo samples at 48kHz (interleaved float32)
        stereo_48k = np.full(480 * 2, 0.5, dtype=np.float32)

        result = normalizer.normalize(
            stereo_48k,
            source_rate=48_000,
            source_channels=2,
        )

        assert result.dtype == np.int16
        # 480 samples at 48kHz -> 160 at 16kHz
        expected_length = int(480 * (TARGET_SAMPLE_RATE / 48_000))
        assert len(result) == expected_length

    def test_custom_target_rate(self) -> None:
        """Normalizer with non-default target rate."""
        normalizer = AudioNormalizer(target_sample_rate=8_000)
        chunk = np.full(160, 1000, dtype=np.int16)

        result = normalizer.normalize(chunk, source_rate=16_000, source_channels=1)

        expected_length = int(160 * (8_000 / 16_000))
        assert len(result) == expected_length
        assert result.dtype == np.int16


# ── Tests: Normalizer Properties ─────────────────


class TestNormalizerProperties:
    """Verify normalizer instance configuration."""

    def test_default_config(self) -> None:
        normalizer = AudioNormalizer()
        assert normalizer._target_rate == TARGET_SAMPLE_RATE
        assert normalizer._target_channels == TARGET_CHANNELS

    def test_custom_config(self) -> None:
        normalizer = AudioNormalizer(target_sample_rate=8_000, target_channels=2)
        assert normalizer._target_rate == 8_000
        assert normalizer._target_channels == 2
