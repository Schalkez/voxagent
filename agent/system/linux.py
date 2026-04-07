"""Linux system automation using xdotool + wmctrl.

Uses xdotool for window management and UI element search as a
practical alternative to AT-SPI. Requires xdotool (and optionally
wmctrl) to be installed.
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

SUBPROCESS_TIMEOUT_SECONDS = 5

logger = logging.getLogger("voxagent.system.linux")


def _get_window_geometry(window_id: str) -> tuple[int, int, int, int]:
    """Retrieve window geometry (x, y, width, height) via xdotool.

    Args:
        window_id: The X11 window ID string.

    Returns:
        A (x, y, width, height) tuple. Falls back to (0, 0, 0, 0) on error.
    """
    try:
        result = subprocess.run(
            ["xdotool", "getwindowgeometry", "--shell", window_id],
            capture_output=True,
            text=True,
            check=False,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return (0, 0, 0, 0)

    values: dict[str, int] = {}
    for line in result.stdout.strip().splitlines():
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        try:
            values[key.strip()] = int(val.strip())
        except ValueError:
            continue

    return (
        values.get("X", 0),
        values.get("Y", 0),
        values.get("WIDTH", 0),
        values.get("HEIGHT", 0),
    )


def _get_window_name(window_id: str) -> str:
    """Retrieve window title for a given X11 window ID.

    Args:
        window_id: The X11 window ID string.

    Returns:
        The window name, or an empty string on failure.
    """
    try:
        result = subprocess.run(
            ["xdotool", "getwindowname", window_id],
            capture_output=True,
            text=True,
            check=False,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        return ""


def _get_window_pid(window_id: str) -> int:
    """Retrieve the PID owning a given X11 window.

    Args:
        window_id: The X11 window ID string.

    Returns:
        The PID, or 0 on failure.
    """
    try:
        result = subprocess.run(
            ["xdotool", "getwindowpid", window_id],
            capture_output=True,
            text=True,
            check=False,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
        return int(result.stdout.strip()) if result.stdout.strip() else 0
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError, ValueError):
        return 0


class LinuxAutomation(SystemAutomation):
    """Linux implementation using xdotool + wmctrl."""

    def get_active_window(self) -> WindowInfo:
        """Get the currently focused window using xdotool."""
        try:
            wid_result = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True,
                text=True,
                check=True,
                timeout=SUBPROCESS_TIMEOUT_SECONDS,
            )
            wid = wid_result.stdout.strip()
            title = _get_window_name(wid) or "Unknown"
            pid = _get_window_pid(wid)

            return WindowInfo(title=title, process_name=title, pid=pid, bounds=(0, 0, 0, 0))
        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            OSError,
            FileNotFoundError,
            ValueError,
        ):
            logger.warning("Failed to get active window via xdotool")
            return WindowInfo(title="Unknown", process_name="unknown", pid=0, bounds=(0, 0, 0, 0))

    def find_element(self, role: str, name: str) -> UIElement | None:
        """Find a UI element by searching windows with xdotool.

        Uses ``xdotool search --name`` to find X11 windows whose title
        contains ``name``. When a match is found, its geometry is read via
        ``xdotool getwindowgeometry``.

        This is a practical window-level alternative to full AT-SPI tree
        walking. The ``role`` parameter is stored on the returned element
        but matching is done on ``name`` only (xdotool operates at the
        window level, not at individual widget level).

        Args:
            role: Semantic role to label the result (e.g. "window").
            name: Window name substring to search for.

        Returns:
            A UIElement with role, name, and bounds on match; None otherwise.
        """
        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", name],
                capture_output=True,
                text=True,
                check=False,
                timeout=SUBPROCESS_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            logger.warning("find_element timed out (role=%s, name=%s)", role, name)
            return None
        except FileNotFoundError:
            logger.error("xdotool not found — install with: sudo apt install xdotool")
            return None
        except OSError:
            logger.warning("find_element OSError (role=%s, name=%s)", role, name)
            return None

        window_ids = result.stdout.strip().splitlines()
        if not window_ids:
            logger.debug("No windows matched name=%s", name)
            return None

        window_id = window_ids[0]
        window_name = _get_window_name(window_id) or name
        bounds = _get_window_geometry(window_id)

        return UIElement(
            role=role,
            name=window_name,
            bounds=bounds,
        )

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
