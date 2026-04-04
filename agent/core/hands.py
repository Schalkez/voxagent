"""HANDS module: Tiered action execution.

Execution Strategy (mandatory priority order):
- Tier A: Native API / Shell (subprocess, ctypes, win32api)
- Tier B: App / Service API (Playwright, Gmail API, Spotify API)
- Tier C: UI Automation (pywinauto, pyobjc, AT-SPI)
- Tier D: Mouse / Keyboard (PyAutoGUI — last resort only)
"""

from dataclasses import dataclass

from skills.base import ExecutionTier, SkillIntent, SkillResult
from skills.registry import registry as skill_registry


@dataclass(frozen=True)
class ActionResult:
    """Result from executing an action.

    Attributes:
        success: Whether the action completed successfully.
        output: Optional output data from the action.
        error: Error message if the action failed.
        tier_used: Which execution tier was used.
    """

    success: bool
    output: str | None = None
    error: str | None = None
    tier_used: ExecutionTier | None = None


DANGEROUS_ACTIONS = frozenset(
    {
        "shutdown",
        "restart",
        "delete_file",
        "format_disk",
        "run_as_admin",
        "send_email",
    }
)


class Hands:
    """Executes actions using the cheapest viable execution tier.

    Iterates through a skill's declared execution tiers (A→D)
    and uses the first one that succeeds. Dangerous actions
    require voice confirmation before execution.
    """

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Execute an action using the loaded skills.

        Args:
            intent: The parsed SkillIntent from the Brain to execute.

        Returns:
            SkillResult with success status and optional output/error/tts.
        """
        if intent.action in DANGEROUS_ACTIONS:
            confirmed = await self._require_confirmation(intent.action, str(intent.params))
            if not confirmed:
                return SkillResult(
                    success=False,
                    error="User cancelled dangerous action",
                    cancelled=True
                )

        # 1. Fetch skill from registry
        try:
            skill = skill_registry.get_skill(intent.skill_name)
        except Exception as e:
            return SkillResult(
                success=False,
                error=str(e),
                tts_response="Tôi không tìm thấy kỹ năng này."
            )

        # 2. Check can handle
        if not await skill.can_handle(intent):
            return SkillResult(
                success=False,
                error="Skill assigned could not handle the intent.",
            )

        # 3. Execute
        # In a real environment, Hands would iterate over `skill.execution_tiers`
        # and provide the necessary implementation objects to the skill execution.
        try:
            result = await skill.execute(intent)
            return result
        except Exception as exec_err:
            return SkillResult(
                success=False,
                error=f"Execution error: {exec_err}",
                tts_response="Đã có lỗi xảy ra trong quá trình thao tác."
            )

    async def _require_confirmation(self, action: str, description: str) -> bool:
        """Request voice confirmation for dangerous actions.

        Args:
            action: The dangerous action type.
            description: Human-readable description of what will happen.

        Returns:
            True if user confirmed, False if cancelled.
        """
        # Placeholder — will use TTS prompt + STT confirmation
        return False
