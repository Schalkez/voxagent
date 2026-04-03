"""Settings schemas for the API."""

from pydantic import BaseModel
from typing import Any

class UpdateSettingsRequest(BaseModel):
    """Request body for updating settings."""
    stt: dict[str, Any]
    tts: dict[str, Any]
    wake_word: dict[str, Any]
    security: dict[str, Any]
