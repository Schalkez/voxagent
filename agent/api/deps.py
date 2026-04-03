"""Dependency Injection for FastAPI endpoints."""

from fastapi import Request
from providers.registry import ProviderRegistry
from api.exceptions import VoxAPIException

def get_provider_registry(request: Request) -> ProviderRegistry:
    """Extract the initialized ProviderRegistry from the application state."""
    registry = getattr(request.app.state, "provider_registry", None)
    if registry is None:
        raise VoxAPIException(
            message="Provider Registry is not initialized.",
            status_code=500,
            code="internal_server_error"
        )
    return registry
