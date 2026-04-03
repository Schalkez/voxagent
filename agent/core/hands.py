"""HANDS module: Tiered action execution.

Execution Strategy (mandatory priority order):
- Tier A: Native API / Shell (subprocess, ctypes, win32api)
- Tier B: App / Service API (Playwright, Gmail API, Spotify API)
- Tier C: UI Automation (pywinauto, pyobjc, AT-SPI)
- Tier D: Mouse / Keyboard (PyAutoGUI — last resort only)
"""

from dataclasses import dataclass
from enum import Enum


class ExecutionTier(Enum):
    """Action execution tiers, ordered by preference.

    Always use the highest tier available. Tier D (mouse/keyboard)
    requires explicit justification in the skill manifest.
    """

    NATIVE_API = "native_api"
    APP_API = "app_api"
    UI = "ui"
    KEYBOARD = "keyboard"


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

    async def execute(self, skill_name: str, action: str, params: dict[str, str]) -> ActionResult:
        """Execute an action, trying execution tiers in priority order.

        Args:
            skill_name: Name of the skill requesting execution.
            action: The specific action to perform.
            params: Parameters for the action.

        Returns:
            ActionResult with success status and optional output/error.
        """
        if action in DANGEROUS_ACTIONS:
            confirmed = await self._require_confirmation(action, str(params))
            if not confirmed:
                return ActionResult(success=False, error="User cancelled dangerous action")

        # Placeholder — will dispatch to skill's execution tiers
        return ActionResult(success=False, error="Not implemented")

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
