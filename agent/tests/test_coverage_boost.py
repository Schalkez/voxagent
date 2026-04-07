"""Additional tests for core modules with low coverage."""


import pytest

from core.hands import DANGEROUS_ACTIONS
from core.mouth import RESPONSE_TEMPLATES, Mouth
from skills.base import SkillIntent, SkillResult


class TestDangerousActions:
    """Test DANGEROUS_ACTIONS set."""

    def test_shutdown_is_dangerous(self) -> None:
        assert "shutdown" in DANGEROUS_ACTIONS

    def test_run_command_is_dangerous(self) -> None:
        assert "run_command" in DANGEROUS_ACTIONS

    def test_delete_file_is_dangerous(self) -> None:
        assert "delete_file" in DANGEROUS_ACTIONS


class TestMouthPlayEarcon:
    """Test Mouth.play_earcon stub."""

    @pytest.mark.asyncio
    async def test_play_earcon_does_not_raise(self) -> None:
        mouth = Mouth()
        result = await mouth.play_earcon("wake")
        assert result is None

    @pytest.mark.asyncio
    async def test_play_earcon_with_various_sounds(self) -> None:
        mouth = Mouth()
        for sound in ("wake", "done", "error", "confirm"):
            result = await mouth.play_earcon(sound)
            assert result is None


class TestMouthFormatResponse:
    """Test Mouth format_response with edge cases."""

    def test_all_template_keys(self) -> None:
        expected = {"success", "report", "error", "confirm"}
        assert expected.issubset(set(RESPONSE_TEMPLATES.keys()))

    def test_format_with_extra_kwargs(self) -> None:
        mouth = Mouth()
        result = mouth.format_response("success", action="test")
        assert isinstance(result, str)
        assert "test" in result


class TestScreenReaderSkill:
    """Test screen_reader skill."""

    @pytest.mark.asyncio
    async def test_can_handle(self) -> None:
        from skills.screen_reader import ScreenReaderSkill

        skill = ScreenReaderSkill()
        intent = SkillIntent(
            skill_name="screen_reader", action="read_text", params={}, raw_text=""
        )
        assert await skill.can_handle(intent) is True

    @pytest.mark.asyncio
    async def test_unknown_action(self) -> None:
        from skills.screen_reader import ScreenReaderSkill

        skill = ScreenReaderSkill()
        intent = SkillIntent(
            skill_name="screen_reader", action="fake", params={}, raw_text=""
        )
        result = await skill.execute(intent)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_describe_screen(self) -> None:
        from skills.screen_reader import ScreenReaderSkill

        skill = ScreenReaderSkill()
        intent = SkillIntent(
            skill_name="screen_reader", action="describe_screen", params={}, raw_text=""
        )
        result = await skill.execute(intent)
        assert result.success is True


class TestCodeReviewerSkill:
    """Test code_reviewer skill."""

    @pytest.mark.asyncio
    async def test_can_handle(self) -> None:
        from skills.code_reviewer import CodeReviewerSkill

        skill = CodeReviewerSkill()
        intent = SkillIntent(
            skill_name="code_reviewer", action="review", params={}, raw_text=""
        )
        assert await skill.can_handle(intent) is True

    @pytest.mark.asyncio
    async def test_review_visible(self) -> None:
        from skills.code_reviewer import CodeReviewerSkill

        skill = CodeReviewerSkill()
        intent = SkillIntent(
            skill_name="code_reviewer", action="review_visible", params={}, raw_text=""
        )
        result = await skill.execute(intent)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_unknown_action(self) -> None:
        from skills.code_reviewer import CodeReviewerSkill

        skill = CodeReviewerSkill()
        intent = SkillIntent(
            skill_name="code_reviewer", action="fake", params={}, raw_text=""
        )
        result = await skill.execute(intent)
        assert result.success is False


class TestFileManagerCoverage:
    """Additional file_manager tests for coverage."""

    @pytest.mark.asyncio
    async def test_search_files(self, tmp_path) -> None:
        from skills.file_manager import FileManagerSkill

        (tmp_path / "report.txt").write_text("data")
        (tmp_path / "notes.txt").write_text("more data")

        skill = FileManagerSkill()
        intent = SkillIntent(
            skill_name="file_manager",
            action="search",
            params={"query": "report", "path": str(tmp_path)},
            raw_text="find report",
        )
        result = await skill.execute(intent)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_delete_requires_path(self) -> None:
        from skills.file_manager import FileManagerSkill

        skill = FileManagerSkill()
        intent = SkillIntent(
            skill_name="file_manager",
            action="delete_file",
            params={},
            raw_text="delete",
        )
        result = await skill.execute(intent)
        assert result.success is False


class TestAppLauncherCoverage:
    """Additional app_launcher tests."""

    @pytest.mark.asyncio
    async def test_close_without_name(self) -> None:
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher",
            action="close",
            params={},
            raw_text="close",
        )
        result = await skill.execute(intent)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_list_running(self) -> None:
        from unittest.mock import patch

        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher",
            action="list_running",
            params={},
            raw_text="list apps",
        )
        with patch("skills.app_launcher.asyncio") as mock_asyncio:
            from unittest.mock import AsyncMock
            mock_asyncio.to_thread = AsyncMock(return_value=None)
            result = await skill.execute(intent)
        assert isinstance(result, SkillResult)
