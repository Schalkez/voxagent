"""Abstract system automation interface for cross-platform support.

Implementations:
- WindowsAutomation: pywinauto + win32gui
- MacOSAutomation: pyobjc + Accessibility API
- LinuxAutomation: AT-SPI (atspi2)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class WindowInfo:
    """Information about a desktop window.

    Attributes:
        title: Window title bar text.
        process_name: Name of the owning process.
        pid: Process identifier.
        bounds: Window geometry as (x, y, width, height).
    """

    title: str
    process_name: str
    pid: int
    bounds: tuple[int, int, int, int]


@dataclass(frozen=True)
class UIElement:
    """A UI element from the accessibility tree.

    Attributes:
        role: Semantic role (button, textfield, label, etc.).
        name: Accessible name.
        value: Current value, if applicable.
        bounds: Element geometry as (x, y, width, height).
    """

    role: str
    name: str
    value: str | None = None
    bounds: tuple[int, int, int, int] | None = None


@dataclass(frozen=True)
class ProcessInfo:
    """Information about a running process.

    Attributes:
        name: Process name.
        pid: Process identifier.
        memory_mb: Memory usage in megabytes.
    """

    name: str
    pid: int
    memory_mb: float


@dataclass(frozen=True)
class Notification:
    """A desktop notification.

    Attributes:
        app: Application that sent the notification.
        title: Notification title.
        body: Notification body text.
        timestamp: When the notification was received.
    """

    app: str
    title: str
    body: str
    timestamp: str


class SystemAutomation(ABC):
    """Cross-platform system automation interface.

    Provides a unified API for interacting with the operating system's
    window management, accessibility tree, and system controls.
    Each OS has its own concrete implementation.
    """

    @abstractmethod
    def get_active_window(self) -> WindowInfo:
        """Get the currently focused window."""

    @abstractmethod
    def find_element(self, role: str, name: str) -> UIElement | None:
        """Find a UI element in the accessibility tree."""

    @abstractmethod
    def get_running_processes(self) -> list[ProcessInfo]:
        """List all running processes with memory usage."""

    @abstractmethod
    def read_notifications(self) -> list[Notification]:
        """Read recent desktop notifications."""

    @abstractmethod
    def set_volume(self, level: int) -> None:
        """Set system volume (0-100)."""

    @abstractmethod
    def get_volume(self) -> int:
        """Get current system volume (0-100)."""
