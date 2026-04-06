"""OCR engine with PaddleOCR primary and Tesseract fallback.

Provides text extraction from screen captures for the Eyes module.
All OCR operations run in a thread pool to avoid blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger("voxagent.core.ocr")


class OCREngine:
    """PaddleOCR with Tesseract fallback.

    Attempts PaddleOCR first for best Vietnamese support,
    falls back to pytesseract, and returns empty string
    if neither is available.
    """

    def __init__(self) -> None:
        """Initialize the OCR engine with lazy-loaded backends."""
        self._paddle_ocr: object | None = None
        self._paddle_available: bool | None = None
        self._tesseract_available: bool | None = None

    def _init_paddle(self) -> bool:
        """Lazily initialize PaddleOCR backend.

        Returns:
            True if PaddleOCR is available and initialized.
        """
        if self._paddle_available is not None:
            return self._paddle_available

        try:
            from paddleocr import PaddleOCR  # type: ignore[import-untyped]

            self._paddle_ocr = PaddleOCR(use_angle_cls=True, lang="vi", show_log=False)
            self._paddle_available = True
            logger.info("PaddleOCR initialized successfully")
        except ImportError:
            self._paddle_available = False
            logger.debug("PaddleOCR not installed — will try Tesseract")

        return self._paddle_available

    def _init_tesseract(self) -> bool:
        """Check if Tesseract is available.

        Returns:
            True if pytesseract is importable.
        """
        if self._tesseract_available is not None:
            return self._tesseract_available

        try:
            import pytesseract  # type: ignore[import-untyped]  # noqa: F401

            self._tesseract_available = True
            logger.info("Tesseract OCR available as fallback")
        except ImportError:
            self._tesseract_available = False
            logger.debug("pytesseract not installed — OCR unavailable")

        return self._tesseract_available

    async def extract_text(self, image: bytes, language: str = "vi") -> str:
        """Extract text from an image using the best available OCR engine.

        Tries PaddleOCR first, then Tesseract, then returns empty string.

        Args:
            image: Image data as PNG/JPEG bytes.
            language: Language code for OCR (default: 'vi').

        Returns:
            Extracted text from the image, or empty string on failure.
        """
        return await asyncio.to_thread(self._extract_sync, image, language)

    def _extract_sync(self, image: bytes, language: str) -> str:
        """Synchronous text extraction dispatcher.

        Args:
            image: Image data as PNG/JPEG bytes.
            language: Language code for OCR.

        Returns:
            Extracted text string.
        """
        if self._init_paddle():
            return self._extract_with_paddle(image)

        if self._init_tesseract():
            return self._extract_with_tesseract(image, language)

        logger.warning("No OCR engine available — returning empty string")
        return ""

    def _extract_with_paddle(self, image: bytes) -> str:
        """Extract text using PaddleOCR.

        Args:
            image: Image data as bytes.

        Returns:
            Extracted text joined by newlines.
        """
        try:
            import io

            import numpy as np
            from PIL import Image

            img = Image.open(io.BytesIO(image))
            img_array = np.array(img)

            result = self._paddle_ocr.ocr(img_array, cls=True)  # type: ignore[union-attr]

            lines: list[str] = []
            for page in result:
                if page is None:
                    continue
                for line in page:
                    text = line[1][0] if isinstance(line[1], (list, tuple)) else str(line[1])
                    lines.append(text)

            return "\n".join(lines)
        except (OSError, ValueError, TypeError) as e:
            logger.warning("PaddleOCR extraction failed: %s", e)
            return ""

    def _extract_with_tesseract(self, image: bytes, language: str) -> str:
        """Extract text using Tesseract OCR.

        Args:
            image: Image data as bytes.
            language: Tesseract language code.

        Returns:
            Extracted text.
        """
        try:
            import io

            import pytesseract  # type: ignore[import-untyped]
            from PIL import Image

            lang_map = {"vi": "vie", "en": "eng", "ja": "jpn", "ko": "kor", "zh": "chi_sim"}
            tess_lang = lang_map.get(language, language)

            img = Image.open(io.BytesIO(image))
            text: str = pytesseract.image_to_string(img, lang=tess_lang)
            return text.strip()
        except (OSError, ValueError, TypeError) as e:
            logger.warning("Tesseract extraction failed: %s", e)
            return ""

    async def health_check(self) -> bool:
        """Check if at least one OCR backend is available.

        Returns:
            True if PaddleOCR or Tesseract is available.
        """
        return await asyncio.to_thread(self._health_check_sync)

    def _health_check_sync(self) -> bool:
        """Synchronous health check.

        Returns:
            True if any OCR engine is available.
        """
        return self._init_paddle() or self._init_tesseract()
