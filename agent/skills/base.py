"""Base skill class and shared types for all VoxAgent skills.

All skills must inherit from BaseSkill and declare their execution
tiers following the mandatory priority order (A→D).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar


class ExecutionTier(Enum):
    """Execution strategy tiers, ordered by preference.

    Skills MUST declare which tiers they support. The HANDS module
    will try them in order from cheapest to most expensive.

    NATIVE_API: subprocess, ctypes, win32api, osascript (Tier A)
    SHELL: Shell commands via subprocess (Tier A variant)
    APP_API: Playwright CDP, REST APIs, native app APIs (Tier B)
    UI: pywinauto, pyobjc Accessibility, AT-SPI (Tier C)
    KEYBOARD: PyAutoGUI mouse/keyboard simulation (Tier D — last resort)
    """

    NATIVE_API = "native_api"
    SHELL = "shell"
    APP_API = "app_api"
    UI = "ui"
    KEYBOARD = "keyboard"


# -- Standard Skill Error Codes --
# Skills may define custom codes; these are the shared conventions.
SKILL_ERR_UNSUPPORTED_ACTION = "unsupported_action"
SKILL_ERR_PERMISSION_DENIED = "permission_denied"
SKILL_ERR_NOT_FOUND = "not_found"
SKILL_ERR_TIMEOUT = "timeout"
SKILL_ERR_COMMAND_BLOCKED = "command_blocked"
SKILL_ERR_INVALID_PARAMS = "invalid_params"
SKILL_ERR_PLATFORM_UNSUPPORTED = "platform_unsupported"
SKILL_ERR_PROVIDER_UNAVAILABLE = "provider_unavailable"
SKILL_ERR_CANCELLED = "cancelled"


@dataclass(frozen=True)
class SkillResult:
    """Result returned by a skill execution.

    Attributes:
        success: Whether the skill completed successfully.
        tts_response: Text for the MOUTH module to speak.
        data: Optional structured data from the skill.
        error: Error message if the skill failed (technical, for logs).
        error_code: Machine-readable error code (e.g., 'command_blocked', 'timeout').
        error_severity: Severity level from ErrorSeverity enum.
        retryable: Whether the failed operation can be retried.
        cancelled: True if the user cancelled a dangerous action.
        tier_used: Which execution tier was used.
    """

    success: bool
    tts_response: str = ""
    data: dict[str, object] = field(default_factory=dict)
    error: str | None = None
    error_code: str = ""
    error_severity: str = "warning"
    retryable: bool = False
    cancelled: bool = False
    tier_used: ExecutionTier | None = None

    @staticmethod
    def ok(
        tts_response: str = "",
        data: dict[str, object] | None = None,
        tier_used: ExecutionTier | None = None,
    ) -> SkillResult:
        """Create a successful SkillResult.

        Args:
            tts_response: Text for TTS to speak.
            data: Optional structured output data.
            tier_used: Which execution tier succeeded.

        Returns:
            A SkillResult with success=True.
        """
        return SkillResult(
            success=True,
            tts_response=tts_response,
            data=data or {},
            tier_used=tier_used,
        )

    @staticmethod
    def fail(
        error: str,
        *,
        tts_response: str = "",
        error_code: str = "",
        error_severity: str = "warning",
        retryable: bool = False,
        data: dict[str, object] | None = None,
        tier_used: ExecutionTier | None = None,
    ) -> SkillResult:
        """Create a failed SkillResult with structured error info.

        Args:
            error: Technical error message for logs.
            tts_response: User-facing Vietnamese message for TTS.
            error_code: Machine-readable error code.
            error_severity: Severity level ('info', 'warning', 'critical').
            retryable: Whether the operation can be retried.
            data: Optional structured data (e.g., partial results).
            tier_used: Which execution tier was attempted.

        Returns:
            A SkillResult with success=False and typed error fields.
        """
        return SkillResult(
            success=False,
            tts_response=tts_response,
            data=data or {},
            error=error,
            error_code=error_code,
            error_severity=error_severity,
            retryable=retryable,
            tier_used=tier_used,
        )


@dataclass(frozen=True)
class SkillIntent:
    """Parsed intent passed to a skill for execution.

    Attributes:
        skill_name: Name of the target skill.
        action: Specific action to perform.
        params: Key-value parameters extracted from the command.
        raw_text: Original transcribed text from EARS.
    """

    skill_name: str
    action: str
    params: dict[str, str]
    raw_text: str


class BaseSkill(ABC):
    """Base class for all VoxAgent skills.

    Subclasses must define class attributes and implement
    can_handle() and execute() methods.

    Example::

        class MediaControlSkill(BaseSkill):
            name = "media_control"
            description = "Control media playback"
            keywords = ["skip", "pause", "next", "stop"]
            execution_tiers = [ExecutionTier.NATIVE_API, ExecutionTier.KEYBOARD]

            async def can_handle(self, intent: SkillIntent) -> bool:
                return intent.skill_name == self.name

            async def execute(self, intent: SkillIntent) -> SkillResult:
                # Implementation here
                ...
    """

    name: str = ""
    description: str = ""
    keywords: ClassVar[list[str]] = []
    execution_tiers: ClassVar[list[ExecutionTier]] = []
    permissions: ClassVar[list[str]] = []

    @abstractmethod
    async def can_handle(self, intent: SkillIntent) -> bool:
        """Check if this skill can handle the given intent.

        Args:
            intent: The parsed user intent.

        Returns:
            True if this skill should handle the intent.
        """

    @abstractmethod
    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Execute the skill action.

        Args:
            intent: The parsed user intent with action and parameters.

        Returns:
            SkillResult with success status, TTS response, and data.
        """
