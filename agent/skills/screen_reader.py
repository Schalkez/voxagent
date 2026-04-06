"""Screen Reader Skill: Read text from screen, describe visible content.

Uses Eyes module for OCR and Vision LLM for complex understanding.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult
from skills.registry import register_skill

logger = logging.getLogger("voxagent.skills.screen_reader")


@register_skill
class ScreenReaderSkill(BaseSkill):
    """Reads and describes screen content."""

    name = "screen_reader"
    description = "Read text from screen or describe what's currently visible."
    keywords: ClassVar[list[str]] = [
        "read screen",
        "what's on screen",
        "đọc màn hình",
        "trên màn hình có gì",
        "screen text",
        "đọc chữ",
    ]
    execution_tiers: ClassVar[list[ExecutionTier]] = [
        ExecutionTier.NATIVE_API,
        ExecutionTier.APP_API,
    ]
    permissions: ClassVar[list[str]] = ["screen:read"]

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Determine if this skill can handle the given intent."""
        return intent.skill_name == self.name

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Execute screen reading action.

        Supported actions: read_text, describe_screen.
        """
        action = intent.action

        if action == "read_text":
            return await self._read_text()

        if action == "describe_screen":
            return await self._describe_screen()

        return SkillResult(
            success=False,
            error=f"Hành động '{action}' không hỗ trợ bởi {self.name}.",
            tier_used=ExecutionTier.NATIVE_API,
        )

    async def _read_text(self) -> SkillResult:
        """Read text from the current screen using OCR."""
        try:
            from core.eyes import Eyes

            eyes = Eyes()
            text = await eyes.read_screen_text()

            if text:
                preview = text[:200]
                return SkillResult(
                    success=True,
                    tts_response=f"Tôi đọc được: {preview}",
                    data={"text": text},
                    tier_used=ExecutionTier.NATIVE_API,
                )
            return SkillResult(
                success=True,
                tts_response="Không đọc được chữ nào trên màn hình.",
                tier_used=ExecutionTier.NATIVE_API,
            )
        except (ImportError, RuntimeError, OSError) as e:
            return SkillResult(
                success=False,
                error=str(e),
                tts_response="Không thể đọc màn hình.",
                tier_used=ExecutionTier.NATIVE_API,
            )

    async def _describe_screen(self) -> SkillResult:
        """Describe screen content using Vision LLM."""
        return SkillResult(
            success=True,
            tts_response="Tính năng mô tả màn hình đang được phát triển.",
            tier_used=ExecutionTier.APP_API,
        )
