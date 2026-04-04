"""Tests for built-in skills."""

from typing import ClassVar

import pytest
from unittest.mock import patch, MagicMock

from skills.base import ExecutionTier, SkillIntent, SkillResult


class TestMediaControlSkill:
    """Test the media_control skill."""

    @pytest.fixture
    def intent(self) -> SkillIntent:
        """Create a base intent for media_control."""
        return SkillIntent(
            skill_name="media_control",
            action="play_pause",
            params={},
            raw_text="play music",
        )

    @pytest.mark.asyncio
    async def test_can_handle_own_intent(self) -> None:
        """Should handle intents directed at media_control."""
        from skills.media_control import MediaControlSkill

        skill = MediaControlSkill()
        intent = SkillIntent(
            skill_name="media_control", action="play", params={}, raw_text="play"
        )
        assert await skill.can_handle(intent) is True

    @pytest.mark.asyncio
    async def test_rejects_other_skills(self) -> None:
        """Should not handle intents for other skills."""
        from skills.media_control import MediaControlSkill

        skill = MediaControlSkill()
        intent = SkillIntent(
            skill_name="other_skill", action="play", params={}, raw_text="play"
        )
        assert await skill.can_handle(intent) is False

    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self) -> None:
        """Should return error for unsupported actions."""
        from skills.media_control import MediaControlSkill

        skill = MediaControlSkill()
        intent = SkillIntent(
            skill_name="media_control",
            action="unknown_action",
            params={},
            raw_text="do something weird",
        )
        result = await skill.execute(intent)
        assert result.success is False
        assert result.tier_used == ExecutionTier.NATIVE_API


class TestAppLauncherSkill:
    """Test the app_launcher skill."""

    @pytest.mark.asyncio
    async def test_can_handle_own_intent(self) -> None:
        """Should handle intents directed at app_launcher."""
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher", action="open", params={"app": "chrome"}, raw_text="mở chrome"
        )
        assert await skill.can_handle(intent) is True

    @pytest.mark.asyncio
    async def test_open_without_name_returns_error(self) -> None:
        """Should ask for app name when not provided."""
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher", action="open", params={}, raw_text="mở"
        )
        result = await skill.execute(intent)
        assert result.success is False
        assert "Anh muốn mở ứng dụng nào" in (result.tts_response or "")

    @pytest.mark.asyncio
    async def test_unknown_action(self) -> None:
        """Should return error for unsupported actions."""
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher",
            action="destroy",
            params={},
            raw_text="destroy everything",
        )
        result = await skill.execute(intent)
        assert result.success is False


class TestSystemControlSkill:
    """Test the system_control skill."""

    @pytest.mark.asyncio
    async def test_can_handle_own_intent(self) -> None:
        """Should handle intents directed at system_control."""
        from skills.system_control import SystemControlSkill

        skill = SystemControlSkill()
        intent = SkillIntent(
            skill_name="system_control", action="lock", params={}, raw_text="khóa"
        )
        assert await skill.can_handle(intent) is True

    @pytest.mark.asyncio
    async def test_unknown_action(self) -> None:
        """Should return error for unsupported actions."""
        from skills.system_control import SystemControlSkill

        skill = SystemControlSkill()
        intent = SkillIntent(
            skill_name="system_control",
            action="fly_to_moon",
            params={},
            raw_text="bay lên mặt trăng",
        )
        result = await skill.execute(intent)
        assert result.success is False


class TestSystemVolumeSkill:
    """Test the system volume skill."""

    @pytest.mark.asyncio
    async def test_set_volume(self) -> None:
        """Should respond with Vietnamese confirmation."""
        from skills.system_skill import SystemVolumeSkill

        skill = SystemVolumeSkill()
        intent = SkillIntent(
            skill_name="system",
            action="set_volume",
            params={"level": "75"},
            raw_text="volume 75",
        )
        result = await skill.execute(intent)
        assert result.success is True
        assert "75" in (result.tts_response or "")
        assert result.tier_used == ExecutionTier.NATIVE_API

    @pytest.mark.asyncio
    async def test_mute(self) -> None:
        """Should handle mute action."""
        from skills.system_skill import SystemVolumeSkill

        skill = SystemVolumeSkill()
        intent = SkillIntent(
            skill_name="system",
            action="mute",
            params={},
            raw_text="tắt tiếng",
        )
        result = await skill.execute(intent)
        assert result.success is True
        assert "Tắt" in (result.tts_response or "")
