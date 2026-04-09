"""Compliance tests for core/app.py and core/ears.py.

Validates that VoxAgentApp and Ears can be instantiated and
manage basic lifecycle with all heavy dependencies mocked.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.config import VoxAgentConfig
from core.ears import Ears, EarsState, EmptyTranscribeResult
from core.errors import PipelineError

# ── Helpers ──────────────────────────────────────────


def _make_mock_stt() -> MagicMock:
    """Create a mock STT provider."""
    stt = MagicMock()
    stt.transcribe = AsyncMock(
        return_value=MagicMock(text="hello", confidence=0.9, language="vi", duration_ms=500),
    )
    return stt


def _make_config() -> VoxAgentConfig:
    """Create a default VoxAgentConfig for testing."""
    return VoxAgentConfig()


# ── VoxAgentApp Tests ────────────────────────────────


class TestVoxAgentAppInstantiation:
    """Test that VoxAgentApp can be created with mocked dependencies."""

    @patch("core.app.load_config", return_value=VoxAgentConfig())
    def test_instantiation_default(self, _mock_load: MagicMock) -> None:
        """VoxAgentApp should instantiate with default arguments."""
        from core.app import VoxAgentApp

        app = VoxAgentApp()
        assert app.debug is False
        assert app._running is False

    @patch("core.app.load_config", return_value=VoxAgentConfig())
    def test_instantiation_debug_mode(self, _mock_load: MagicMock) -> None:
        """VoxAgentApp should accept debug=True."""
        from core.app import VoxAgentApp

        app = VoxAgentApp(debug=True)
        assert app.debug is True

    @patch("core.app.load_config", return_value=VoxAgentConfig())
    def test_stop_when_not_running_is_noop(self, _mock_load: MagicMock) -> None:
        """Calling stop() before start() should not raise."""
        from core.app import VoxAgentApp

        app = VoxAgentApp()
        asyncio.get_event_loop().run_until_complete(app.stop())
        assert app._running is False

    @patch("core.app.load_config", return_value=VoxAgentConfig())
    def test_config_is_loaded(self, _mock_load: MagicMock) -> None:
        """VoxAgentApp should have a config object after init."""
        from core.app import VoxAgentApp

        app = VoxAgentApp()
        assert app._config is not None
        assert isinstance(app._config, VoxAgentConfig)

    @patch("core.app.load_config", return_value=VoxAgentConfig())
    def test_registry_is_created(self, _mock_load: MagicMock) -> None:
        """VoxAgentApp should create a ProviderRegistry."""
        from core.app import VoxAgentApp
        from providers.registry import ProviderRegistry

        app = VoxAgentApp()
        assert isinstance(app._registry, ProviderRegistry)


# ── Ears Tests ───────────────────────────────────────


class TestEarsLifecycle:
    """Test Ears class handles basic lifecycle and state management."""

    def test_initial_state_is_idle(self) -> None:
        """Ears should start in IDLE state."""
        with (
            patch("core.ears.AudioRecorder"),
            patch("core.ears.WakeWordDetector"),
            patch("core.ears.VoiceActivityDetector"),
        ):
            ears = Ears(stt_provider=_make_mock_stt(), config=_make_config())
            assert ears.state == EarsState.IDLE

    def test_state_property_returns_current_state(self) -> None:
        """The state property should reflect internal state."""
        with (
            patch("core.ears.AudioRecorder"),
            patch("core.ears.WakeWordDetector"),
            patch("core.ears.VoiceActivityDetector"),
        ):
            ears = Ears(stt_provider=_make_mock_stt(), config=_make_config())
            assert ears.state == ears._state

    def test_event_callback_registration(self) -> None:
        """on_event should register callbacks without error."""
        with (
            patch("core.ears.AudioRecorder"),
            patch("core.ears.WakeWordDetector"),
            patch("core.ears.VoiceActivityDetector"),
        ):
            ears = Ears(stt_provider=_make_mock_stt(), config=_make_config())
            callback = MagicMock()
            ears.on_event(callback)
            assert callback in ears._event_callbacks

    def test_emit_updates_state_and_notifies(self) -> None:
        """_emit should update state and call registered callbacks."""
        with (
            patch("core.ears.AudioRecorder"),
            patch("core.ears.WakeWordDetector"),
            patch("core.ears.VoiceActivityDetector"),
        ):
            ears = Ears(stt_provider=_make_mock_stt(), config=_make_config())
            callback = MagicMock()
            ears.on_event(callback)

            ears._emit(EarsState.RECORDING_SPEECH, "test message")

            assert ears.state == EarsState.RECORDING_SPEECH
            callback.assert_called_once()
            event = callback.call_args[0][0]
            assert event.state == EarsState.RECORDING_SPEECH
            assert event.message == "test message"

    def test_emit_handles_callback_error(self) -> None:
        """_emit should not crash when a callback raises."""
        with (
            patch("core.ears.AudioRecorder"),
            patch("core.ears.WakeWordDetector"),
            patch("core.ears.VoiceActivityDetector"),
        ):
            ears = Ears(stt_provider=_make_mock_stt(), config=_make_config())
            bad_callback = MagicMock(side_effect=TypeError("test error"))
            ears.on_event(bad_callback)

            # Should not raise despite callback error
            ears._emit(EarsState.STOPPED, "shutting down")
            assert ears.state == EarsState.STOPPED

    def test_ensure_started_raises_when_not_active(self) -> None:
        """_ensure_started should raise RuntimeError if recorder is inactive."""
        with (
            patch("core.ears.AudioRecorder") as mock_recorder_cls,
            patch("core.ears.WakeWordDetector"),
            patch("core.ears.VoiceActivityDetector"),
        ):
            mock_recorder_cls.return_value.is_active = False
            ears = Ears(stt_provider=_make_mock_stt(), config=_make_config())

            with pytest.raises(PipelineError, match="Ears not started"):
                ears._ensure_started()

    @pytest.mark.asyncio
    async def test_stop_calls_subcomponents(self) -> None:
        """stop() should release audio resources and set STOPPED state."""
        with (
            patch("core.ears.AudioRecorder") as mock_recorder_cls,
            patch("core.ears.WakeWordDetector") as mock_ww_cls,
            patch("core.ears.VoiceActivityDetector") as mock_vad_cls,
        ):
            mock_recorder = mock_recorder_cls.return_value
            mock_recorder.stop = AsyncMock()
            mock_ww = mock_ww_cls.return_value
            mock_vad = mock_vad_cls.return_value

            ears = Ears(stt_provider=_make_mock_stt(), config=_make_config())
            await ears.stop()

            mock_recorder.stop.assert_awaited_once()
            mock_ww.unload.assert_called_once()
            mock_vad.unload.assert_called_once()
            assert ears.state == EarsState.STOPPED

    @pytest.mark.asyncio
    async def test_start_listening_loads_models(self) -> None:
        """start_listening should load wake word and VAD models."""
        with (
            patch("core.ears.AudioRecorder") as mock_recorder_cls,
            patch("core.ears.WakeWordDetector") as mock_ww_cls,
            patch("core.ears.VoiceActivityDetector") as mock_vad_cls,
        ):
            mock_recorder = mock_recorder_cls.return_value
            mock_recorder.start = AsyncMock()
            mock_ww = mock_ww_cls.return_value
            mock_vad = mock_vad_cls.return_value

            ears = Ears(stt_provider=_make_mock_stt(), config=_make_config())
            await ears.start_listening()

            mock_ww.load.assert_called_once()
            mock_vad.load.assert_called_once()
            mock_recorder.start.assert_awaited_once()
            assert ears.state == EarsState.LISTENING_FOR_WAKE_WORD

    def test_empty_transcribe_result_returned_for_no_frames(self) -> None:
        """EmptyTranscribeResult should have sensible defaults."""
        result = EmptyTranscribeResult()
        assert result.text == ""
        assert result.confidence == 0.0
        assert result.language == "vi"
        assert result.duration_ms == 0
