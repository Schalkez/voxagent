"""macOS system automation using osascript + System Events.

Uses osascript for window management and UI element discovery via
the Accessibility API exposed through System Events. Requires
"Accessibility" permission for the terminal in System Settings.
"""

from __future__ import annotations

import json
import logging
import subprocess

from system.base import (
    Notification,
    ProcessInfo,
    SystemAutomation,
    UIElement,
    WindowInfo,
)

OSASCRIPT_TIMEOUT_SECONDS = 5

logger = logging.getLogger("voxagent.system.macos")


def _run_osascript(script: str) -> subprocess.CompletedProcess[str]:
    """Execute an AppleScript snippet via osascript.

    Args:
        script: The AppleScript source to run.

    Returns:
        CompletedProcess with stdout/stderr.

    Raises:
        subprocess.TimeoutExpired: If the script exceeds the timeout.
        FileNotFoundError: If osascript is not found.
        OSError: If the subprocess cannot be started.
    """
    return subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
        timeout=OSASCRIPT_TIMEOUT_SECONDS,
    )


def _build_find_element_script(role: str, name: str) -> str:
    """Build an AppleScript that searches the frontmost app's UI tree.

    The script walks the accessibility tree of the frontmost application
    via System Events, looking for a UI element whose role matches
    ``role`` and whose name contains ``name``. When found it returns
    a JSON payload with role, name, and position/size.

    Args:
        role: Accessibility role to match (e.g. "button", "text field").
        name: Accessible name (substring match, case-insensitive).

    Returns:
        An AppleScript source string.
    """
    safe_role = role.replace('"', '\\"')
    safe_name = name.replace('"', '\\"')

    return f"""
        use scripting additions
        use framework "Foundation"

        tell application "System Events"
            set frontApp to first process whose frontmost is true
            set appName to name of frontApp

            tell frontApp
                set matchedRole to "{safe_role}"
                set matchedName to "{safe_name}"

                try
                    set uiElements to entire contents of window 1
                on error
                    return "NOT_FOUND"
                end try

                repeat with elem in uiElements
                    try
                        set elemRole to role of elem
                        set elemName to name of elem

                        if elemName is missing value then set elemName to ""

                        set lcRole to do shell script "echo " & quoted form of elemRole & " | tr '[:upper:]' '[:lower:]'"
                        set lcMatch to do shell script "echo " & quoted form of matchedRole & " | tr '[:upper:]' '[:lower:]'"
                        set lcName to do shell script "echo " & quoted form of elemName & " | tr '[:upper:]' '[:lower:]'"
                        set lcMatchName to do shell script "echo " & quoted form of matchedName & " | tr '[:upper:]' '[:lower:]'"

                        if lcRole contains lcMatch and lcName contains lcMatchName then
                            try
                                set pos to position of elem
                                set sz to size of elem
                                set posX to item 1 of pos
                                set posY to item 2 of pos
                                set szW to item 1 of sz
                                set szH to item 2 of sz
                            on error
                                set posX to 0
                                set posY to 0
                                set szW to 0
                                set szH to 0
                            end try

                            set jsonStr to "{{\\"role\\":\\"" & elemRole & "\\",\\"name\\":\\"" & elemName & "\\",\\"x\\":" & posX & ",\\"y\\":" & posY & ",\\"w\\":" & szW & ",\\"h\\":" & szH & "}}"
                            return jsonStr
                        end if
                    end try
                end repeat
            end tell
        end tell
        return "NOT_FOUND"
    """


def _parse_element_json(raw: str) -> UIElement | None:
    """Parse the JSON payload returned by the AppleScript into a UIElement.

    Args:
        raw: Raw stdout from osascript (JSON string or "NOT_FOUND").

    Returns:
        A UIElement on success, None when no match or on parse failure.
    """
    stripped = raw.strip()
    if not stripped or stripped == "NOT_FOUND":
        return None

    try:
        data = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse AppleScript JSON: %s", stripped)
        return None

    return UIElement(
        role=data.get("role", "unknown"),
        name=data.get("name", ""),
        bounds=(
            int(data.get("x", 0)),
            int(data.get("y", 0)),
            int(data.get("w", 0)),
            int(data.get("h", 0)),
        ),
    )


class MacOSAutomation(SystemAutomation):
    """macOS implementation using osascript + System Events."""

    def get_active_window(self) -> WindowInfo:
        """Get the currently focused window using osascript."""
        try:
            result = _run_osascript(
                'tell application "System Events" to get name '
                "of first process whose frontmost is true"
            )
            app_name = result.stdout.strip() or "Unknown"
            return WindowInfo(title=app_name, process_name=app_name, pid=0, bounds=(0, 0, 0, 0))
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
            logger.warning("Failed to get active window via osascript")
            return WindowInfo(title="Unknown", process_name="unknown", pid=0, bounds=(0, 0, 0, 0))

    def find_element(self, role: str, name: str) -> UIElement | None:
        """Find a UI element in the frontmost app via System Events.

        Walks the accessibility tree of the frontmost application's first
        window, searching for an element whose role contains ``role`` and
        whose name contains ``name`` (both case-insensitive).

        Args:
            role: Accessibility role to match (e.g. "button").
            name: Accessible name substring to match.

        Returns:
            A UIElement with role, name, and bounds on match; None otherwise.
        """
        try:
            script = _build_find_element_script(role, name)
            result = _run_osascript(script)
            return _parse_element_json(result.stdout)
        except subprocess.TimeoutExpired:
            logger.warning("find_element timed out (role=%s, name=%s)", role, name)
            return None
        except FileNotFoundError:
            logger.error("osascript not found — is this macOS?")
            return None
        except OSError:
            logger.warning("find_element OSError (role=%s, name=%s)", role, name)
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
