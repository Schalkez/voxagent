"""Tests for Brain module — tier routing logic."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.brain import Brain, Tier
from providers.registry import ProviderRegistry
from skills.base import BaseSkill


class MockMediaSkill(BaseSkill):
    name = "media_control"
    description = "Control media playback"
    keywords = ["skip", "pause", "next", "stop"]

    async def can_handle(self, intent) -> bool:
        return True

    async def execute(self, intent):
        pass


class MockSystemSkill(BaseSkill):
    name = "system_control"
    description = "Control system power"
    keywords = ["tắt"]

    async def can_handle(self, intent) -> bool:
        return True

    async def execute(self, intent):
        pass


class MockAppSkill(BaseSkill):
    name = "app_launcher"
    description = "Launch apps"
    keywords = ["mở"]

    async def can_handle(self, intent) -> bool:
        return True

    async def execute(self, intent):
        pass


@pytest.fixture
def mock_registry() -> tuple[ProviderRegistry, MagicMock]:
    """Provide a registry with a mocked LLM."""
    registry = ProviderRegistry()
    mock_llm = MagicMock()
    # Mock default chat_with_tools response
    mock_llm.chat_with_tools = AsyncMock(
        return_value={"tool": "media_control", "result": {"action": "volume_up"}}
    )
    registry.get_llm = MagicMock(return_value=mock_llm)
    return registry, mock_llm


@pytest.fixture
def brain(mock_registry: tuple[ProviderRegistry, MagicMock]) -> Brain:
    """Provide a Brain instance with dependencies injected."""
    registry, _ = mock_registry
    skills = [MockMediaSkill(), MockSystemSkill(), MockAppSkill()]
    config = {"tiers": [{"provider": "mocked", "model": "llama3"}]}
    return Brain(registry=registry, skills=skills, routing_config=config)


class TestTierZeroRouting:
    """Tier 0 keyword matching tests."""

    def test_skip_routes_to_media_control(self, brain: Brain) -> None:
        """'skip' should route to media_control skill."""
        result = brain._try_tier_zero("skip")
        assert result is not None
        assert result.skill_name == "media_control"
        assert result.action == "skip"
        assert result.tier_used == Tier.ZERO
        assert result.confidence == 1.0

    def test_unknown_text_returns_none(self, brain: Brain) -> None:
        """Unknown text should not match any keyword."""
        result = brain._try_tier_zero("what is the weather like today?")
        assert result is None

    @pytest.mark.parametrize(
        ("keyword", "expected_skill"),
        [
            ("pause", "media_control"),
            ("next", "media_control"),
            ("stop", "media_control"),
            ("tắt", "system_control"),
            ("mở", "app_launcher"),
        ],
    )
    def test_keywords_map_correctly(self, brain: Brain, keyword: str, expected_skill: str) -> None:
        """Each keyword should map to its expected skill."""
        result = brain._try_tier_zero(keyword)
        assert result is not None
        assert result.skill_name == expected_skill

    def test_case_insensitive_matching(self, brain: Brain) -> None:
        """Keyword matching should be case-insensitive."""
        result = brain._try_tier_zero("SKIP")
        assert result is not None
        assert result.skill_name == "media_control"

    def test_keyword_in_sentence(self, brain: Brain) -> None:
        """Keywords embedded in sentences should still match."""
        result = brain._try_tier_zero("hãy skip bài này đi")
        assert result is not None
        assert result.skill_name == "media_control"


class TestBrainProcess:
    """Tests for the full Brain.process() pipeline."""

    @pytest.mark.asyncio
    async def test_tier_zero_shortcircuit(self, brain: Brain) -> None:
        """Simple keywords should resolve via Tier 0 without LLM."""
        intent = await brain.process("skip")
        assert intent.tier_used == Tier.ZERO
        assert intent.skill_name == "media_control"

    @pytest.mark.asyncio
    async def test_llm_tier_one_routing(self, mock_registry: tuple[ProviderRegistry, MagicMock]) -> None:
        """Unknown text should fall through to Tier 1 and use LLM."""
        registry, mock_llm = mock_registry
        skills = [MockMediaSkill()]
        config = {"tiers": [{"provider": "mocked", "model": "llama3"}]}
        brain = Brain(registry=registry, skills=skills, routing_config=config)

        # Mock the LLM to return an intent
        mock_llm.chat_with_tools = AsyncMock(
            return_value={"tool": "media_control", "result": {"action": "volume_up"}}
        )

        intent = await brain.process("can you turn up the volume?")
        
        assert intent.tier_used == Tier.ONE
        assert intent.skill_name == "media_control"
        assert intent.action == "volume_up"
        
        # Verify LLM was actually called
        assert mock_llm.chat_with_tools.called
