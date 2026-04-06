"""Linux system automation implementation (stub).

Uses xdotool for basic window management and psutil for processes.
Full implementation requires AT-SPI (atspi2) for accessibility.
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

logger = logging.getLogger("voxagent.system.linux")


class LinuxAutomation(SystemAutomation):
    """Stub implementation of SystemAutomation for Linux."""

    def get_active_window(self) -> WindowInfo:
        """Get the currently focused window using xdotool."""
        try:
            subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            ).stdout.strip()

            name_result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            title = name_result.stdout.strip() or "Unknown"

            pid_result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowpid"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            pid = int(pid_result.stdout.strip()) if pid_result.stdout.strip() else 0

            return WindowInfo(title=title, process_name=title, pid=pid, bounds=(0, 0, 0, 0))
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError, FileNotFoundError, ValueError):
            logger.warning("Failed to get active window via xdotool")
            return WindowInfo(title="Unknown", process_name="unknown", pid=0, bounds=(0, 0, 0, 0))

    def find_element(self, role: str, name: str) -> UIElement | None:
        """Find a UI element — requires AT-SPI (not yet implemented)."""
        logger.debug("find_element not implemented on Linux (role=%s, name=%s)", role, name)
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
        """Read notifications — not implemented on Linux."""
        return []

    def set_volume(self, level: int) -> None:
        """Set system volume using pactl."""
        try:
            subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"],
                check=False,
                timeout=5,
                capture_output=True,
            )
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
            logger.warning("Failed to set volume on Linux")

    def get_volume(self) -> int:
        """Get system volume — approximate via pactl."""
        try:
            result = subprocess.run(
                ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            # Parse "Volume: front-left: 65536 / 100% / 0.00 dB"
            for part in result.stdout.split("/"):
                part = part.strip()
                if part.endswith("%"):
                    return int(part[:-1])
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError, ValueError):
            pass
        return 50
