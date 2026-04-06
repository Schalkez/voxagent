"""Tests for the Ears pipeline module."""

import pytest

from core.ears import EarsEvent, EarsState, EmptyTranscribeResult


class TestEarsState:
    """Test EarsState enum."""

    def test_states_exist(self) -> None:
        assert EarsState.STOPPED is not None
        assert EarsState.LISTENING_FOR_WAKE_WORD is not None
        assert EarsState.RECORDING_SPEECH is not None
        assert EarsState.TRANSCRIBING is not None
        assert EarsState.IDLE is not None


class TestEarsEvent:
    """Test EarsEvent dataclass."""

    def test_event_creation(self) -> None:
        event = EarsEvent(state=EarsState.STOPPED, message="test")
        assert event.state == EarsState.STOPPED
        assert event.message == "test"

    def test_event_default_message(self) -> None:
        event = EarsEvent(state=EarsState.IDLE)
        assert event.message == ""

    def test_event_is_frozen(self) -> None:
        event = EarsEvent(state=EarsState.STOPPED, message="test")
        with pytest.raises(AttributeError):
            event.state = EarsState.IDLE


class TestEmptyTranscribeResult:
    """Test EmptyTranscribeResult defaults."""

    def test_defaults(self) -> None:
        result = EmptyTranscribeResult()
        assert result.text == ""
        assert result.confidence == 0.0
        assert result.language == "vi"
        assert result.duration_ms == 0
