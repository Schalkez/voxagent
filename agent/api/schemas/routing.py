"""Routing schemas for the API."""

from pydantic import BaseModel

from api.state.store import TierEntry


class RoutingConfigRequest(BaseModel):
    """Request body for updating routing config."""

    preset: str
    tiers: list[TierEntry]
    status: str
