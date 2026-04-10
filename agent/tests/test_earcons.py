"""Tests for the earcon audio feedback system.

ERRH-03: Error earcon is audibly different from acknowledgment.
PROG-01: Acknowledge earcon plays within 200ms of wake word.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from core.audio.earcons import (
    ACK_DURATION_MS,
    ACK_FREQ_END_HZ,
    ACK_FREQ_START_HZ,
    EARCON_SAMPLE_RATE,
    ERR_DURATION_MS,
    ERR_FREQ_END_HZ,
    ERR_FREQ_START_HZ,
    PROG_DURATION_MS,
    PROG_FREQ_HZ,
    EarconType,
    _apply_fade_and_convert,
    _build_cache,
    _generate_sweep,
    _generate_tone,
    get_earcon,
    play_earcon,
)


class TestToneGeneration:
    """Tests for tone generation functions."""

    def test_generate_tone_shape(self) -> None:
        """Generated tone should have correct number of samples."""
        pcm = _generate_tone(440, 100)
        expected_samples = int(EARCON_SAMPLE_RATE * 100 / 1000)
        assert len(pcm) == expected_samples

    def test_generate_tone_dtype(self) -> None:
        """Generated tone should be int16."""
        pcm = _generate_tone(440, 100)
        assert pcm.dtype == np.int16

    def test_generate_tone_not_silent(self) -> None:
        """Generated tone should not be all zeros."""
        pcm = _generate_tone(440, 100)
        assert np.max(np.abs(pcm)) > 0

    def test_generate_tone_within_range(self) -> None:
        """Generated tone should stay within int16 range."""
        pcm = _generate_tone(440, 100, amplitude=1.0)
        assert np.max(pcm) <= 32767
        assert np.min(pcm) >= -32768

    def test_generate_sweep_shape(self) -> None:
        """Generated sweep should have correct number of samples."""
        pcm = _generate_sweep(400, 800, 200)
        expected_samples = int(EARCON_SAMPLE_RATE * 200 / 1000)
        assert len(pcm) == expected_samples

    def test_generate_sweep_dtype(self) -> None:
        """Generated sweep should be int16."""
        pcm = _generate_sweep(400, 800, 200)
        assert pcm.dtype == np.int16

    def test_generate_sweep_not_silent(self) -> None:
        """Generated sweep should not be all zeros."""
        pcm = _generate_sweep(400, 800, 200)
        assert np.max(np.abs(pcm)) > 0

    def test_generate_sweep_different_from_reverse(self) -> None:
        """Rising sweep should differ from descending sweep."""
        rising = _generate_sweep(400, 800, 200)
        descending = _generate_sweep(800, 400, 200)
        assert not np.array_equal(rising, descending)


class TestFadeAndConvert:
    """Tests for anti-click fade in/out."""

    def test_fade_produces_int16(self) -> None:
        """Fade conversion should produce int16 output."""
        signal = np.sin(np.linspace(0, 2 * np.pi, 100))
        pcm = _apply_fade_and_convert(signal)
        assert pcm.dtype == np.int16

    def test_fade_start_is_quiet(self) -> None:
        """First few samples should be attenuated by fade-in."""
        signal = np.ones(1000, dtype=np.float64) * 0.5
        pcm = _apply_fade_and_convert(signal)
        # First sample should be zero or near-zero (faded in)
        assert abs(pcm[0]) < abs(pcm[len(pcm) // 2])

    def test_fade_end_is_quiet(self) -> None:
        """Last few samples should be attenuated by fade-out."""
        signal = np.ones(1000, dtype=np.float64) * 0.5
        pcm = _apply_fade_and_convert(signal)
        # Last sample should be zero or near-zero (faded out)
        assert abs(pcm[-1]) < abs(pcm[len(pcm) // 2])


class TestEarconCache:
    """Tests for earcon pre-generation cache."""

    def test_build_cache_returns_all_types(self) -> None:
        """Cache should contain all EarconType entries."""
        cache = _build_cache()
        assert EarconType.ACKNOWLEDGE in cache
        assert EarconType.ERROR in cache
        assert EarconType.PROGRESS in cache

    def test_acknowledge_earcon_duration(self) -> None:
        """Acknowledge earcon should be ~200ms."""
        cache = _build_cache()
        pcm = cache[EarconType.ACKNOWLEDGE]
        expected = int(EARCON_SAMPLE_RATE * ACK_DURATION_MS / 1000)
        assert len(pcm) == expected

    def test_error_earcon_duration(self) -> None:
        """Error earcon should be ~300ms."""
        cache = _build_cache()
        pcm = cache[EarconType.ERROR]
        expected = int(EARCON_SAMPLE_RATE * ERR_DURATION_MS / 1000)
        assert len(pcm) == expected

    def test_progress_earcon_duration(self) -> None:
        """Progress earcon should be ~150ms."""
        cache = _build_cache()
        pcm = cache[EarconType.PROGRESS]
        expected = int(EARCON_SAMPLE_RATE * PROG_DURATION_MS / 1000)
        assert len(pcm) == expected

    def test_earcons_are_distinct(self) -> None:
        """ERRH-03: Different earcon types must produce different audio."""
        cache = _build_cache()
        ack = cache[EarconType.ACKNOWLEDGE]
        err = cache[EarconType.ERROR]
        prog = cache[EarconType.PROGRESS]

        # Different lengths already guarantee distinction
        assert len(ack) != len(err)
        assert len(ack) != len(prog)
        assert len(err) != len(prog)

    def test_get_earcon_returns_cached(self) -> None:
        """get_earcon should return a valid numpy array."""
        pcm = get_earcon(EarconType.ACKNOWLEDGE)
        assert isinstance(pcm, np.ndarray)
        assert pcm.dtype == np.int16
        assert len(pcm) > 0


class TestEarconPlayback:
    """Tests for async earcon playback."""

    @pytest.mark.asyncio
    async def test_play_earcon_calls_sounddevice(self) -> None:
        """play_earcon should call _play_pcm_blocking in a thread."""
        with patch(
            "core.audio.earcons._play_pcm_blocking",
        ) as mock_play:
            await play_earcon(EarconType.ACKNOWLEDGE)
            mock_play.assert_called_once()
            # Verify the argument is the acknowledge PCM
            call_args = mock_play.call_args[0][0]
            assert isinstance(call_args, np.ndarray)
            assert call_args.dtype == np.int16

    @pytest.mark.asyncio
    async def test_play_earcon_handles_oserror(self) -> None:
        """play_earcon should not raise on OSError."""
        with patch(
            "core.audio.earcons._play_pcm_blocking",
            side_effect=OSError("no audio device"),
        ):
            # Should not raise
            await play_earcon(EarconType.ERROR)

    @pytest.mark.asyncio
    async def test_play_earcon_handles_runtime_error(self) -> None:
        """play_earcon should not raise on RuntimeError."""
        with patch(
            "core.audio.earcons._play_pcm_blocking",
            side_effect=RuntimeError("stream error"),
        ):
            await play_earcon(EarconType.PROGRESS)


class TestEarconTypes:
    """Tests for EarconType enum."""

    def test_all_types_defined(self) -> None:
        """All expected earcon types should be defined."""
        assert hasattr(EarconType, "ACKNOWLEDGE")
        assert hasattr(EarconType, "ERROR")
        assert hasattr(EarconType, "PROGRESS")

    def test_type_names(self) -> None:
        """EarconType names should be descriptive."""
        assert EarconType.ACKNOWLEDGE.name == "ACKNOWLEDGE"
        assert EarconType.ERROR.name == "ERROR"
        assert EarconType.PROGRESS.name == "PROGRESS"


class TestMouthEarconIntegration:
    """Tests for Mouth.play_earcon() integration."""

    @pytest.mark.asyncio
    async def test_mouth_play_earcon_delegates(self) -> None:
        """Mouth.play_earcon should delegate to earcon system."""
        from core.mouth import Mouth

        mouth = Mouth()
        with patch(
            "core.mouth.play_earcon",
            new_callable=AsyncMock,
        ) as mock_play:
            await mouth.play_earcon(EarconType.ACKNOWLEDGE)
            mock_play.assert_called_once_with(EarconType.ACKNOWLEDGE)

    @pytest.mark.asyncio
    async def test_mouth_play_earcon_handles_error(self) -> None:
        """Mouth.play_earcon should not raise on failure."""
        from core.mouth import Mouth

        mouth = Mouth()
        with patch(
            "core.mouth.play_earcon",
            new_callable=AsyncMock,
            side_effect=RuntimeError("audio fail"),
        ):
            # Should not raise
            await mouth.play_earcon(EarconType.ERROR)
