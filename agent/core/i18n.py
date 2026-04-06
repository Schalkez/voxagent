"""Internationalization support for VoxAgent responses."""

from __future__ import annotations

SUPPORTED_LOCALES = ("vi", "en")

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "vi": {
        "success": "Đã {action} rồi nha",
        "report": "Hiện tại {state}. {detail}",
        "error": "Không {action} được vì {reason}",
        "confirm": "Ý anh là {option_a} hay {option_b}?",
        "thinking": "Để tôi xem...",
        "dangerous": "Hành động {action} có thể nguy hiểm. Anh có chắc không?",
        "cancelled": "Đã hủy thao tác.",
        "not_found": "Tôi không tìm thấy kỹ năng này.",
        "timeout": "Quá thời gian chờ.",
        "volume_set": "Đã chỉnh âm lượng ở mức {level} phần trăm.",
        "app_opened": "Đã mở {app} rồi nha.",
        "app_closed": "Đã tắt {app} rồi.",
    },
    "en": {
        "success": "Done — {action} completed",
        "report": "Currently {state}. {detail}",
        "error": "Can't {action} because {reason}",
        "confirm": "Do you mean {option_a} or {option_b}?",
        "thinking": "Let me check...",
        "dangerous": "Action {action} could be dangerous. Are you sure?",
        "cancelled": "Action cancelled.",
        "not_found": "I can't find that skill.",
        "timeout": "Timed out.",
        "volume_set": "Volume set to {level} percent.",
        "app_opened": "Opened {app}.",
        "app_closed": "Closed {app}.",
    },
}

_current_locale = "vi"


def t(key: str, locale: str | None = None, **kwargs: str) -> str:
    """Get a translated string with interpolation.

    Args:
        key: Translation key (e.g., 'success', 'error').
        locale: Language code. Defaults to current locale.
        **kwargs: Values to interpolate into the template.

    Returns:
        Translated and formatted string.
    """
    lang = locale or _current_locale
    translations = _TRANSLATIONS.get(lang, _TRANSLATIONS["vi"])
    template = translations.get(key, key)
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def set_locale(locale: str) -> None:
    """Set the current locale.

    Args:
        locale: Language code ('vi', 'en').
    """
    global _current_locale
    if locale in SUPPORTED_LOCALES:
        _current_locale = locale


def get_locale() -> str:
    """Get the current locale."""
    return _current_locale
