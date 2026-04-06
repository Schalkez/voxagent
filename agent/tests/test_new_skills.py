"""Tests for Phase 2 skills: terminal, file_manager, browser_control."""

import pytest

from skills.base import SkillIntent


class TestTerminalSkill:
    """Test the terminal skill."""

    @pytest.fixture
    def intent(self) -> SkillIntent:
        return SkillIntent(
            skill_name="terminal",
            action="run_command",
            params={"command": "echo hello"},
            raw_text="run echo hello",
        )

    @pytest.mark.asyncio
    async def test_can_handle(self, intent: SkillIntent) -> None:
        from skills.terminal import TerminalSkill

        skill = TerminalSkill()
        assert await skill.can_handle(intent) is True

    @pytest.mark.asyncio
    async def test_rejects_other(self) -> None:
        from skills.terminal import TerminalSkill

        skill = TerminalSkill()
        other = SkillIntent(skill_name="other", action="x", params={}, raw_text="")
        assert await skill.can_handle(other) is False

    @pytest.mark.asyncio
    async def test_run_echo(self) -> None:
        from skills.terminal import TerminalSkill

        skill = TerminalSkill()
        intent = SkillIntent(
            skill_name="terminal",
            action="run_command",
            params={"command": "echo hello"},
            raw_text="run echo hello",
        )
        result = await skill.execute(intent)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_blocked_command(self) -> None:
        from skills.terminal import TerminalSkill

        skill = TerminalSkill()
        intent = SkillIntent(
            skill_name="terminal",
            action="run_command",
            params={"command": "rm -rf /"},
            raw_text="run rm -rf /",
        )
        result = await skill.execute(intent)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_unknown_action(self) -> None:
        from skills.terminal import TerminalSkill

        skill = TerminalSkill()
        intent = SkillIntent(
            skill_name="terminal", action="fake", params={}, raw_text=""
        )
        result = await skill.execute(intent)
        assert result.success is False


class TestFileManagerSkill:
    """Test the file_manager skill."""

    @pytest.mark.asyncio
    async def test_can_handle(self) -> None:
        from skills.file_manager import FileManagerSkill

        skill = FileManagerSkill()
        intent = SkillIntent(
            skill_name="file_manager", action="list_dir", params={}, raw_text=""
        )
        assert await skill.can_handle(intent) is True

    @pytest.mark.asyncio
    async def test_list_dir(self, tmp_path) -> None:
        from skills.file_manager import FileManagerSkill

        # Create a temp file
        (tmp_path / "test.txt").write_text("hello")

        skill = FileManagerSkill()
        intent = SkillIntent(
            skill_name="file_manager",
            action="list_dir",
            params={"path": str(tmp_path)},
            raw_text=f"list {tmp_path}",
        )
        result = await skill.execute(intent)
        assert result.success is True
        assert "test.txt" in str(result.data)

    @pytest.mark.asyncio
    async def test_unknown_action(self) -> None:
        from skills.file_manager import FileManagerSkill

        skill = FileManagerSkill()
        intent = SkillIntent(
            skill_name="file_manager", action="fake", params={}, raw_text=""
        )
        result = await skill.execute(intent)
        assert result.success is False


class TestBrowserControlSkill:
    """Test the browser_control skill."""

    @pytest.mark.asyncio
    async def test_can_handle(self) -> None:
        from skills.browser_control import BrowserControlSkill

        skill = BrowserControlSkill()
        intent = SkillIntent(
            skill_name="browser_control", action="open_url", params={}, raw_text=""
        )
        assert await skill.can_handle(intent) is True

    @pytest.mark.asyncio
    async def test_search_web(self) -> None:
        from unittest.mock import patch

        from skills.browser_control import BrowserControlSkill

        skill = BrowserControlSkill()
        intent = SkillIntent(
            skill_name="browser_control",
            action="search_web",
            params={"query": "python docs"},
            raw_text="search python docs",
        )
        with patch("webbrowser.open", return_value=True):
            result = await skill.execute(intent)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_unknown_action(self) -> None:
        from skills.browser_control import BrowserControlSkill

        skill = BrowserControlSkill()
        intent = SkillIntent(
            skill_name="browser_control", action="fake", params={}, raw_text=""
        )
        result = await skill.execute(intent)
        assert result.success is False
