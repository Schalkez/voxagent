"""Routing API Router."""

from fastapi import APIRouter
from api.schemas.routing import RoutingConfigRequest
from api.services.routing import get_routing_config, update_routing_config

router = APIRouter(prefix="/api/routing", tags=["routing"])

@router.get("")
async def get_routing_route() -> dict[str, object]:
    """Get the current tier routing configuration."""
    return get_routing_config()

@router.put("")
async def update_routing_route(body: RoutingConfigRequest) -> dict[str, object]:
    """Update the tier routing configuration."""
    update_routing_config(body.preset, body.tiers, body.status)
    return {"success": True}
