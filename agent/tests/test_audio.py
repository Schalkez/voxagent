"""Tests for audio subsystem: recorder, VAD, wake word, converter."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from core.audio.converter import AudioConverter
from core.audio.recorder import CHUNK_SAMPLES, SAMPLE_RATE, AudioRecorder
from core.audio.vad import ENERGY_THRESHOLD, SPEECH_THRESHOLD, VoiceActivityDetector
from core.audio.wake_word import WakeWordDetector


class TestAudioRecorderConstants:
    """Test AudioRecorder module constants."""

    def test_sample_rate(self) -> None:
        assert SAMPLE_RATE == 16_000

    def test_chunk_samples(self) -> None:
        assert int(SAMPLE_RATE * 80 / 1000) == CHUNK_SAMPLES


class TestAudioRecorder:
    """Test AudioRecorder class."""

    def test_not_active_initially(self) -> None:
        recorder = AudioRecorder()
        assert recorder.is_active is False

    @pytest.mark.asyncio
    async def test_read_chunk_timeout(self) -> None:
        recorder = AudioRecorder()
        result = await recorder.read_chunk()
        assert result is None

    def test_drain_queue(self) -> None:
        recorder = AudioRecorder()
        recorder._audio_queue.put_nowait(np.zeros(100, dtype=np.int16))
        recorder._drain_queue()
        assert recorder._audio_queue.empty()

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self) -> None:
        recorder = AudioRecorder()
        await recorder.stop()
        assert recorder.is_active is False


class TestVoiceActivityDetector:
    """Test VoiceActivityDetector class."""

    def test_defaults(self) -> None:
        vad = VoiceActivityDetector()
        assert vad._speech_threshold == SPEECH_THRESHOLD
        assert vad._energy_threshold == ENERGY_THRESHOLD

    def test_not_loaded_initially(self) -> None:
        vad = VoiceActivityDetector()
        assert vad.is_loaded is False

    def test_energy_detect_loud(self) -> None:
        vad = VoiceActivityDetector(energy_threshold=100.0)
        loud = np.full(1280, 5000, dtype=np.int16)
        assert vad._energy_detect(loud) is True

    def test_energy_detect_quiet(self) -> None:
        vad = VoiceActivityDetector(energy_threshold=100.0)
        quiet = np.zeros(1280, dtype=np.int16)
        assert vad._energy_detect(quiet) is False

    def test_detect_speech_uses_energy_when_no_model(self) -> None:
        vad = VoiceActivityDetector(energy_threshold=100.0)
        loud = np.full(1280, 5000, dtype=np.int16)
        assert vad.detect_speech(loud) is True

    def test_unload(self) -> None:
        vad = VoiceActivityDetector()
        vad._model = "fake"
        vad.unload()
        assert vad._model is None


class TestWakeWordDetector:
    """Test WakeWordDetector class."""

    def test_init_default_sensitivity(self) -> None:
        det = WakeWordDetector()
        assert det._sensitivity == 0.7

    def test_detect_without_load_raises(self) -> None:
        det = WakeWordDetector()
        with pytest.raises(RuntimeError, match="not loaded"):
            det.detect(np.zeros(1280, dtype=np.int16))

    def test_unload(self) -> None:
        det = WakeWordDetector()
        det._model = MagicMock()
        det.unload()
        assert det._model is None


class TestAudioConverter:
    """Test AudioConverter frames_to_wav."""

    def test_frames_to_wav_returns_bytes(self) -> None:
        frames = [np.zeros(1280, dtype=np.int16)]
        wav = AudioConverter.frames_to_wav(frames)
        assert isinstance(wav, bytes)
        assert len(wav) > 44  # WAV header is 44 bytes

    def test_frames_to_wav_starts_with_riff(self) -> None:
        frames = [np.zeros(100, dtype=np.int16)]
        wav = AudioConverter.frames_to_wav(frames)
        assert wav[:4] == b"RIFF"

    def test_multiple_frames(self) -> None:
        frames = [np.zeros(100, dtype=np.int16) for _ in range(5)]
        wav = AudioConverter.frames_to_wav(frames)
        assert isinstance(wav, bytes)
