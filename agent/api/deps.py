"""Dependency Injection for FastAPI endpoints."""

from typing import cast

from fastapi import Request

from api.exceptions import VoxAPIException
from providers.registry import ProviderRegistry


def get_provider_registry(request: Request) -> ProviderRegistry:
    """Extract the initialized ProviderRegistry from the application state."""
    registry = getattr(request.app.state, "provider_registry", None)
    if registry is None:
        raise VoxAPIException(
            message="Provider Registry is not initialized.",
            status_code=500,
            code="internal_server_error",
        )
    return cast(ProviderRegistry, registry)
