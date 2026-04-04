"""Settings schemas for the API."""

from typing import Any

from pydantic import BaseModel


class UpdateSettingsRequest(BaseModel):
    """Request body for updating settings."""
    stt: dict[str, Any]
    tts: dict[str, Any]
    wake_word: dict[str, Any]
    security: dict[str, Any]
