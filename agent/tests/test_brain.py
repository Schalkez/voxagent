"""Tests for Brain module — tier routing logic."""

import pytest

from core.brain import Brain, Tier


class TestTierZeroRouting:
    """Tier 0 keyword matching tests."""

    def setup_method(self) -> None:
        """Create a fresh Brain instance for each test."""
        self.brain = Brain()

    def test_skip_routes_to_media_control(self) -> None:
        """'skip' should route to media_control skill."""
        result = self.brain._try_tier_zero("skip")
        assert result is not None
        assert result.skill_name == "media_control"
        assert result.action == "skip"
        assert result.tier_used == Tier.ZERO
        assert result.confidence == 1.0

    def test_unknown_text_returns_none(self) -> None:
        """Unknown text should not match any keyword."""
        result = self.brain._try_tier_zero("what is the weather like today?")
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
    def test_keywords_map_correctly(self, keyword: str, expected_skill: str) -> None:
        """Each keyword should map to its expected skill."""
        result = self.brain._try_tier_zero(keyword)
        assert result is not None
        assert result.skill_name == expected_skill

    def test_case_insensitive_matching(self) -> None:
        """Keyword matching should be case-insensitive."""
        result = self.brain._try_tier_zero("SKIP")
        assert result is not None
        assert result.skill_name == "media_control"

    def test_keyword_in_sentence(self) -> None:
        """Keywords embedded in sentences should still match."""
        result = self.brain._try_tier_zero("hãy skip bài này đi")
        assert result is not None
        assert result.skill_name == "media_control"


class TestBrainProcess:
    """Tests for the full Brain.process() pipeline."""

    def setup_method(self) -> None:
        """Create a fresh Brain instance for each test."""
        self.brain = Brain()

    @pytest.mark.asyncio
    async def test_tier_zero_shortcircuit(self) -> None:
        """Simple keywords should resolve via Tier 0 without LLM."""
        intent = await self.brain.process("skip")
        assert intent.tier_used == Tier.ZERO
        assert intent.skill_name == "media_control"

    @pytest.mark.asyncio
    async def test_unknown_falls_through(self) -> None:
        """Unknown text should fall through to higher tiers."""
        intent = await self.brain.process("what's the weather?")
        assert intent.skill_name == "unknown"
        assert intent.tier_used == Tier.ONE
