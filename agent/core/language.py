"""Multi-language conversation support."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("voxagent.language")


@dataclass(frozen=True)
class LanguageInfo:
    """Configuration for a supported language.

    Attributes:
        code: ISO 639-1 language code.
        name: Human-readable name in native script.
        stt_code: Language code for STT providers.
        tts_voice: Default Edge TTS voice identifier.
    """

    code: str
    name: str
    stt_code: str
    tts_voice: str


SUPPORTED_LANGUAGES: dict[str, LanguageInfo] = {
    "vi": LanguageInfo(code="vi", name="Tiếng Việt", stt_code="vi", tts_voice="vi-VN-HoaiMyNeural"),
    "en": LanguageInfo(code="en", name="English", stt_code="en", tts_voice="en-US-JennyNeural"),
    "ja": LanguageInfo(code="ja", name="日本語", stt_code="ja", tts_voice="ja-JP-NanamiNeural"),
    "ko": LanguageInfo(code="ko", name="한국어", stt_code="ko", tts_voice="ko-KR-SunHiNeural"),
    "zh": LanguageInfo(code="zh", name="中文", stt_code="zh", tts_voice="zh-CN-XiaoxiaoNeural"),
}


class LanguageManager:
    """Manages multi-language conversation settings."""

    def __init__(self, default: str = "vi") -> None:
        """Initialize with a default language.

        Args:
            default: Default language code.
        """
        self._current = default if default in SUPPORTED_LANGUAGES else "vi"

    @property
    def current(self) -> str:
        """Get the current language code."""
        return self._current

    async def detect_language(self, text: str) -> str:
        """Detect the language of input text.

        Simple heuristic-based detection. For production, use a
        proper language detection library (langdetect, fasttext).

        Args:
            text: Input text to detect.

        Returns:
            Detected language code.
        """
        # Vietnamese characters
        vietnamese_chars = set("àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ")
        text_lower = text.lower()

        if any(c in vietnamese_chars for c in text_lower):
            return "vi"

        # CJK character ranges
        for c in text:
            cp = ord(c)
            if 0x4E00 <= cp <= 0x9FFF:
                return "zh"
            if 0x3040 <= cp <= 0x309F or 0x30A0 <= cp <= 0x30FF:
                return "ja"
            if 0xAC00 <= cp <= 0xD7AF:
                return "ko"

        return "en"

    def get_stt_code(self, lang: str | None = None) -> str:
        """Get the STT language code.

        Args:
            lang: Language code. Defaults to current language.

        Returns:
            STT provider language code.
        """
        code = lang or self._current
        info = SUPPORTED_LANGUAGES.get(code)
        return info.stt_code if info else "vi"

    def get_tts_voice(self, lang: str | None = None) -> str:
        """Get the TTS voice identifier.

        Args:
            lang: Language code. Defaults to current language.

        Returns:
            Edge TTS voice identifier.
        """
        code = lang or self._current
        info = SUPPORTED_LANGUAGES.get(code)
        return info.tts_voice if info else "vi-VN-HoaiMyNeural"

    def switch_language(self, lang: str) -> None:
        """Switch the active language.

        Args:
            lang: Target language code.
        """
        if lang in SUPPORTED_LANGUAGES:
            self._current = lang
            logger.info("Language switched to: %s", SUPPORTED_LANGUAGES[lang].name)
        else:
            logger.warning("Unsupported language: %s", lang)
