"""Windows-specific system automation implementation.

Uses ctypes, win32gui (via ctypes), and psutil for real system interaction.
Falls back gracefully when optional dependencies aren't available.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging

from system.base import (
    Notification,
    ProcessInfo,
    SystemAutomation,
    UIElement,
    WindowInfo,
)

logger = logging.getLogger("voxagent.system.windows")


class WindowsAutomation(SystemAutomation):
    """Implementation of SystemAutomation for Windows OS."""

    def get_active_window(self) -> WindowInfo:
        """Get the currently focused window using Win32 API."""
        try:
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            hwnd = user32.GetForegroundWindow()

            # Get window title
            length = user32.GetWindowTextLengthW(hwnd)
            title_buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title_buffer, length + 1)
            title = title_buffer.value

            # Get process ID
            pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            # Get process name
            process_name = _get_process_name(pid.value)

            # Get window bounds
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            bounds = (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)

            return WindowInfo(
                title=title,
                process_name=process_name,
                pid=pid.value,
                bounds=bounds,
            )
        except Exception:
            logger.exception("Failed to get active window")
            return WindowInfo(
                title="Unknown",
                process_name="unknown",
                pid=0,
                bounds=(0, 0, 0, 0),
            )

    def find_element(self, role: str, name: str) -> UIElement | None:
        """Find a UI element in the accessibility tree.

        Basic implementation — full UI automation requires pywinauto.
        """
        logger.debug("find_element not fully implemented (role=%s, name=%s)", role, name)
        return None

    def get_running_processes(self) -> list[ProcessInfo]:
        """List all running processes with memory usage via psutil."""
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
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return processes

    def read_notifications(self) -> list[Notification]:
        """Read recent desktop notifications.

        Windows notification center access is complex and requires
        UWP APIs. Returns empty list for now.
        """
        return []

    def set_volume(self, level: int) -> None:
        """Set system volume (0-100) using media key simulation.

        For precise volume control, pycaw would be needed.
        This implementation uses volume up/down key presses as approximation.
        """
        try:
            current = self.get_volume()
            user32 = ctypes.windll.user32  # type: ignore[attr-defined]

            steps = abs(level - current) // 2
            vk_code = 0xAF if level > current else 0xAE  # VK_VOLUME_UP or DOWN

            for _ in range(steps):
                user32.keybd_event(vk_code, 0, 0x0001, 0)
                user32.keybd_event(vk_code, 0, 0x0003, 0)

            logger.info("Volume set to ~%d%% (%d steps)", level, steps)
        except Exception:
            logger.exception("Failed to set volume to %d", level)

    def get_volume(self) -> int:
        """Get current system volume (0-100).

        Approximate — returns 50 unless pycaw is available.
        """
        return 50


def _get_process_name(pid: int) -> str:
    """Get process name from PID using psutil.

    Args:
        pid: Process identifier.

    Returns:
        Process name or 'unknown'.
    """
    try:
        import psutil

        proc = psutil.Process(pid)
        return proc.name()
    except Exception:
        return "unknown"
