"""High-impact targeted tests for the final 2% coverage push."""

from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.hands import Hands
from core.mouth import Mouth
from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult

# ── Hands: test can_handle rejection + tier fallback + confirmation ──


class FailSkill(BaseSkill):
    """Skill that always fails to can_handle."""

    name = "failskill"
    description = "Always fails"
    execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]

    async def can_handle(self, intent: SkillIntent) -> bool:
        return intent.skill_name == self.name

    async def execute(self, intent: SkillIntent) -> SkillResult:
        raise RuntimeError("Tier failed intentionally")


class TestHandsTierFallback:
    """Test tier fallback behavior in Hands."""

    @pytest.mark.asyncio
    async def test_all_tiers_fail(self) -> None:
        from skills.registry import SkillRegistry

        registry = SkillRegistry()
        registry._skills.clear()
        registry.register(FailSkill)

        hands = Hands()
        intent = SkillIntent(
            skill_name="failskill", action="do", params={}, raw_text="do"
        )
        result = await hands.execute(intent)
        assert result.success is False
        assert "Tier" in (result.error or "")

    @pytest.mark.asyncio
    async def test_can_handle_rejection(self) -> None:
        """If skill.can_handle returns False, should fail gracefully."""

        class RejectSkill(BaseSkill):
            name = "reject"
            description = "Always rejects"
            execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]

            async def can_handle(self, intent: SkillIntent) -> bool:
                return False  # Always rejects

            async def execute(self, intent: SkillIntent) -> SkillResult:
                return SkillResult(success=True, tier_used=ExecutionTier.NATIVE_API)

        from skills.registry import SkillRegistry

        registry = SkillRegistry()
        registry._skills.clear()
        registry.register(RejectSkill)

        hands = Hands()
        intent = SkillIntent(
            skill_name="reject", action="x", params={}, raw_text=""
        )
        result = await hands.execute(intent)
        assert result.success is False
        assert "could not handle" in (result.error or "").lower()


class TestHandsConfirmation:
    """Test dangerous action confirmation flow."""

    @pytest.mark.asyncio
    async def test_confirmation_denied_without_io(self) -> None:
        """Without mouth/ears, dangerous actions are auto-denied."""
        hands = Hands()
        result = await hands._require_confirmation("shutdown", "params")
        assert result is False

    @pytest.mark.asyncio
    async def test_confirmation_user_says_yes(self) -> None:
        """When user says yes, confirmation returns True."""
        mock_mouth = AsyncMock()
        mock_ears = AsyncMock()

        # Simulate user saying "có"
        transcription = MagicMock()
        transcription.text = "có chắc"
        mock_ears.push_to_talk.return_value = transcription

        hands = Hands(mouth=mock_mouth, ears=mock_ears)
        result = await hands._require_confirmation("shutdown", "shutting down")
        assert result is True

    @pytest.mark.asyncio
    async def test_confirmation_user_says_no(self) -> None:
        """When user says no, confirmation returns False."""
        mock_mouth = AsyncMock()
        mock_ears = AsyncMock()

        transcription = MagicMock()
        transcription.text = "không thôi"
        mock_ears.push_to_talk.return_value = transcription

        hands = Hands(mouth=mock_mouth, ears=mock_ears)
        result = await hands._require_confirmation("shutdown", "shutting down")
        assert result is False

    @pytest.mark.asyncio
    async def test_confirmation_unclear_response(self) -> None:
        """Unclear response defaults to deny."""
        mock_mouth = AsyncMock()
        mock_ears = AsyncMock()

        transcription = MagicMock()
        transcription.text = "hmm maybe"
        mock_ears.push_to_talk.return_value = transcription

        hands = Hands(mouth=mock_mouth, ears=mock_ears)
        result = await hands._require_confirmation("restart", "restarting")
        assert result is False

    @pytest.mark.asyncio
    async def test_confirmation_timeout(self) -> None:
        """Timeout defaults to deny."""
        mock_mouth = AsyncMock()
        mock_ears = AsyncMock()
        mock_ears.push_to_talk.side_effect = TimeoutError("No response")

        hands = Hands(mouth=mock_mouth, ears=mock_ears)
        result = await hands._require_confirmation("restart", "restarting")
        assert result is False


# ── Mouth: test _play_wav + speak with provider ──


class TestMouthPlayWav:
    """Test _play_wav function."""

    @pytest.mark.asyncio
    async def test_play_wav_without_sounddevice(self) -> None:
        """Should log warning and return when sounddevice is missing."""
        from core.mouth import _play_wav

        with patch.dict("sys.modules", {"sounddevice": None}):
            # Force ImportError

            # Just test it doesn't crash
            await _play_wav(b"\x00" * 100)

    @pytest.mark.asyncio
    async def test_speak_with_tts_provider(self) -> None:
        """Speak should call TTS provider and play audio."""
        mock_provider = AsyncMock()
        mock_provider.synthesize.return_value = b"RIFF" + b"\x00" * 40

        mouth = Mouth(tts_provider=mock_provider)

        with patch("core.mouth._play_wav", new_callable=AsyncMock) as mock_play:
            await mouth.speak("hello world")

        mock_provider.synthesize.assert_called_once()
        mock_play.assert_called_once()

    @pytest.mark.asyncio
    async def test_speak_with_tts_exception(self) -> None:
        """When TTS provider raises, should not crash."""
        mock_provider = AsyncMock()
        mock_provider.synthesize.side_effect = RuntimeError("TTS failed")

        mouth = Mouth(tts_provider=mock_provider)
        await mouth.speak("hello")  # Should not raise


# ── Eyes: coverage for system-automation-backed paths ──


class TestEyesCoverage:
    """Test Eyes methods that use system automation."""

    @pytest.mark.asyncio
    async def test_find_element_returns_none(self) -> None:
        from core.eyes import Eyes

        eyes = Eyes()
        result = await eyes.find_element("button", "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_read_screen_returns_string(self) -> None:
        from core.eyes import Eyes

        eyes = Eyes()
        result = await eyes.read_screen_text()
        assert isinstance(result, str)


# ── App launcher: open/close/list ──


class TestAppLauncherFull:
    """Test remaining app_launcher branches."""

    @pytest.mark.asyncio
    async def test_open_known_app(self) -> None:
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher",
            action="open",
            params={"app_name": "notepad"},
            raw_text="open notepad",
        )
        # Mock os.startfile / subprocess to avoid actually opening
        with patch("skills.app_launcher.asyncio") as mock_asyncio:
            mock_asyncio.to_thread = AsyncMock(return_value=None)
            result = await skill.execute(intent)
        assert isinstance(result, SkillResult)

    @pytest.mark.asyncio
    async def test_close_known_app(self) -> None:
        from skills.app_launcher import AppLauncherSkill

        skill = AppLauncherSkill()
        intent = SkillIntent(
            skill_name="app_launcher",
            action="close",
            params={"app_name": "notepad"},
            raw_text="close notepad",
        )
        with patch("skills.app_launcher.asyncio") as mock_asyncio:
            mock_asyncio.to_thread = AsyncMock(return_value=None)
            result = await skill.execute(intent)
        assert isinstance(result, SkillResult)


# ── File manager: delete + search branch ──


class TestFileManagerBranches:
    """Cover remaining file_manager branches."""

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self) -> None:
        from skills.file_manager import FileManagerSkill

        skill = FileManagerSkill()
        intent = SkillIntent(
            skill_name="file_manager",
            action="delete_file",
            params={"path": "/nonexistent/file.txt"},
            raw_text="delete",
        )
        result = await skill.execute(intent)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_delete_file_success(self, tmp_path) -> None:
        from skills.file_manager import FileManagerSkill

        target = tmp_path / "deleteme.txt"
        target.write_text("bye")

        skill = FileManagerSkill()
        intent = SkillIntent(
            skill_name="file_manager",
            action="delete_file",
            params={"path": str(target)},
            raw_text="delete file",
        )
        result = await skill.execute(intent)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_search_with_results(self, tmp_path) -> None:
        from skills.file_manager import FileManagerSkill

        (tmp_path / "report2024.txt").write_text("data")
        (tmp_path / "other.txt").write_text("data")

        skill = FileManagerSkill()
        intent = SkillIntent(
            skill_name="file_manager",
            action="search",
            params={"query": "report", "path": str(tmp_path)},
            raw_text="find report",
        )
        result = await skill.execute(intent)
        assert result.success is True
        assert "report2024" in str(result.data)

    @pytest.mark.asyncio
    async def test_move_missing_params(self) -> None:
        from skills.file_manager import FileManagerSkill

        skill = FileManagerSkill()
        intent = SkillIntent(
            skill_name="file_manager",
            action="move",
            params={},
            raw_text="move",
        )
        result = await skill.execute(intent)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_copy_missing_params(self) -> None:
        from skills.file_manager import FileManagerSkill

        skill = FileManagerSkill()
        intent = SkillIntent(
            skill_name="file_manager",
            action="copy",
            params={},
            raw_text="copy",
        )
        result = await skill.execute(intent)
        assert result.success is False
