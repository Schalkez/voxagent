"""Routing schemas for the API."""

from typing import Any

from pydantic import BaseModel


class RoutingConfigRequest(BaseModel):
    """Request body for updating routing config."""
    preset: str
    tiers: list[dict[str, Any]]
    status: str
