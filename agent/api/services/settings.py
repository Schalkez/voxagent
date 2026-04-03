"""Settings business logic."""

from typing import Any
from dataclasses import asdict, replace
from core.config import load_config, save_config, STTConfig, TTSConfig, WakeWordConfig, SecurityConfig

def get_system_settings() -> dict[str, Any]:
    """Get system settings mapped to dict."""
    config = load_config()
    return asdict(config)

def update_system_settings(stt: dict[str, Any], tts: dict[str, Any], wake_word: dict[str, Any], security: dict[str, Any]) -> dict[str, Any]:
    """Merge updates safely into the system configuration."""
    config = load_config()

    new_stt = STTConfig(
        provider=stt.get("provider", config.stt.provider),
        model=stt.get("model", config.stt.model),
        language=stt.get("language", config.stt.language),
    )
    new_tts = TTSConfig(
        provider=tts.get("provider", config.tts.provider),
        voice=tts.get("voice", config.tts.voice),
        speed=float(tts.get("speed", config.tts.speed)),
    )
    new_ww = WakeWordConfig(
        engine=wake_word.get("engine", config.wake_word.engine),
        phrase=wake_word.get("phrase", config.wake_word.phrase),
        sensitivity=float(wake_word.get("sensitivity", config.wake_word.sensitivity)),
    )
    new_sec = SecurityConfig(
        confirm_dangerous_actions=bool(security.get("confirm_dangerous_actions", config.security.confirm_dangerous_actions)),
        max_file_delete_without_confirm=int(security.get("max_file_delete_without_confirm", config.security.max_file_delete_without_confirm)),
    )
    
    updated_config = replace(config, stt=new_stt, tts=new_tts, wake_word=new_ww, security=new_sec)
    save_config(updated_config)
    
    return asdict(updated_config)
