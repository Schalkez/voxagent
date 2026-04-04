"""Global custom exceptions for the VoxAgent API."""

from typing import Any

from fastapi import HTTPException


class VoxAPIException(HTTPException):
    """Base exception for VoxAgent managed errors."""
    def __init__(self, message: str, status_code: int = 400, code: str = "bad_request", details: Any | None = None):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.details = details

class ProviderConfigError(VoxAPIException):
    """Exception raised when there's an error with a provider's configuration."""
    def __init__(self, message: str, details: Any | None = None):
        super().__init__(message=message, status_code=400, code="provider_config_error", details=details)

class ProviderNotFoundError(VoxAPIException):
    """Exception raised when a requested provider is not found."""
    def __init__(self, provider_id: str):
        super().__init__(
            message=f"Provider '{provider_id}' is not registered or not found.",
            status_code=404,
            code="provider_not_found",
            details={"provider_id": provider_id}
        )
