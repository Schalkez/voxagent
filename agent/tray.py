"""VoxAgent system tray application.

Provides a system tray icon with menu for controlling the agent
and launching the dashboard in a browser.
"""

from __future__ import annotations

import logging
import threading
import webbrowser
from collections.abc import Callable

logger = logging.getLogger("voxagent.tray")

_DASHBOARD_URL = "http://localhost:8642"

# Colors for tray icon states
_COLOR_LISTENING = (76, 175, 80)  # Green
_COLOR_STOPPED = (158, 158, 158)  # Gray
_COLOR_ERROR = (244, 67, 54)  # Red


def _create_icon_image(color: tuple[int, int, int], size: int = 64) -> object:
    """Create a simple colored circle icon.

    Args:
        color: RGB tuple for the icon color.
        size: Icon size in pixels.

    Returns:
        PIL.Image object.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.warning("Pillow not installed — tray icons disabled. Run: pip install Pillow")
        return None

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = 4
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(*color, 255),
    )
    return image


class TrayApp:
    """System tray application for VoxAgent.

    Provides start/stop controls and dashboard access from the system tray.
    """

    def __init__(self) -> None:
        """Initialize the tray application."""
        self._listening = False
        self._icon: object = None
        self._on_start_callback: Callable[[], None] | None = None
        self._on_stop_callback: Callable[[], None] | None = None

    def set_callbacks(
        self,
        on_start: Callable[[], None] | None = None,
        on_stop: Callable[[], None] | None = None,
    ) -> None:
        """Set callbacks for tray menu actions.

        Args:
            on_start: Called when user clicks 'Start Listening'.
            on_stop: Called when user clicks 'Stop Listening'.
        """
        self._on_start_callback = on_start
        self._on_stop_callback = on_stop

    def run(self) -> None:
        """Start the system tray icon (blocking).

        Should be called from a separate thread.
        """
        try:
            import pystray  # type: ignore[import-untyped]
        except ImportError:
            logger.warning("pystray not installed — tray disabled")
            return

        image = _create_icon_image(_COLOR_STOPPED)

        menu = pystray.Menu(
            pystray.MenuItem(
                "Start Listening",
                self._on_start,
                visible=lambda _: not self._listening,
            ),
            pystray.MenuItem(
                "Stop Listening",
                self._on_stop,
                visible=lambda _: self._listening,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Dashboard", self._on_open_dashboard),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._on_quit),
        )

        self._icon = pystray.Icon("VoxAgent", image, "VoxAgent", menu)
        logger.info("System tray started")
        self._icon.run()

    def run_in_thread(self) -> threading.Thread:
        """Start the system tray in a background thread.

        Returns:
            The thread running the tray icon.
        """
        thread = threading.Thread(target=self.run, daemon=True, name="voxagent-tray")
        thread.start()
        return thread

    def update_status(self, listening: bool) -> None:
        """Update the tray icon to reflect current status.

        Args:
            listening: True if the agent is listening, False if stopped.
        """
        self._listening = listening
        if self._icon is not None:
            color = _COLOR_LISTENING if listening else _COLOR_STOPPED
            self._icon.icon = _create_icon_image(color)
            self._icon.update_menu()

    def _on_start(self, _icon: object, _item: object) -> None:
        """Handle 'Start Listening' menu click."""
        self._listening = True
        self.update_status(listening=True)
        if self._on_start_callback:
            self._on_start_callback()

    def _on_stop(self, _icon: object, _item: object) -> None:
        """Handle 'Stop Listening' menu click."""
        self._listening = False
        self.update_status(listening=False)
        if self._on_stop_callback:
            self._on_stop_callback()

    def _on_open_dashboard(self, _icon: object, _item: object) -> None:
        """Handle 'Open Dashboard' menu click."""
        webbrowser.open(_DASHBOARD_URL)

    def _on_quit(self, _icon: object, _item: object) -> None:
        """Handle 'Quit' menu click."""
        self._listening = False
        if self._icon is not None:
            self._icon.stop()
        logger.info("System tray stopped by user")
