"""Settings schemas for the API."""

from pydantic import BaseModel


class STTSettings(BaseModel):
    """STT configuration section."""

    provider: str = "local"
    model: str = "whisper-base"
    language: str = "vi"


class TTSSettings(BaseModel):
    """TTS configuration section."""

    provider: str = "edge_tts"
    voice: str = "vi-female"
    speed: float = 1.0


class WakeWordSettings(BaseModel):
    """Wake word configuration section."""

    engine: str = "openwakeword"
    phrase: str = "hey vox"
    sensitivity: float = 0.7


class SecuritySettings(BaseModel):
    """Security configuration section."""

    confirm_dangerous_actions: bool = True
    max_file_delete_without_confirm: int = 0


class UpdateSettingsRequest(BaseModel):
    """Request body for updating settings."""

    stt: STTSettings
    tts: TTSSettings
    wake_word: WakeWordSettings
    security: SecuritySettings
