"""Settings API Router."""

from fastapi import APIRouter

from api.schemas.settings import UpdateSettingsRequest
from api.services.settings import get_system_settings, update_system_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings_route() -> dict[str, object]:
    """Get the current vox agent config settings."""
    return get_system_settings()


@router.put("")
async def update_settings_route(body: UpdateSettingsRequest) -> dict[str, object]:
    """Update settings to config.yaml."""
    updated = update_system_settings(body.stt, body.tts, body.wake_word, body.security)
    return {"success": True, "settings": updated}
