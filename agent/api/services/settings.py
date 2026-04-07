"""Settings business logic."""

from dataclasses import asdict, replace

from api.schemas.settings import SecuritySettings, STTSettings, TTSSettings, WakeWordSettings
from core.config import (
    SecurityConfig,
    STTConfig,
    TTSConfig,
    WakeWordConfig,
    load_config,
    save_config,
)


def get_system_settings() -> dict[str, object]:
    """Get system settings mapped to dict."""
    config = load_config()
    return asdict(config)


def update_system_settings(
    stt: STTSettings, tts: TTSSettings, wake_word: WakeWordSettings, security: SecuritySettings
) -> dict[str, object]:
    """Merge updates safely into the system configuration."""
    config = load_config()

    new_stt = STTConfig(
        provider=stt.provider,
        model=stt.model,
        language=stt.language,
    )
    new_tts = TTSConfig(
        provider=tts.provider,
        voice=tts.voice,
        speed=tts.speed,
    )
    new_ww = WakeWordConfig(
        engine=wake_word.engine,
        phrase=wake_word.phrase,
        sensitivity=wake_word.sensitivity,
    )
    new_sec = SecurityConfig(
        confirm_dangerous_actions=security.confirm_dangerous_actions,
        max_file_delete_without_confirm=security.max_file_delete_without_confirm,
    )

    updated_config = replace(config, stt=new_stt, tts=new_tts, wake_word=new_ww, security=new_sec)
    save_config(updated_config)

    return asdict(updated_config)
