"""HANDS module: Tiered action execution.

Execution Strategy (mandatory priority order):
- Tier A: Native API / Shell (subprocess, ctypes, win32api)
- Tier B: App / Service API (Playwright, Gmail API, Spotify API)
- Tier C: UI Automation (pywinauto, pyobjc, AT-SPI)
- Tier D: Mouse / Keyboard (PyAutoGUI — last resort only)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.errors import SkillError, VoxError
from core.logging import get_logger
from skills.base import (
    SKILL_ERR_CANCELLED,
    SKILL_ERR_NOT_FOUND,
    SKILL_ERR_PERMISSION_DENIED,
    SKILL_ERR_UNSUPPORTED_ACTION,
    ExecutionTier,
    SkillIntent,
    SkillResult,
)
from skills.permissions import PermissionLevel, PermissionManager
from skills.registry import registry as skill_registry

if TYPE_CHECKING:
    from core.ears import Ears
    from core.mouth import Mouth

logger = get_logger(module="hands")


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
                    error_code=SKILL_ERR_CANCELLED,
                    error_severity="info",
                    cancelled=True,
                    tts_response="Đã hủy thao tác.",
                )

        # 1. Fetch skill from registry
        try:
            skill = skill_registry.get_skill(intent.skill_name)
        except (SkillError, KeyError, ValueError) as e:
            return SkillResult.fail(
                error=str(e),
                tts_response="Tôi không tìm thấy kỹ năng này.",
                error_code=SKILL_ERR_NOT_FOUND,
            )

        # 1.5 Permission enforcement
        perms = self._perm_mgr.get_required_permissions(skill)
        blocked = [p for p in perms if p.level == PermissionLevel.DANGEROUS]
        if blocked and not self._perm_mgr.check_permission(skill, blocked[0].name):
            names = ", ".join(p.name for p in blocked)
            logger.warning("skill blocked — missing dangerous permissions", skill=skill.name, permissions=names)
            return SkillResult.fail(
                error=f"Permission denied: {names}",
                tts_response="Kỹ năng này cần quyền truy cập nguy hiểm mà chưa được cấp.",
                error_code=SKILL_ERR_PERMISSION_DENIED,
                error_severity="warning",
            )

        # 2. Check can handle
        if not await skill.can_handle(intent):
            return SkillResult.fail(
                error="Skill assigned could not handle the intent.",
                error_code=SKILL_ERR_UNSUPPORTED_ACTION,
            )

        # 3. Execute with tier priority (A → D)
        last_error: str | None = None
        for tier in skill.execution_tiers:
            try:
                logger.debug("trying execution tier", tier=tier.value, skill=skill.name)
                result = await skill.execute(intent)
                if result.success:
                    return result
                last_error = result.error
            except (VoxError, RuntimeError, OSError, TypeError, ValueError) as exc:
                last_error = f"Tier {tier.value} failed: {exc}"
                logger.warning(last_error)
                continue

        if last_error:
            return SkillResult.fail(
                error=last_error,
                tts_response="Đã có lỗi xảy ra trong quá trình thao tác.",
                error_code="tier_exhausted",
            )

        return SkillResult.fail(
            error="No execution tier succeeded",
            tts_response="Không thể thực hiện lệnh này.",
            error_code="tier_exhausted",
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
                "cannot confirm dangerous action — no voice I/O configured",
                action=action,
            )
            return False

        prompt = f"Hành động {action} có thể nguy hiểm. Anh có chắc không?"
        await self._mouth.speak(prompt)

        try:
            transcription = await self._ears.push_to_talk(duration_s=5)
            answer = transcription.text.lower().strip()

            for word in answer.split():
                if word in _CONFIRM_YES_WORDS:
                    logger.info("user confirmed dangerous action", action=action)
                    return True
                if word in _CONFIRM_NO_WORDS:
                    logger.info("user denied dangerous action", action=action)
                    return False

            logger.info("unclear confirmation response — defaulting to deny", answer=answer)
            return False
        except (VoxError, TimeoutError, RuntimeError, OSError):
            logger.exception("error during confirmation — defaulting to deny")
            return False
