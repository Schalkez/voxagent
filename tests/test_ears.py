"""Unit tests for the Ears voice input pipeline.

Tests are organized per-component following SRP:
- TestAudioConverter: WAV conversion
- TestVoiceActivityDetector: Speech detection
- TestWakeWordDetector: Wake word detection
- TestEarsEvents: Event callback system
- TestEarsOrchestration: Pipeline orchestration
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from core.audio.converter import AudioConverter
from core.audio.recorder import CHUNK_SAMPLES
from core.audio.vad import VoiceActivityDetector
from core.config import VoxAgentConfig
from core.ears import Ears, EarsState, EmptyTranscribeResult
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


# ── AudioConverter Tests ──────────────────────────


class TestAudioConverter:
    """Verify WAV conversion (single responsibility: format conversion)."""

    def test_produces_valid_wav_header(self) -> None:
        """Output should start with RIFF/WAVE header."""
        frames = [np.zeros((CHUNK_SAMPLES, 1), dtype=np.int16) for _ in range(5)]
        wav_bytes = AudioConverter.frames_to_wav(frames)

        assert wav_bytes[:4] == b"RIFF"
        assert wav_bytes[8:12] == b"WAVE"

    def test_correct_data_length(self) -> None:
        """WAV data length should match input frames."""
        frame_count = 10
        frames = [np.ones((CHUNK_SAMPLES, 1), dtype=np.int16) for _ in range(frame_count)]
        wav_bytes = AudioConverter.frames_to_wav(frames)

        # WAV header = 44 bytes, data = frame_count * chunk_samples * 2 bytes
        expected_data = frame_count * CHUNK_SAMPLES * 2
        assert len(wav_bytes) == 44 + expected_data


# ── VoiceActivityDetector Tests ───────────────────


class TestVoiceActivityDetector:
    """Verify speech detection (single responsibility: speech vs silence)."""

    def test_silence_not_detected_as_speech(self) -> None:
        """Zero-energy audio should not be detected as speech."""
        vad = VoiceActivityDetector()
        silence = np.zeros((CHUNK_SAMPLES,), dtype=np.int16)
        assert vad.detect_speech(silence) is False

    def test_loud_audio_detected_as_speech(self) -> None:
        """High-energy audio should be detected as speech."""
        vad = VoiceActivityDetector()
        loud = np.full((CHUNK_SAMPLES,), 5000, dtype=np.int16)
        assert vad.detect_speech(loud) is True

    def test_energy_threshold_boundary(self) -> None:
        """Audio at exactly threshold should not be detected."""
        vad = VoiceActivityDetector(energy_threshold=500.0)
        at_threshold = np.full((CHUNK_SAMPLES,), 500, dtype=np.int16)
        assert vad.detect_speech(at_threshold) is False

        above = np.full((CHUNK_SAMPLES,), 501, dtype=np.int16)
        assert vad.detect_speech(above) is True

    def test_not_loaded_uses_energy_fallback(self) -> None:
        """Without Silero loaded, should use energy fallback."""
        vad = VoiceActivityDetector()
        assert not vad.is_loaded
        loud = np.full((CHUNK_SAMPLES,), 5000, dtype=np.int16)
        assert vad.detect_speech(loud) is True


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


# ── Ears Event System Tests ──────────────────────


class TestEarsEvents:
    """Verify the event callback system."""

    def test_callback_fires_on_emit(self, ears: Ears) -> None:
        """Registered callbacks should receive events."""
        events: list = []
        ears.on_event(lambda event: events.append(event))

        ears._emit(EarsState.LISTENING_FOR_WAKE_WORD, "test")

        assert len(events) == 1
        assert events[0].state == EarsState.LISTENING_FOR_WAKE_WORD

    def test_multiple_callbacks(self, ears: Ears) -> None:
        """Multiple callbacks should all fire."""
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


# ── Ears Orchestration Tests ─────────────────────


class TestEarsOrchestration:
    """Verify pipeline orchestration logic."""

    def test_initial_state_is_idle(self, ears: Ears) -> None:
        """Ears should start in IDLE state."""
        assert ears.state == EarsState.IDLE

    @pytest.mark.asyncio
    async def test_wait_for_command_not_started_raises(self, ears: Ears) -> None:
        """wait_for_command should raise if not started."""
        with pytest.raises(RuntimeError, match="Ears not started"):
            await ears.wait_for_command()

    @pytest.mark.asyncio
    async def test_push_to_talk_not_started_raises(self, ears: Ears) -> None:
        """push_to_talk should raise if not started."""
        with pytest.raises(RuntimeError, match="Ears not started"):
            await ears.push_to_talk()

    @pytest.mark.asyncio
    async def test_push_to_talk_empty_returns_empty_result(
        self, ears: Ears, mock_stt_provider: AsyncMock
    ) -> None:
        """PTT with no audio should return EmptyTranscribeResult."""
        # Mock recorder as active but empty
        ears._recorder._stream = MagicMock()

        result = await ears.push_to_talk(duration_s=0.1)

        assert isinstance(result, EmptyTranscribeResult)
        assert result.text == ""
        mock_stt_provider.transcribe.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_push_to_talk_transcribes_audio(
        self, ears: Ears, mock_stt_provider: AsyncMock
    ) -> None:
        """PTT should record and transcribe when audio is available."""
        ears._recorder._stream = MagicMock()

        # Pre-fill recorder queue
        for _ in range(5):
            chunk = np.random.randint(-1000, 1000, size=(CHUNK_SAMPLES, 1), dtype=np.int16)
            ears._recorder._audio_queue.put_nowait(chunk)

        result = await ears.push_to_talk(duration_s=0.4)

        assert result.text == "mở Chrome"
        mock_stt_provider.transcribe.assert_awaited_once()
