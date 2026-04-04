from typing import ClassVar

import pytest

from core.hands import Hands
from skills.base import ExecutionTier, SkillIntent
from skills.registry import BaseSkill, SkillRegistry


class DummySkill(BaseSkill):
    name = "dummy"
    description = "A dummy skill for testing"
    execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.APP_API]

    async def can_handle(self, intent: SkillIntent) -> bool:
        return intent.skill_name == self.name

    async def execute(self, intent: SkillIntent):
        from skills.base import SkillResult
        return SkillResult(success=True, data={"run": True}, tier_used=ExecutionTier.APP_API)


@pytest.fixture
def mock_registry(monkeypatch):
    registry = SkillRegistry()
    registry._skills.clear() # Reset for test
    registry.register(DummySkill)
    return registry


@pytest.mark.asyncio
class TestHandsOrchestration:
    async def test_hands_executes_registered_skill(self, mock_registry):
        hands = Hands()
        intent = SkillIntent(
            skill_name="dummy",
            action="do_test",
            params={},
            raw_text="test dummy skill"
        )

        result = await hands.execute(intent)

        assert result.success is True
        assert result.data["run"] is True
        assert result.tier_used == ExecutionTier.APP_API

    async def test_hands_returns_error_for_unknown_skill(self, mock_registry):
        hands = Hands()
        intent = SkillIntent(
            skill_name="nonexistent",
            action="nothing",
            params={},
            raw_text="run fake"
        )

        result = await hands.execute(intent)

        assert result.success is False
        assert result.error is not None
        assert result.tts_response == "Tôi không tìm thấy kỹ năng này."
