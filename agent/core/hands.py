"""HANDS module: Tiered action execution.

Execution Strategy (mandatory priority order):
- Tier A: Native API / Shell (subprocess, ctypes, win32api)
- Tier B: App / Service API (Playwright, Gmail API, Spotify API)
- Tier C: UI Automation (pywinauto, pyobjc, AT-SPI)
- Tier D: Mouse / Keyboard (PyAutoGUI — last resort only)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors import SkillError, VoxError
from skills.base import ExecutionTier, SkillIntent, SkillResult
from skills.permissions import PermissionLevel, PermissionManager
from skills.registry import registry as skill_registry

if TYPE_CHECKING:
    from core.ears import Ears
    from core.mouth import Mouth

logger = logging.getLogger("voxagent.hands")


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
        "run_command",
    }
)

_CONFIRM_YES_WORDS = frozenset({"có", "vâng", "ừ", "ok", "yes", "đúng", "chắc"})
_CONFIRM_NO_WORDS = frozenset({"không", "thôi", "hủy", "no", "cancel", "dừng"})


class Hands:
    """Executes actions using the cheapest viable execution tier.

    Iterates through a skill's declared execution tiers (A→D)
    and uses the first one that succeeds. Dangerous actions
    require voice confirmation before execution.
    Permission checks enforce skill-level access control.
    """

    def __init__(
        self,
        mouth: Mouth | None = None,
        ears: Ears | None = None,
        permission_manager: PermissionManager | None = None,
    ) -> None:
        """Initialize the Hands module.

        Args:
            mouth: Mouth module for voice confirmation prompts.
            ears: Ears module for listening to confirmation responses.
            permission_manager: Optional PermissionManager for access control.
        """
        self._mouth = mouth
        self._ears = ears
        self._perm_mgr = permission_manager or PermissionManager()

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
                    cancelled=True,
                    tts_response="Đã hủy thao tác.",
                )

        # 1. Fetch skill from registry
        try:
            skill = skill_registry.get_skill(intent.skill_name)
        except (SkillError, KeyError, ValueError) as e:
            return SkillResult(
                success=False,
                error=str(e),
                tts_response="Tôi không tìm thấy kỹ năng này.",
            )

        # 1.5 Permission enforcement
        perms = self._perm_mgr.get_required_permissions(skill)
        blocked = [p for p in perms if p.level == PermissionLevel.DANGEROUS]
        if blocked and not self._perm_mgr.check_permission(skill, blocked[0].name):
            names = ", ".join(p.name for p in blocked)
            logger.warning("Skill '%s' blocked — missing dangerous permissions: %s", skill.name, names)
            return SkillResult(
                success=False,
                error=f"Permission denied: {names}",
                tts_response="Kỹ năng này cần quyền truy cập nguy hiểm mà chưa được cấp.",
            )

        # 2. Check can handle
        if not await skill.can_handle(intent):
            return SkillResult(
                success=False,
                error="Skill assigned could not handle the intent.",
            )

        # 3. Execute with tier priority (A → D)
        last_error: str | None = None
        for tier in skill.execution_tiers:
            try:
                logger.debug("Trying tier %s for skill %s", tier.value, skill.name)
                result = await skill.execute(intent)
                if result.success:
                    return result
                last_error = result.error
            except (VoxError, RuntimeError, OSError, TypeError, ValueError) as exc:
                last_error = f"Tier {tier.value} failed: {exc}"
                logger.warning(last_error)
                continue

        if last_error:
            return SkillResult(
                success=False,
                error=last_error,
                tts_response="Đã có lỗi xảy ra trong quá trình thao tác.",
            )

        return SkillResult(
            success=False,
            error="No execution tier succeeded",
            tts_response="Không thể thực hiện lệnh này.",
        )

    async def _require_confirmation(self, action: str, description: str) -> bool:
        """Request voice confirmation for dangerous actions.

        Uses Mouth to ask the question and Ears to listen for the answer.
        Falls back to auto-deny if Mouth/Ears are not configured.

        Args:
            action: The dangerous action type.
            description: Human-readable description of what will happen.

        Returns:
            True if user confirmed, False if cancelled.
        """
        if self._mouth is None or self._ears is None:
            logger.warning(
                "Cannot confirm dangerous action '%s' — no voice I/O configured",
                action,
            )
            return False

        prompt = f"Hành động {action} có thể nguy hiểm. Anh có chắc không?"
        await self._mouth.speak(prompt)

        try:
            transcription = await self._ears.push_to_talk(duration_s=5)
            answer = transcription.text.lower().strip()

            for word in answer.split():
                if word in _CONFIRM_YES_WORDS:
                    logger.info("User confirmed dangerous action: %s", action)
                    return True
                if word in _CONFIRM_NO_WORDS:
                    logger.info("User denied dangerous action: %s", action)
                    return False

            logger.info("Unclear confirmation response '%s' — defaulting to deny", answer)
            return False
        except (VoxError, TimeoutError, RuntimeError, OSError):
            logger.exception("Error during confirmation — defaulting to deny")
            return False
