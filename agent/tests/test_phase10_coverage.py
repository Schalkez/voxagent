"""Phase 10 coverage tests: screen reader, dependency resolver, permissions.

Targets coverage gaps identified across skills and permission modules
that were not exercised by earlier phase tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from skills.base import ExecutionTier, SkillIntent


# -- Screen Reader Skill Coverage --


class TestScreenReaderSkillCoverage:
    """Cover ScreenReaderSkill._read_text with mocked Eyes."""

    @pytest.mark.asyncio
    async def test_read_text_with_mock_eyes(self) -> None:
        """Screen reader delegates to core.eyes.Eyes for OCR text."""
        from skills.screen_reader import ScreenReaderSkill

        skill = ScreenReaderSkill()
        intent = SkillIntent(
            skill_name="screen_reader",
            action="read_text",
            params={},
            raw_text="read screen",
        )

        mock_eyes = AsyncMock()
        mock_eyes.read_screen_text = AsyncMock(return_value="Hello World")

        with patch("core.eyes.Eyes", return_value=mock_eyes):
            result = await skill.execute(intent)

        assert result.success is True
        assert "Hello" in result.tts_response


# -- Dependency Resolver Coverage --


class TestDependencyResolverCoverage:
    """Cover dependency_resolver module exports."""

    def test_skill_exists(self) -> None:
        """Dependency resolver module exists with core functions."""
        from skills.dependency_resolver import Dependency, is_installed, parse_dependencies

        dep = Dependency(package="pytest")
        assert dep.package == "pytest"


# -- Permissions Coverage --


class TestPermissionsCoverage:
    """Cover PermissionLevel enum values."""

    def test_permission_level_enum(self) -> None:
        """PermissionLevel has SAFE, ELEVATED, DANGEROUS members."""
        from skills.permissions import PermissionLevel

        assert PermissionLevel.SAFE is not None
        assert PermissionLevel.ELEVATED is not None
        assert PermissionLevel.DANGEROUS is not None
