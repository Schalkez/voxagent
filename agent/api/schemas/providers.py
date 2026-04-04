"""Provider schemas for the API."""

from dataclasses import dataclass

from pydantic import BaseModel


class SaveKeyRequest(BaseModel):
    """Request body for saving an API key."""

    api_key: str


@dataclass(frozen=True)
class ProviderInfo:
    """Provider information returned by the API."""

    id: str
    name: str
    icon: str
    provider_type: str
    status: str
    has_key: bool


@dataclass(frozen=True)
class TestResult:
    """Result of a provider health check."""

    ok: bool
    latency_ms: int
    message: str
