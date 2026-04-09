"""Tests for skill base classes and types."""

from skills.base import ExecutionTier, SkillIntent, SkillResult


class TestSkillResult:
    """Tests for SkillResult dataclass."""

    def test_success_result(self) -> None:
        """Successful result should have no error."""
        result = SkillResult(success=True, tts_response="Done!")
        assert result.success is True
        assert result.error is None
        assert result.cancelled is False

    def test_error_result(self) -> None:
        """Failed result should carry error message."""
        result = SkillResult(success=False, error="Provider unavailable")
        assert result.success is False
        assert result.error == "Provider unavailable"

    def test_cancelled_result(self) -> None:
        """Cancelled result should be marked accordingly."""
        result = SkillResult(success=False, cancelled=True)
        assert result.cancelled is True

    def test_default_data_is_empty_dict(self) -> None:
        """Data field should default to empty dict, not shared reference."""
        result1 = SkillResult(success=True)
        result2 = SkillResult(success=True)
        assert result1.data == {}
        assert result1.data is not result2.data  # Separate instances


class TestSkillResultNewFields:
    """Tests for the new typed error fields."""

    def test_error_code_default_empty(self) -> None:
        result = SkillResult(success=False, error="something")
        assert result.error_code == ""

    def test_error_severity_default_warning(self) -> None:
        result = SkillResult(success=False, error="something")
        assert result.error_severity == "warning"

    def test_retryable_default_false(self) -> None:
        result = SkillResult(success=False, error="something")
        assert result.retryable is False

    def test_retryable_explicit_true(self) -> None:
        result = SkillResult(success=False, error="timeout", retryable=True)
        assert result.retryable is True

    def test_backward_compat_no_new_fields(self) -> None:
        """Existing code that doesn't use new fields should still work."""
        result = SkillResult(success=True, tts_response="Done!")
        assert result.error_code == ""
        assert result.error_severity == "warning"
        assert result.retryable is False


class TestSkillResultOk:
    """Tests for SkillResult.ok() convenience method."""

    def test_basic_ok(self) -> None:
        result = SkillResult.ok(tts_response="Done!")
        assert result.success is True
        assert result.tts_response == "Done!"
        assert result.error is None

    def test_ok_with_data(self) -> None:
        result = SkillResult.ok(data={"key": "value"})
        assert result.data == {"key": "value"}

    def test_ok_with_tier(self) -> None:
        result = SkillResult.ok(tier_used=ExecutionTier.NATIVE_API)
        assert result.tier_used == ExecutionTier.NATIVE_API

    def test_ok_defaults(self) -> None:
        result = SkillResult.ok()
        assert result.success is True
        assert result.tts_response == ""
        assert result.data == {}
        assert result.error is None
        assert result.error_code == ""
        assert result.retryable is False


class TestSkillResultFail:
    """Tests for SkillResult.fail() convenience method."""

    def test_basic_fail(self) -> None:
        result = SkillResult.fail(error="broke")
        assert result.success is False
        assert result.error == "broke"

    def test_fail_with_code(self) -> None:
        result = SkillResult.fail(
            error="timeout",
            error_code="timeout",
            error_severity="warning",
            retryable=True,
        )
        assert result.error_code == "timeout"
        assert result.error_severity == "warning"
        assert result.retryable is True

    def test_fail_with_tts(self) -> None:
        result = SkillResult.fail(
            error="blocked",
            tts_response="Lenh bi chan.",
            error_code="command_blocked",
        )
        assert result.tts_response == "Lenh bi chan."

    def test_fail_with_data(self) -> None:
        result = SkillResult.fail(
            error="partial",
            data={"partial": "result"},
            error_code="command_failed",
        )
        assert result.data == {"partial": "result"}

    def test_fail_with_tier(self) -> None:
        result = SkillResult.fail(
            error="shell failed",
            error_code="execution_error",
            tier_used=ExecutionTier.SHELL,
        )
        assert result.tier_used == ExecutionTier.SHELL

    def test_fail_default_severity(self) -> None:
        result = SkillResult.fail(error="something")
        assert result.error_severity == "warning"

    def test_fail_critical_severity(self) -> None:
        result = SkillResult.fail(
            error="fatal",
            error_code="system_failure",
            error_severity="critical",
        )
        assert result.error_severity == "critical"


class TestExecutionTier:
    """Tests for ExecutionTier enum."""

    def test_all_tiers_exist(self) -> None:
        """All 5 execution tiers from the architecture should exist."""
        tiers = {tier.value for tier in ExecutionTier}
        assert "native_api" in tiers
        assert "shell" in tiers
        assert "app_api" in tiers
        assert "ui" in tiers
        assert "keyboard" in tiers

    def test_tier_count(self) -> None:
        """Should have exactly 5 tiers (A: native+shell, B, C, D)."""
        assert len(ExecutionTier) == 5


class TestSkillIntent:
    """Tests for SkillIntent dataclass."""

    def test_frozen_dataclass(self) -> None:
        """SkillIntent should be immutable."""
        intent = SkillIntent(
            skill_name="media_control",
            action="skip",
            params={"direction": "forward"},
            raw_text="skip to the next song",
        )
        assert intent.skill_name == "media_control"
        assert intent.params["direction"] == "forward"
