"""Windows-specific system automation implementation."""

from system.base import (
    Notification,
    ProcessInfo,
    SystemAutomation,
    UIElement,
    WindowInfo,
)


class WindowsAutomation(SystemAutomation):
    """Implementation of SystemAutomation for Windows OS using pywinauto."""

    def get_active_window(self) -> WindowInfo:
        return WindowInfo(
            title="Mock Windows Window",
            process_name="mock.exe",
            pid=1234,
            bounds=(0, 0, 1920, 1080)
        )

    def find_element(self, role: str, name: str) -> UIElement | None:
        return None

    def get_running_processes(self) -> list[ProcessInfo]:
        return []

    def read_notifications(self) -> list[Notification]:
        return []

    def set_volume(self, level: int) -> None:
        # TODO: Implement with pycaw or ctypes
        pass

    def get_volume(self) -> int:
        return 50
