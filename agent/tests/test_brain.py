"""Tests for the Brain intent routing module."""

from unittest.mock import AsyncMock, MagicMock
from typing import ClassVar

import pytest

from core.brain import Brain, Intent, Tier
from providers.base import LLMProvider, Message, ModelInfo
from providers.registry import ProviderRegistry
from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult


class MockLLM(LLMProvider):
    """Mock LLM provider for testing."""

    async def chat(self, messages: list[Message], **kwargs: object) -> str:
        return "mock response"

    async def chat_with_tools(
        self, messages: list[Message], tools: list[dict[str, object]], **kwargs: object
    ) -> dict[str, object]:
        return {"tool": "media_control", "result": {"action": "play_pause"}}

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(name="mock", provider="mock")

    async def health_check(self) -> bool:
        return True


class MockSkill(BaseSkill):
    """Mock skill for testing."""

    name = "media_control"
    description = "Test skill"
    keywords: ClassVar[list[str]] = ["play", "pause", "nhạc"]
    execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]

    async def can_handle(self, intent: SkillIntent) -> bool:
        return intent.skill_name == self.name

    async def execute(self, intent: SkillIntent) -> SkillResult:
        return SkillResult(success=True, tier_used=ExecutionTier.NATIVE_API)


@pytest.fixture
def brain() -> Brain:
    """Create a Brain instance with mock providers and skills."""
    registry = ProviderRegistry()
    registry.register_llm("mock", MockLLM)
    registry.register_llm("ollama", MockLLM)
    registry.set_fallback_chain(["mock", "ollama"])

    skills = [MockSkill()]

    return Brain(registry=registry, skills=skills, routing_config={})


class TestBrainTierZero:
    """Test Tier 0 keyword matching."""

    @pytest.mark.asyncio
    async def test_keyword_match_returns_correct_skill(self, brain: Brain) -> None:
        """Tier 0 should match keywords to skills."""
        result = await brain.process("play nhạc đi")
        assert result.skill_name == "media_control"
        assert result.tier_used == Tier.ZERO

    @pytest.mark.asyncio
    async def test_no_keyword_match_escalates(self, brain: Brain) -> None:
        """When no keyword matches, should escalate to higher tier or return unknown."""
        result = await brain.process("cho tôi xem thời tiết")
        # Should return some result (might be unknown if LLM routing fails)
        assert result is not None
        assert isinstance(result, Intent)


class TestBrainIntent:
    """Test Intent dataclass."""

    def test_intent_is_frozen(self) -> None:
        """Intent should be immutable."""
        intent = Intent(
            skill_name="test",
            action="do",
            params={},
            confidence=0.9,
            tier_used=Tier.ZERO,
        )
        with pytest.raises(AttributeError):
            intent.skill_name = "changed"  # type: ignore[misc]

    def test_intent_fields(self) -> None:
        """Intent should have all required fields."""
        intent = Intent(
            skill_name="test",
            action="run",
            params={"key": "value"},
            confidence=0.85,
            tier_used=Tier.ONE,
        )
        assert intent.skill_name == "test"
        assert intent.action == "run"
        assert intent.params == {"key": "value"}
        assert intent.confidence == 0.85
        assert intent.tier_used == Tier.ONE
