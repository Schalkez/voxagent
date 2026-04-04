"""Unit tests for the Ears voice input pipeline."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from core.config import VoxAgentConfig
from core.ears import (
    CHUNK_SAMPLES,
    SAMPLE_RATE,
    Ears,
    EarsState,
    EmptyTranscribeResult,
)
from providers.base import TranscribeResult


# ── Fixtures ──────────────────────────────────────


@pytest.fixture
def mock_stt_provider() -> AsyncMock:
    """Create a mock STT provider that returns a canned transcription."""
    provider = AsyncMock()
    provider.transcribe = AsyncMock(
        return_value=TranscribeResult(
            text="mở Chrome",
            confidence=0.95,
            language="vi",
            duration_ms=2000,
        )
    )
    return provider


@pytest.fixture
def default_config() -> VoxAgentConfig:
    """Create a default VoxAgent config for testing."""
    return VoxAgentConfig()


@pytest.fixture
def ears(mock_stt_provider: AsyncMock, default_config: VoxAgentConfig) -> Ears:
    """Create an Ears instance with mocked dependencies."""
    return Ears(stt_provider=mock_stt_provider, config=default_config)


# ── Constructor & State Tests ─────────────────────


class TestEarsConstruction:
    """Verify DI constructor and initial state."""

    def test_initial_state_is_idle(self, ears: Ears) -> None:
        """Ears should start in IDLE state."""
        assert ears.state == EarsState.IDLE

    def test_di_injects_stt_provider(
        self, ears: Ears, mock_stt_provider: AsyncMock
    ) -> None:
        """STT provider should be injected and stored."""
        assert ears._stt_provider is mock_stt_provider

    def test_di_injects_config(
        self, ears: Ears, default_config: VoxAgentConfig
    ) -> None:
        """Config should be injected and stored."""
        assert ears._config is default_config


# ── Event System Tests ────────────────────────────


class TestEarsEvents:
    """Verify the event callback system."""

    def test_event_callback_fires_on_state_change(self, ears: Ears) -> None:
        """Registered callbacks should be called on _emit."""
        events: list = []
        ears.on_event(lambda event: events.append(event))

        ears._emit(EarsState.LISTENING_FOR_WAKE_WORD, "test")

        assert len(events) == 1
        assert events[0].state == EarsState.LISTENING_FOR_WAKE_WORD
        assert events[0].message == "test"

    def test_multiple_callbacks(self, ears: Ears) -> None:
        """Multiple callbacks should all be invoked."""
        count = {"first": 0, "second": 0}
        ears.on_event(lambda _: count.__setitem__("first", count["first"] + 1))
        ears.on_event(lambda _: count.__setitem__("second", count["second"] + 1))

        ears._emit(EarsState.RECORDING_SPEECH)

        assert count["first"] == 1
        assert count["second"] == 1

    def test_broken_callback_does_not_crash(self, ears: Ears) -> None:
        """A failing callback should not break other callbacks."""
        results: list = []

        def bad_callback(_: object) -> None:
            raise ValueError("boom")

        ears.on_event(bad_callback)
        ears.on_event(lambda event: results.append(event))

        ears._emit(EarsState.TRANSCRIBING)  # Should not raise

        assert len(results) == 1


# ── Audio Conversion Tests ────────────────────────


class TestAudioConversion:
    """Verify WAV conversion logic."""

    def test_frames_to_wav_produces_valid_wav(self) -> None:
        """Concatenated frames should produce valid WAV bytes."""
        frames = [np.zeros((CHUNK_SAMPLES, 1), dtype=np.int16) for _ in range(5)]

        wav_bytes = Ears._frames_to_wav(frames)

        # WAV files start with RIFF header
        assert wav_bytes[:4] == b"RIFF"
        assert wav_bytes[8:12] == b"WAVE"

    def test_frames_to_wav_correct_length(self) -> None:
        """WAV data length should match input frames."""
        frame_count = 10
        frames = [np.ones((CHUNK_SAMPLES, 1), dtype=np.int16) for _ in range(frame_count)]

        wav_bytes = Ears._frames_to_wav(frames)

        # WAV header is 44 bytes, data = frame_count * chunk_samples * 2 bytes
        expected_data = frame_count * CHUNK_SAMPLES * 2
        assert len(wav_bytes) == 44 + expected_data


# ── Energy VAD Tests ──────────────────────────────


class TestEnergyVAD:
    """Verify the fallback energy-based VAD."""

    def test_silence_returns_false(self) -> None:
        """Zero-energy audio should not be detected as speech."""
        silence = np.zeros((CHUNK_SAMPLES,), dtype=np.int16)
        assert Ears._energy_vad(silence) is False

    def test_loud_audio_returns_true(self) -> None:
        """High-energy audio should be detected as speech."""
        loud = np.full((CHUNK_SAMPLES,), 5000, dtype=np.int16)
        assert Ears._energy_vad(loud) is True

    def test_threshold_boundary(self) -> None:
        """Audio at exactly the threshold should behave consistently."""
        # RMS of constant value X is X itself
        threshold = 500.0
        exactly_at = np.full((CHUNK_SAMPLES,), int(threshold), dtype=np.int16)
        # RMS = 500.0, threshold is 500.0, so > threshold is False
        assert Ears._energy_vad(exactly_at) is False

        above = np.full((CHUNK_SAMPLES,), int(threshold) + 1, dtype=np.int16)
        assert Ears._energy_vad(above) is True


# ── EmptyTranscribeResult Tests ───────────────────


class TestEmptyTranscribeResult:
    """Verify the empty result dataclass."""

    def test_default_values(self) -> None:
        """Default values should represent empty audio."""
        result = EmptyTranscribeResult()
        assert result.text == ""
        assert result.confidence == 0.0
        assert result.duration_ms == 0

    def test_is_frozen(self) -> None:
        """EmptyTranscribeResult should be immutable."""
        result = EmptyTranscribeResult()
        with pytest.raises(AttributeError):
            result.text = "modified"  # type: ignore[misc]


# ── Push-to-Talk Tests ────────────────────────────


class TestPushToTalk:
    """Verify the push-to-talk fallback mode."""

    @pytest.mark.asyncio
    async def test_push_to_talk_not_started_raises(self, ears: Ears) -> None:
        """PTT should raise if ears are not started."""
        with pytest.raises(RuntimeError, match="Ears not started"):
            await ears.push_to_talk()

    @pytest.mark.asyncio
    async def test_push_to_talk_records_and_transcribes(
        self, ears: Ears, mock_stt_provider: AsyncMock
    ) -> None:
        """PTT should record audio chunks and call STT provider."""
        # Simulate started state with a fake stream
        ears._stream = MagicMock()

        # Pre-fill audio queue with fake chunks
        for _ in range(5):
            chunk = np.random.randint(-1000, 1000, size=(CHUNK_SAMPLES, 1), dtype=np.int16)
            ears._audio_queue.put_nowait(chunk)

        result = await ears.push_to_talk(duration_s=0.4)

        assert result.text == "mở Chrome"
        mock_stt_provider.transcribe.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_push_to_talk_empty_audio(
        self, ears: Ears, mock_stt_provider: AsyncMock
    ) -> None:
        """PTT with no audio should return EmptyTranscribeResult."""
        ears._stream = MagicMock()
        # Queue is empty — should timeout

        result = await ears.push_to_talk(duration_s=0.1)

        assert isinstance(result, EmptyTranscribeResult)
        assert result.text == ""
        assert result.confidence == 0.0
        mock_stt_provider.transcribe.assert_not_awaited()


# ── Wait For Command Tests ────────────────────────


class TestWaitForCommand:
    """Verify the full pipeline: wake word → record → transcribe."""

    @pytest.mark.asyncio
    async def test_not_started_raises(self, ears: Ears) -> None:
        """wait_for_command should raise if ears are not started."""
        with pytest.raises(RuntimeError, match="Ears not started"):
            await ears.wait_for_command()


# ── Should Stop Recording Tests ───────────────────


class TestShouldStopRecording:
    """Verify the silence detection logic."""

    def test_stops_when_enough_silence(self) -> None:
        """Should stop when silence exceeds threshold and has enough frames."""
        assert Ears._should_stop_recording(
            silence_chunks=20, max_silence_chunks=18, total_frames=50
        ) is True

    def test_does_not_stop_too_few_silence(self) -> None:
        """Should not stop when silence is below threshold."""
        assert Ears._should_stop_recording(
            silence_chunks=5, max_silence_chunks=18, total_frames=50
        ) is False

    def test_does_not_stop_too_few_frames(self) -> None:
        """Should not stop when total frames are below max silence."""
        assert Ears._should_stop_recording(
            silence_chunks=20, max_silence_chunks=18, total_frames=10
        ) is False
