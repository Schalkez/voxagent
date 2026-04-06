"""macOS system automation implementation (stub).

Uses osascript for basic window management and psutil for processes.
Full implementation requires pyobjc and Accessibility API permissions.
"""

from __future__ import annotations

import logging
import subprocess

from system.base import (
    Notification,
    ProcessInfo,
    SystemAutomation,
    UIElement,
    WindowInfo,
)

logger = logging.getLogger("voxagent.system.macos")


class MacOSAutomation(SystemAutomation):
    """Stub implementation of SystemAutomation for macOS."""

    def get_active_window(self) -> WindowInfo:
        """Get the currently focused window using osascript."""
        try:
            result = subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "System Events" to get name of first process whose frontmost is true',
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            app_name = result.stdout.strip() or "Unknown"
            return WindowInfo(title=app_name, process_name=app_name, pid=0, bounds=(0, 0, 0, 0))
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
            logger.warning("Failed to get active window via osascript")
            return WindowInfo(title="Unknown", process_name="unknown", pid=0, bounds=(0, 0, 0, 0))

    def find_element(self, role: str, name: str) -> UIElement | None:
        """Find a UI element — requires pyobjc (not yet implemented)."""
        logger.debug("find_element not implemented on macOS (role=%s, name=%s)", role, name)
        return None

    def get_running_processes(self) -> list[ProcessInfo]:
        """List running processes via psutil."""
        try:
            import psutil
        except ImportError:
            logger.warning("psutil not installed — cannot list processes")
            return []

        processes: list[ProcessInfo] = []
        for proc in psutil.process_iter(["name", "pid", "memory_info"]):
            try:
                info = proc.info
                mem = info.get("memory_info")
                mem_mb = mem.rss / (1024 * 1024) if mem else 0.0
                processes.append(
                    ProcessInfo(
                        name=info["name"] or "unknown",
                        pid=info["pid"],
                        memory_mb=round(mem_mb, 1),
                    )
                )
            except (AttributeError, OSError):
                continue

        return processes

    def read_notifications(self) -> list[Notification]:
        """Read notifications — not implemented on macOS."""
        return []

    def set_volume(self, level: int) -> None:
        """Set system volume using osascript."""
        try:
            subprocess.run(
                ["osascript", "-e", f"set volume output volume {level}"],
                check=False,
                timeout=5,
                capture_output=True,
            )
        except (subprocess.TimeoutExpired, OSError):
            logger.warning("Failed to set volume on macOS")

    def get_volume(self) -> int:
        """Get system volume using osascript."""
        try:
            result = subprocess.run(
                ["osascript", "-e", "output volume of (get volume settings)"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            return int(result.stdout.strip())
        except (subprocess.TimeoutExpired, OSError, ValueError):
            return 50
