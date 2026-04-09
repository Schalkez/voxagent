"""Code Reviewer Skill: Review code from screen or clipboard.

Captures visible code and sends to Vision LLM for review.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult
from skills.registry import register_skill

logger = logging.getLogger("voxagent.skills.code_reviewer")


@register_skill
class CodeReviewerSkill(BaseSkill):
    """Reviews code visible on screen or from clipboard."""

    name = "code_reviewer"
    description = "Review code from screen or clipboard using AI."
    keywords: ClassVar[list[str]] = [
        "review code",
        "check code",
        "xem code",
        "kiểm tra code",
        "code review",
        "lint code",
    ]
    execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.APP_API]
    permissions: ClassVar[list[str]] = ["screen:read"]

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Determine if this skill can handle the given intent."""
        return intent.skill_name == self.name

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Execute code review action.

        Supported actions: review_visible, review_clipboard.
        """
        action = intent.action

        if action in ("review_visible", "review"):
            return await self._review_visible()

        return SkillResult.fail(
            error=f"Unsupported action: {action}",
            tts_response=f"Hành động '{action}' không hỗ trợ bởi {self.name}.",
            error_code="unsupported_action",
            tier_used=ExecutionTier.APP_API,
        )

    async def _review_visible(self) -> SkillResult:
        """Review code currently visible on screen."""
        return SkillResult.ok(
            tts_response="Tính năng review code đang được phát triển. Hiện tại chưa hỗ trợ.",
            tier_used=ExecutionTier.APP_API,
        )
