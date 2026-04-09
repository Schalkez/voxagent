"""EYES module: Layered screen understanding.

Layer 1: Native UI Automation (free, instant) — widget tree via SystemAutomation
Layer 2: OCR (free, < 500ms) — PaddleOCR/Tesseract via core.ocr
Layer 3: Vision LLM (complex cases only) — GPT-4o/Claude/Gemini via VisionProvider
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
from dataclasses import dataclass, field

from core.errors import ProviderError

logger = logging.getLogger("voxagent.eyes")

# ── Constants ──

OCR_CACHE_TTL_SECONDS = 5.0


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


@dataclass
class _OCRCacheEntry:
    """Cached OCR result with timestamp.

    Attributes:
        text: Cached OCR text.
        timestamp: When the cache entry was created.
        region: The screen region used for this result.
    """

    text: str
    timestamp: float
    region: tuple[int, int, int, int] | None


@dataclass
class Eyes:
    """Layered screen understanding: UI tree -> OCR -> Vision LLM.

    Attempts the cheapest layer first. Vision LLM is only used for
    complex visual understanding tasks and always crops the target
    region instead of sending the full screen.
    """

    _ocr_cache: _OCRCacheEntry | None = field(default=None, init=False, repr=False)

    async def get_active_window(self) -> WindowInfo:
        """Get information about the currently focused window.

        Uses Layer 1 (native SystemAutomation) for instant results.

        Returns:
            WindowInfo with title, process name, PID, and bounds.
        """
        try:
            from system.factory import get_system_automation

            automation = get_system_automation()
            win = await asyncio.to_thread(automation.get_active_window)
            return WindowInfo(
                title=win.title,
                process_name=win.process_name,
                pid=win.pid,
                bounds=win.bounds,
            )
        except (NotImplementedError, OSError, RuntimeError) as e:
            logger.warning("Failed to get active window: %s", e)
            return WindowInfo(title="", process_name="", pid=0, bounds=(0, 0, 0, 0))

    async def find_element(self, role: str, name: str) -> UIElement | None:
        """Search the UI accessibility tree for a specific element.

        Uses Layer 1 (native SystemAutomation).

        Args:
            role: Element role to search for (e.g., 'button', 'textfield').
            name: Accessible name to match.

        Returns:
            UIElement if found, None otherwise.
        """
        try:
            from system.factory import get_system_automation

            automation = get_system_automation()
            elem = await asyncio.to_thread(automation.find_element, role, name)
            if elem is None:
                return None
            return UIElement(
                role=elem.role,
                name=elem.name,
                value=elem.value,
                bounds=elem.bounds,
            )
        except (NotImplementedError, OSError, RuntimeError) as e:
            logger.warning("Failed to find element: %s", e)
            return None

    async def capture_screen(
        self, region: tuple[int, int, int, int] | None = None
    ) -> bytes:
        """Capture a screenshot of the screen or a specific region.

        Uses Pillow's ImageGrab for cross-platform screenshot capture.

        Args:
            region: Optional (x, y, width, height) to crop. Full screen if None.

        Returns:
            PNG image bytes of the captured screen region.
        """
        return await asyncio.to_thread(self._capture_sync, region)

    def _capture_sync(self, region: tuple[int, int, int, int] | None) -> bytes:
        """Synchronous screen capture using Pillow.

        Args:
            region: Optional (x, y, width, height) to crop.

        Returns:
            PNG image bytes.
        """
        try:
            from PIL import ImageGrab
        except ImportError:
            logger.warning("Pillow not installed — cannot capture screen")
            return b""

        try:
            if region is not None:
                x, y, w, h = region
                bbox = (x, y, x + w, y + h)
                screenshot = ImageGrab.grab(bbox=bbox)
            else:
                screenshot = ImageGrab.grab()

            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            return buffer.getvalue()
        except (OSError, ValueError) as e:
            logger.warning("Screen capture failed: %s", e)
            return b""

    async def read_screen_text(
        self, region: tuple[int, int, int, int] | None = None
    ) -> str:
        """Read text from the screen using OCR (Layer 2).

        Uses targeted cropping to only process the relevant region,
        with 5-second caching to avoid redundant OCR calls.

        Args:
            region: Optional (x, y, width, height) to crop. Full screen if None.

        Returns:
            Extracted text from the screen region.
        """
        cached = self._get_cached_ocr(region)
        if cached is not None:
            return cached

        image = await self.capture_screen(region)
        if not image:
            return ""

        from core.ocr import OCREngine

        engine = OCREngine()
        text = await engine.extract_text(image)

        self._ocr_cache = _OCRCacheEntry(
            text=text,
            timestamp=time.monotonic(),
            region=region,
        )

        return text

    async def analyze_screen(
        self,
        prompt: str,
        region: tuple[int, int, int, int] | None = None,
    ) -> str:
        """Analyze the screen using a Vision LLM (Layer 3).

        Captures a screenshot and sends it to the configured Vision
        provider with the given prompt. Always crops to the target
        region to minimize token usage.

        Args:
            prompt: Question or instruction about the screen content.
            region: Optional (x, y, width, height) to crop. Full screen if None.

        Returns:
            Text analysis result from the Vision LLM.
        """
        image = await self.capture_screen(region)
        if not image:
            return "Could not capture screen."

        try:
            from providers.registry import ProviderRegistry

            registry = ProviderRegistry()
            vision_providers = registry.list_registered().get("vision", [])

            if not vision_providers:
                return "No vision provider configured."

            provider = registry.get_vision(vision_providers[0])
            return await provider.analyze_image(image, prompt)
        except (ProviderError, KeyError, RuntimeError, ConnectionError) as e:
            logger.warning("Vision analysis failed: %s", e)
            return f"Vision analysis failed: {e}"

    def _get_cached_ocr(self, region: tuple[int, int, int, int] | None) -> str | None:
        """Return cached OCR text if still valid.

        Args:
            region: The region to check against the cache.

        Returns:
            Cached text if valid, None if cache miss or expired.
        """
        if self._ocr_cache is None:
            return None

        age = time.monotonic() - self._ocr_cache.timestamp
        if age > OCR_CACHE_TTL_SECONDS:
            return None

        if self._ocr_cache.region != region:
            return None

        return self._ocr_cache.text
