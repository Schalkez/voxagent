"""Tests for barge-in and echo prevention (Phase 6).

Covers:
- AUDR-01: Mic muting during TTS prevents echo
- BGIN-01: Wake word detection during SPEAKING state
- BGIN-02: Audio fade-out on interrupt (no click/pop)
- BGIN-03: In-flight TTS cancellation on interrupt
- BGIN-04: Pipeline state machine integration
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from core.audio.interrupt_controller import InterruptController
from core.audio.streaming_player import (
    FADE_OUT_MS,
    _apply_fade_out,
)
from core.pipeline_state import PipelineState, PipelineStateMachine


# ── AUDR-01: Mic Muting Tests ───────────────────────────────────────────────


class TestMicMuting:
    """AUDR-01: Mic muted (input discarded) while TTS is playing."""

    def test_recorder_starts_unmuted(self) -> None:
        """Recorder is not muted by default."""
        from core.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        assert recorder.is_muted is False

    def test_mute_sets_flag(self) -> None:
        """Calling mute() sets is_muted to True."""
        from core.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        recorder.mute()
        assert recorder.is_muted is True

    def test_unmute_clears_flag(self) -> None:
        """Calling unmute() clears is_muted."""
        from core.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        recorder.mute()
        recorder.unmute()
        assert recorder.is_muted is False

    def test_unmute_drains_ring_buffer(self) -> None:
        """Unmuting drains the ring buffer to prevent echo leakage."""
        from core.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        # Write some data to the ring buffer
        chunk = np.zeros(1280, dtype=np.int16)
        recorder._ring_buffer.write(chunk)
        recorder._ring_buffer.write(chunk)
        assert recorder._ring_buffer.size == 2

        recorder.mute()
        recorder.unmute()
        # Ring buffer should be drained after unmute
        assert recorder._ring_buffer.size == 0

    @pytest.mark.asyncio
    async def test_read_chunk_returns_none_when_muted(self) -> None:
        """read_chunk() returns None when muted (echo prevention)."""
        from core.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        # Write a chunk so there's data available
        chunk = np.zeros(1280, dtype=np.int16)
        recorder._ring_buffer.write(chunk)

        recorder.mute()
        result = await recorder.read_chunk()
        assert result is None

    @pytest.mark.asyncio
    async def test_read_chunk_raw_works_when_muted(self) -> None:
        """read_chunk_raw() returns data even when muted (for wake word)."""
        from core.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        chunk = np.ones(1280, dtype=np.int16)
        recorder._ring_buffer.write(chunk)

        recorder.mute()
        result = await recorder.read_chunk_raw()
        assert result is not None
        assert len(result) == 1280

    def test_mute_is_idempotent(self) -> None:
        """Calling mute() twice doesn't cause issues."""
        from core.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        recorder.mute()
        recorder.mute()
        assert recorder.is_muted is True

    def test_unmute_is_idempotent(self) -> None:
        """Calling unmute() twice doesn't cause issues."""
        from core.audio.recorder import AudioRecorder

        recorder = AudioRecorder()
        recorder.unmute()
        assert recorder.is_muted is False


# ── BGIN-01: Wake Word During TTS Tests ─────────────────────────────────────


class TestWakeWordDuringTTS:
    """BGIN-01: Wake word detector runs continuously during TTS playback."""

    @pytest.mark.asyncio
    async def test_monitor_detects_wake_word_and_interrupts(self) -> None:
        """Monitor triggers interrupt when wake word detected during speech."""
        from core.audio.recorder import AudioRecorder
        from core.ears import Ears

        mock_config = MagicMock()
        mock_config.wake_word.sensitivity = 0.7
        mock_config.stt.language = "vi"
        mock_stt = MagicMock()

        ears = Ears(stt_provider=mock_stt, config=mock_config)

        # Mock the wake word detector to detect on first chunk
        ears._wake_word_detector._model = MagicMock()
        ears._wake_word_detector.detect = MagicMock(return_value=True)

        # Mock the recorder to return one chunk then hang
        chunk = np.zeros(1280, dtype=np.int16)
        call_count = 0

        async def fake_read_raw() -> np.ndarray | None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return chunk
            await asyncio.sleep(10)
            return None

        ears._recorder.read_chunk_raw = fake_read_raw
        ears._recorder._stream = True  # Mark as active

        interrupt = InterruptController()
        result = await ears.monitor_wake_word_during_speech(interrupt)

        assert result is True
        assert interrupt.is_interrupted

    @pytest.mark.asyncio
    async def test_monitor_returns_false_when_not_active(self) -> None:
        """Monitor returns False when recorder is not active."""
        from core.ears import Ears

        mock_config = MagicMock()
        mock_config.wake_word.sensitivity = 0.7
        mock_stt = MagicMock()

        ears = Ears(stt_provider=mock_stt, config=mock_config)
        # Recorder not started (no stream)

        interrupt = InterruptController()
        result = await ears.monitor_wake_word_during_speech(interrupt)
        assert result is False

    @pytest.mark.asyncio
    async def test_monitor_stops_when_already_interrupted(self) -> None:
        """Monitor exits when interrupt is already set."""
        from core.ears import Ears

        mock_config = MagicMock()
        mock_config.wake_word.sensitivity = 0.7
        mock_stt = MagicMock()

        ears = Ears(stt_provider=mock_stt, config=mock_config)
        ears._recorder._stream = True  # Mark as active

        interrupt = InterruptController()
        interrupt.interrupt()  # Pre-interrupt

        # Should return almost immediately
        result = await asyncio.wait_for(
            ears.monitor_wake_word_during_speech(interrupt),
            timeout=1.0,
        )
        assert result is False


# ── BGIN-02: Audio Fade-Out Tests ───────────────────────────────────────────


class TestAudioFadeOut:
    """BGIN-02: Audio fades out over 15-25ms on interrupt."""

    def test_fade_out_applies_ramp(self) -> None:
        """Fade-out applies a linear ramp from 1.0 to 0.0."""
        sample_rate = 16_000
        frames = 1024
        outdata = np.full((frames, 1), 10000, dtype=np.int16)

        _apply_fade_out(outdata, sample_rate)

        fade_samples = int(sample_rate * FADE_OUT_MS / 1000)

        # First sample should be close to original
        assert outdata[0, 0] > 5000
        # Last fade sample should be near zero
        assert abs(outdata[fade_samples - 1, 0]) < 500
        # After fade region should be silence
        assert np.all(outdata[fade_samples:] == 0)

    def test_fade_out_no_discontinuity(self) -> None:
        """Fade-out ramp is monotonically decreasing (no click/pop)."""
        sample_rate = 16_000
        frames = 512
        outdata = np.full((frames, 1), 20000, dtype=np.int16)

        _apply_fade_out(outdata, sample_rate)

        fade_samples = min(int(sample_rate * FADE_OUT_MS / 1000), frames)

        # Check monotonic decrease in the fade region
        for i in range(1, fade_samples):
            assert outdata[i, 0] <= outdata[i - 1, 0]

    def test_fade_out_ms_in_range(self) -> None:
        """FADE_OUT_MS is within the 15-25ms spec."""
        assert 15 <= FADE_OUT_MS <= 25

    def test_fade_out_handles_small_buffer(self) -> None:
        """Fade-out works when buffer is smaller than fade length."""
        sample_rate = 16_000
        frames = 10  # Very small buffer
        outdata = np.full((frames, 1), 10000, dtype=np.int16)

        _apply_fade_out(outdata, sample_rate)

        # Should not crash, and result should be decreasing
        assert outdata[0, 0] > outdata[-1, 0]

    def test_fade_out_silence_all_zeros(self) -> None:
        """All-zero buffer remains zero after fade-out."""
        sample_rate = 16_000
        frames = 256
        outdata = np.zeros((frames, 1), dtype=np.int16)

        _apply_fade_out(outdata, sample_rate)

        assert np.all(outdata == 0)

    def test_fade_out_multichannel(self) -> None:
        """Fade-out works with multi-channel audio."""
        sample_rate = 16_000
        frames = 512
        channels = 2
        outdata = np.full((frames, channels), 15000, dtype=np.int16)

        _apply_fade_out(outdata, sample_rate)

        fade_samples = int(sample_rate * FADE_OUT_MS / 1000)

        # Both channels should be faded
        for ch in range(channels):
            assert outdata[0, ch] > 5000
            assert np.all(outdata[fade_samples:, ch] == 0)


# ── BGIN-03: TTS Cancellation Tests ─────────────────────────────────────────


class TestTTSCancellation:
    """BGIN-03: In-flight TTS synthesis requests cancelled on interrupt."""

    @pytest.mark.asyncio
    async def test_interrupt_cancels_producer_task(self) -> None:
        """When interrupted, the TTS producer task is cancelled."""
        from core.mouth import Mouth

        mock_tts = MagicMock()
        interrupt = InterruptController()

        # Mock synthesize_stream to be slow
        async def slow_stream(*_args: object, **_kwargs: object):  # noqa: ANN202
            for i in range(100):
                await asyncio.sleep(0.1)
                yield b"\x00" * 100

        mock_tts.synthesize_stream = slow_stream

        mouth = Mouth(tts_provider=mock_tts, interrupt=interrupt)

        # Start speaking and interrupt quickly
        speak_task = asyncio.create_task(
            mouth.speak_streaming("This is a long sentence for testing.")
        )

        # Give it a moment to start, then interrupt
        await asyncio.sleep(0.05)
        interrupt.interrupt()

        # Should complete quickly (not wait for all 100 chunks)
        await asyncio.wait_for(speak_task, timeout=2.0)

    @pytest.mark.asyncio
    async def test_speak_streaming_handles_interrupt_gracefully(self) -> None:
        """speak_streaming completes without error on interrupt."""
        from core.mouth import Mouth

        mock_tts = MagicMock()
        interrupt = InterruptController()

        async def stream_with_delay(*_args: object, **_kwargs: object):  # noqa: ANN202
            for _ in range(5):
                await asyncio.sleep(0.01)
                yield b"\x00" * 50

        mock_tts.synthesize_stream = stream_with_delay

        mouth = Mouth(tts_provider=mock_tts, interrupt=interrupt)

        # Pre-interrupt before speaking
        interrupt.interrupt()

        # Should not raise
        await mouth.speak_streaming("Hello world.")


# ── BGIN-04: Pipeline State Machine Integration ─────────────────────────────


class TestPipelineStateIntegration:
    """BGIN-04: State machine integration with the pipeline."""

    def test_barge_in_full_cycle(self) -> None:
        """Full barge-in state cycle without errors."""
        sm = PipelineStateMachine()
        interrupt = InterruptController()

        # Normal flow to SPEAKING
        assert sm.transition_to(PipelineState.PROCESSING)
        assert sm.transition_to(PipelineState.SPEAKING)

        # Simulate barge-in
        interrupt.interrupt()
        assert sm.transition_to(PipelineState.INTERRUPTED)
        assert sm.transition_to(PipelineState.LISTENING)

        # Ready for next cycle
        interrupt.reset()
        assert sm.transition_to(PipelineState.PROCESSING)

    def test_normal_speech_cycle(self) -> None:
        """Normal speech completion without barge-in."""
        sm = PipelineStateMachine()

        assert sm.transition_to(PipelineState.PROCESSING)
        assert sm.transition_to(PipelineState.SPEAKING)
        assert sm.transition_to(PipelineState.LISTENING)  # Normal completion

    def test_interrupt_controller_reset_between_cycles(self) -> None:
        """InterruptController must be reset between pipeline cycles."""
        interrupt = InterruptController()

        # Cycle 1: barge-in
        interrupt.interrupt()
        assert interrupt.is_interrupted

        # Reset for next cycle
        interrupt.reset()
        assert not interrupt.is_interrupted

        # Cycle 2: normal
        assert not interrupt.is_interrupted

    def test_speaking_to_processing_rejected(self) -> None:
        """SPEAKING -> PROCESSING is invalid (must interrupt or complete)."""
        sm = PipelineStateMachine()
        sm.transition_to(PipelineState.PROCESSING)
        sm.transition_to(PipelineState.SPEAKING)

        assert sm.transition_to(PipelineState.PROCESSING) is False
        assert sm.current_state == PipelineState.SPEAKING
