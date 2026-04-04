"""Providers API Router."""

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_provider_registry
from api.schemas.providers import SaveKeyRequest
from api.services.providers import (
    check_provider_health,
    get_all_providers,
    get_provider_usage,
    store_provider_key,
)
from api.state.store import PROVIDER_META
from providers.registry import ProviderRegistry

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("")
async def list_providers_route() -> list[dict[str, object]]:
    """List all providers with their status."""
    return get_all_providers()


@router.post("/{provider_id}/key")
async def save_provider_key_route(provider_id: str, body: SaveKeyRequest) -> dict[str, object]:
    """Save an API key to the OS keyring."""
    if provider_id not in PROVIDER_META:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_id}")
    store_provider_key(provider_id, body.api_key)
    return {"success": True, "provider": provider_id}


@router.post("/{provider_id}/test")
async def test_provider_route(provider_id: str, registry: ProviderRegistry = Depends(get_provider_registry)) -> dict[str, object]:
    """Test connectivity to a provider."""
    if provider_id not in PROVIDER_META:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_id}")
    return await check_provider_health(registry, provider_id)


@router.get("/{provider_id}/usage")
async def get_usage_route(provider_id: str) -> dict[str, object]:
    """Get usage statistics for a provider."""
    if provider_id not in PROVIDER_META:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_id}")
    return get_provider_usage(provider_id)
