"""Factory for providing correct OS-specific automation implementation."""

from __future__ import annotations

import logging
import platform
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from system.base import SystemAutomation

logger = logging.getLogger("voxagent.system")

_automation: SystemAutomation | None = None


def get_system_automation() -> SystemAutomation:
    """Get the appropriate SystemAutomation implementation for the current OS.

    Uses lazy initialization to avoid crash-on-import on unsupported platforms.

    Returns:
        SystemAutomation instance for the current OS.

    Raises:
        NotImplementedError: If the current OS is not supported.
        OSError: If the OS cannot be determined.
    """
    global _automation
    if _automation is not None:
        return _automation

    os_name = platform.system().lower()

    if os_name == "windows":
        from system.windows import WindowsAutomation

        _automation = WindowsAutomation()
    elif os_name == "darwin":
        from system.macos import MacOSAutomation

        _automation = MacOSAutomation()
    elif os_name == "linux":
        from system.linux import LinuxAutomation

        _automation = LinuxAutomation()
    else:
        raise OSError(f"Unsupported operating system: {os_name}")

    return _automation
