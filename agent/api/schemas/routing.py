"""Routing schemas for the API."""

from pydantic import BaseModel
from typing import Any

class RoutingConfigRequest(BaseModel):
    """Request body for updating routing config."""
    preset: str
    tiers: list[dict[str, Any]]
    status: str
