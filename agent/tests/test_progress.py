"""Tests for progress monitoring in Hands module.

PROG-02: Timeout-based progress updates for long-running skills.
Skills running >3s trigger spoken "Đang xử lý..." with periodic repeats.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.hands import (
    PROGRESS_INITIAL_DELAY_S,
    PROGRESS_MESSAGES,
    PROGRESS_REPEAT_INTERVAL_S,
    Hands,
)
from skills.base import ExecutionTier, SkillIntent, SkillResult


def _make_intent(skill: str = "test_skill", action: str = "test") -> SkillIntent:
    """Create a test SkillIntent."""
    return SkillIntent(
        skill_name=skill,
        action=action,
        params={},
        raw_text="test command",
    )


def _make_fast_skill() -> MagicMock:
    """Create a mock skill that completes instantly."""
    skill = MagicMock()
    skill.name = "fast_skill"
    skill.execution_tiers = [ExecutionTier.NATIVE_API]
    skill.can_handle = AsyncMock(return_value=True)
    skill.execute = AsyncMock(
        return_value=SkillResult(success=True, tts_response="Done"),
    )
    return skill


def _make_slow_skill(delay_s: float = 4.0) -> MagicMock:
    """Create a mock skill that takes longer than the progress threshold.

    Args:
        delay_s: How long the skill takes to complete.
    """
    skill = MagicMock()
    skill.name = "slow_skill"
    skill.execution_tiers = [ExecutionTier.NATIVE_API]
    skill.can_handle = AsyncMock(return_value=True)

    async def slow_execute(intent: SkillIntent) -> SkillResult:
        await asyncio.sleep(delay_s)
        return SkillResult(success=True, tts_response="Finally done")

    skill.execute = AsyncMock(side_effect=slow_execute)
    return skill


class TestProgressConstants:
    """Test progress-related constants."""

    def test_initial_delay_is_3s(self) -> None:
        """Progress should start after 3 seconds."""
        assert PROGRESS_INITIAL_DELAY_S == 3.0

    def test_repeat_interval_is_5s(self) -> None:
        """Progress should repeat every 5 seconds."""
        assert PROGRESS_REPEAT_INTERVAL_S == 5.0

    def test_progress_messages_not_empty(self) -> None:
        """There should be multiple progress messages."""
        assert len(PROGRESS_MESSAGES) >= 2

    def test_first_message_is_processing(self) -> None:
        """First progress message should indicate processing."""
        assert "xử lý" in PROGRESS_MESSAGES[0].lower()


class TestProgressMonitor:
    """Test progress announcement during skill execution."""

    @pytest.mark.asyncio
    async def test_fast_skill_no_progress(self) -> None:
        """Skills completing under 3s should NOT trigger progress."""
        mock_mouth = MagicMock()
        mock_mouth.speak = AsyncMock()
        mock_mouth.play_earcon = AsyncMock()

        hands = Hands(mouth=mock_mouth)

        skill = _make_fast_skill()
        intent = _make_intent()

        with patch("core.hands.skill_registry") as mock_reg:
            mock_reg.get_skill.return_value = skill
            result = await hands.execute(intent)

        assert result.success
        # speak should NOT be called for progress (fast skill)
        mock_mouth.speak.assert_not_called()

    @pytest.mark.asyncio
    async def test_slow_skill_triggers_progress(self) -> None:
        """PROG-02: Skills exceeding 3s should trigger progress update."""
        mock_mouth = MagicMock()
        mock_mouth.speak = AsyncMock()
        mock_mouth.play_earcon = AsyncMock()

        hands = Hands(mouth=mock_mouth)

        # Skill that takes 4s (over the 3s threshold)
        skill = _make_slow_skill(delay_s=4.0)
        intent = _make_intent()

        with patch("core.hands.skill_registry") as mock_reg:
            mock_reg.get_skill.return_value = skill
            result = await hands.execute(intent)

        assert result.success
        # Should have spoken at least one progress message
        assert mock_mouth.speak.call_count >= 1
        first_call = mock_mouth.speak.call_args_list[0]
        assert first_call[0][0] == PROGRESS_MESSAGES[0]

    @pytest.mark.asyncio
    async def test_progress_cancelled_on_completion(self) -> None:
        """Progress task should be cancelled when skill finishes."""
        mock_mouth = MagicMock()
        mock_mouth.speak = AsyncMock()
        mock_mouth.play_earcon = AsyncMock()

        hands = Hands(mouth=mock_mouth)

        # Skill takes 3.5s — just over threshold, completes before second message
        skill = _make_slow_skill(delay_s=3.5)
        intent = _make_intent()

        with patch("core.hands.skill_registry") as mock_reg:
            mock_reg.get_skill.return_value = skill
            result = await hands.execute(intent)

        assert result.success
        # At most 1 progress message (3s delay + cancelled before 5s repeat)
        assert mock_mouth.speak.call_count <= 1

    @pytest.mark.asyncio
    async def test_progress_without_mouth_is_noop(self) -> None:
        """Progress should not crash when Mouth is not available."""
        hands = Hands(mouth=None)

        skill = _make_slow_skill(delay_s=4.0)
        intent = _make_intent()

        with patch("core.hands.skill_registry") as mock_reg:
            mock_reg.get_skill.return_value = skill
            result = await hands.execute(intent)

        # Should complete without error even with no mouth
        assert result.success


class TestAnnounceProgress:
    """Test the _announce_progress method directly."""

    @pytest.mark.asyncio
    async def test_announce_waits_initial_delay(self) -> None:
        """_announce_progress should wait PROGRESS_INITIAL_DELAY_S first."""
        mock_mouth = MagicMock()
        mock_mouth.speak = AsyncMock()

        hands = Hands(mouth=mock_mouth)

        # Run for just 1s — should NOT produce any message
        task = asyncio.create_task(hands._announce_progress("test"))
        await asyncio.sleep(1.0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        mock_mouth.speak.assert_not_called()

    @pytest.mark.asyncio
    async def test_announce_speaks_first_message(self) -> None:
        """_announce_progress should speak first message after delay."""
        mock_mouth = MagicMock()
        mock_mouth.speak = AsyncMock()

        hands = Hands(mouth=mock_mouth)

        # Run for 3.5s — should produce exactly 1 message
        task = asyncio.create_task(hands._announce_progress("test"))
        await asyncio.sleep(3.5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert mock_mouth.speak.call_count == 1
        mock_mouth.speak.assert_called_with(PROGRESS_MESSAGES[0])

    @pytest.mark.asyncio
    async def test_announce_mouth_error_does_not_crash(self) -> None:
        """Progress should survive mouth.speak() failures."""
        mock_mouth = MagicMock()
        mock_mouth.speak = AsyncMock(side_effect=RuntimeError("TTS down"))

        hands = Hands(mouth=mock_mouth)

        task = asyncio.create_task(hands._announce_progress("test"))
        await asyncio.sleep(3.5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should have attempted to speak (and survived the error)
        assert mock_mouth.speak.call_count >= 1
