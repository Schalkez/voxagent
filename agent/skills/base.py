"""Base skill class and shared types for all VoxAgent skills.

All skills must inherit from BaseSkill and declare their execution
tiers following the mandatory priority order (A→D).
"""

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


@dataclass(frozen=True)
class SkillResult:
    """Result returned by a skill execution.

    Attributes:
        success: Whether the skill completed successfully.
        tts_response: Text for the MOUTH module to speak.
        data: Optional structured data from the skill.
        error: Error message if the skill failed.
        cancelled: True if the user cancelled a dangerous action.
        tier_used: Which execution tier was used.
    """

    success: bool
    tts_response: str = ""
    data: dict[str, object] = field(default_factory=dict)
    error: str | None = None
    cancelled: bool = False
    tier_used: ExecutionTier | None = None


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
