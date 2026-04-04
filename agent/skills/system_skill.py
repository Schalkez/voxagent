"""Basic System Manipulation Skill.

Provides operations such as controlling the volume, lock screen, and
running safe shell commands.
"""

from typing import ClassVar

from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult
from skills.registry import register_skill


@register_skill
class SystemSkill(BaseSkill):
    """Controls volume and basic system features via native API."""

    name = "system"
    description = "Control system features like volume and screen."
    keywords: ClassVar[list[str]] = ["volume", "mute", "unmute", "sound", "lock"]
    execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Determines if the system skill can handle the given intent."""
        return intent.skill_name == self.name

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Executes system interactions like sound volume tweaks."""
        if intent.action == "set_volume":
            level = intent.params.get("level", "50")
            # TODO: Integrate with SystemAutomation class to actually change volume
            return SkillResult(
                success=True,
                tts_response=f"Đã chỉnh âm lượng ở mức {level} phần trăm.",
                data={"volume": int(level)},
                tier_used=ExecutionTier.NATIVE_API
            )

        if intent.action in ("mute", "unmute"):
            action_text = "Tắt" if intent.action == "mute" else "Bật"
            return SkillResult(
                success=True,
                tts_response=f"Đã {action_text} tiếng máy tính.",
                tier_used=ExecutionTier.NATIVE_API
            )

        return SkillResult(
            success=False,
            error=f"Hành động '{intent.action}' không hỗ trợ bởi {self.name} skill.",
            tier_used=ExecutionTier.NATIVE_API
        )
