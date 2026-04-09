"""Tests for VoxError hierarchy."""

import pytest

from core.errors import (
    AudioError,
    ConfigError,
    ErrorSeverity,
    PipelineError,
    ProviderError,
    SkillError,
    VoxError,
)


class TestVoxError:
    """Tests for the base VoxError class."""

    def test_basic_creation(self) -> None:
        err = VoxError("something broke")
        assert str(err) == "something broke"
        assert err.severity == ErrorSeverity.WARNING
        assert err.retryable is False
        assert err.context == {}

    def test_custom_fields(self) -> None:
        err = VoxError(
            "network timeout",
            severity=ErrorSeverity.CRITICAL,
            user_message="Loi mang.",
            retryable=True,
            context={"provider": "openai"},
        )
        assert err.severity == ErrorSeverity.CRITICAL
        assert err.user_message == "Loi mang."
        assert err.retryable is True
        assert err.context["provider"] == "openai"

    def test_is_exception(self) -> None:
        assert issubclass(VoxError, Exception)

    def test_can_be_caught_as_exception(self) -> None:
        with pytest.raises(Exception):
            raise VoxError("test")


class TestProviderError:
    """Tests for ProviderError subclass."""

    def test_default_retryable(self) -> None:
        err = ProviderError("timeout", provider_name="openai")
        assert err.retryable is True
        assert err.provider_name == "openai"
        assert err.context["provider"] == "openai"

    def test_inherits_voxerror(self) -> None:
        err = ProviderError("test", provider_name="groq")
        assert isinstance(err, VoxError)


class TestPipelineError:
    def test_stage_in_context(self) -> None:
        err = PipelineError("bad state", stage="brain")
        assert err.stage == "brain"
        assert err.context["stage"] == "brain"


class TestSkillError:
    def test_skill_name_in_context(self) -> None:
        err = SkillError("crash", skill_name="terminal")
        assert err.skill_name == "terminal"
        assert err.context["skill"] == "terminal"


class TestAudioError:
    def test_default_not_retryable(self) -> None:
        err = AudioError("mic disconnected")
        assert err.retryable is False


class TestConfigError:
    def test_default_critical(self) -> None:
        err = ConfigError("missing yaml key")
        assert err.severity == ErrorSeverity.CRITICAL


class TestErrorHierarchy:
    """Verify isinstance relationships for catch blocks."""

    def test_provider_error_caught_by_voxerror(self) -> None:
        with pytest.raises(VoxError):
            raise ProviderError("test", provider_name="x")

    def test_pipeline_error_caught_by_voxerror(self) -> None:
        with pytest.raises(VoxError):
            raise PipelineError("test", stage="y")

    def test_skill_error_caught_by_voxerror(self) -> None:
        with pytest.raises(VoxError):
            raise SkillError("test", skill_name="z")

    def test_audio_error_caught_by_voxerror(self) -> None:
        with pytest.raises(VoxError):
            raise AudioError("test")
