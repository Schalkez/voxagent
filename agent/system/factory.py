"""Factory for providing correct OS-specific automation implementation."""

import logging
import platform

from system.base import SystemAutomation

logger = logging.getLogger("voxagent.system")


def _get_system_automation() -> SystemAutomation:
    """Get the appropriate SystemAutomation implementation for the current OS."""
    os_name = platform.system().lower()

    if os_name == "windows":
        from system.windows import WindowsAutomation
        return WindowsAutomation()
    if os_name == "darwin":
        raise NotImplementedError("MacOS automation is not supported yet.")
    if os_name == "linux":
        raise NotImplementedError("Linux automation is not supported yet.")

    raise OSError(f"Unsupported operating system: {os_name}")


# Export a global singleton instance
automation = _get_system_automation()
