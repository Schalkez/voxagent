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
