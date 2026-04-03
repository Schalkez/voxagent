"""EYES module: Layered screen understanding.

Layer 1: Native UI Automation (free, instant) — widget tree
Layer 2: OCR (free, < 500ms) — PaddleOCR/Tesseract
Layer 3: Vision LLM (complex cases only) — GPT-4o/Claude/Qwen-VL
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class WindowInfo:
    """Information about a desktop window.

    Attributes:
        title: Window title text.
        process_name: Name of the process owning the window.
        pid: Process ID.
        bounds: Window position and size as (x, y, width, height).
    """

    title: str
    process_name: str
    pid: int
    bounds: tuple[int, int, int, int]


@dataclass(frozen=True)
class UIElement:
    """A UI element found in the accessibility tree.

    Attributes:
        role: Element role (button, textfield, label, etc.).
        name: Accessible name of the element.
        value: Current value, if applicable.
        bounds: Element position and size as (x, y, width, height).
    """

    role: str
    name: str
    value: str | None = None
    bounds: tuple[int, int, int, int] | None = None


class Eyes:
    """Layered screen understanding: UI tree → OCR → Vision LLM.

    Attempts the cheapest layer first. Vision LLM is only used for
    complex visual understanding tasks and always crops the target
    region instead of sending the full screen.
    """

    async def get_active_window(self) -> WindowInfo:
        """Get information about the currently focused window.

        Returns:
            WindowInfo with title, process name, PID, and bounds.
        """
        # Placeholder — will use platform-specific automation
        return WindowInfo(title="", process_name="", pid=0, bounds=(0, 0, 0, 0))

    async def find_element(self, role: str, name: str) -> UIElement | None:
        """Search the UI accessibility tree for a specific element.

        Args:
            role: Element role to search for (e.g., 'button', 'textfield').
            name: Accessible name to match.

        Returns:
            UIElement if found, None otherwise.
        """
        return None

    async def read_screen_text(self, region: tuple[int, int, int, int] | None = None) -> str:
        """Read text from the screen using OCR.

        Uses targeted cropping to only process the relevant region,
        with 5-second caching to avoid redundant OCR calls.

        Args:
            region: Optional (x, y, width, height) to crop. Full screen if None.

        Returns:
            Extracted text from the screen region.
        """
        return ""
