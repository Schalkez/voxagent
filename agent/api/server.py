"""VoxAgent Management API Server.

Provides REST endpoints for the React dashboard to manage providers,
API keys, and system configuration.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.keyring_manager import list_provider_keys, save_key
from providers.base import LLMProvider
from providers.registry import ProviderNotFoundError, ProviderRegistry

# ── App Setup ──

app = FastAPI(
    title="VoxAgent Management API",
    version="0.1.0",
    docs_url="/api/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Registry ──

registry = ProviderRegistry()

# Import and register providers (lazy to avoid import errors if deps missing)
try:
    from providers.openai_provider import OpenAIProvider

    registry.register_llm("openai", OpenAIProvider)
except ImportError:
    pass

try:
    from providers.groq_provider import GroqProvider

    registry.register_llm("groq", GroqProvider)
except ImportError:
    pass

try:
    from providers.anthropic_provider import AnthropicProvider

    registry.register_llm("anthropic", AnthropicProvider)
except ImportError:
    pass

try:
    from providers.ollama_provider import OllamaProvider

    registry.register_llm("ollama", OllamaProvider)
except ImportError:
    pass

# ── Provider metadata for the dashboard ──

PROVIDER_META = {
    "openai": {"name": "OpenAI", "icon": "psychology", "type": "cloud"},
    "groq": {"name": "Groq", "icon": "bolt", "type": "cloud"},
    "anthropic": {"name": "Anthropic", "icon": "shield", "type": "cloud"},
    "gemini": {"name": "Gemini", "icon": "flare", "type": "cloud"},
    "ollama": {"name": "Ollama", "icon": "terminal", "type": "local"},
}


# ── Request/Response Models ──


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


# ── Endpoints ──


@app.get("/api/providers")
async def list_providers() -> list[dict[str, object]]:
    """List all providers with their status."""
    key_status = list_provider_keys()
    result: list[dict[str, object]] = []

    for pid, meta in PROVIDER_META.items():
        has_key = key_status.get(pid, False)
        status = "connected" if has_key or meta["type"] == "local" else "missing"

        info = ProviderInfo(
            id=pid,
            name=meta["name"],
            icon=meta["icon"],
            provider_type=meta["type"],
            status=status,
            has_key=has_key,
        )
        result.append(asdict(info))

    return result


@app.post("/api/providers/{provider_id}/key")
async def save_provider_key(provider_id: str, body: SaveKeyRequest) -> dict[str, object]:
    """Save an API key to the OS keyring."""
    if provider_id not in PROVIDER_META:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_id}")

    save_key(provider_id, body.api_key)
    return {"success": True, "provider": provider_id}


@app.post("/api/providers/{provider_id}/test")
async def test_provider(provider_id: str) -> dict[str, object]:
    """Test connectivity to a provider."""
    if provider_id not in PROVIDER_META:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider_id}")

    start = time.monotonic()
    try:
        provider: LLMProvider = registry.get_llm(provider_id)
        ok = await provider.health_check()
        latency = int((time.monotonic() - start) * 1000)

        message = "Connection successful" if ok else "Provider unreachable"

        # For Ollama, also list models
        if provider_id == "ollama" and ok:
            from providers.ollama_provider import OllamaProvider

            if isinstance(provider, OllamaProvider):
                models = await provider.list_models()
                message = f"Ping 200 OK - {len(models)} models found ({', '.join(models[:3])})"

        result = TestResult(ok=ok, latency_ms=latency, message=message)
        return asdict(result)
    except ProviderNotFoundError:
        return asdict(TestResult(ok=False, latency_ms=0, message="Provider not registered"))
    except Exception as exc:
        latency = int((time.monotonic() - start) * 1000)
        return asdict(TestResult(ok=False, latency_ms=latency, message=str(exc)))


@app.get("/api/providers/{provider_id}/usage")
async def get_usage(provider_id: str) -> dict[str, object]:
    """Get usage statistics for a provider (placeholder)."""
    # Placeholder — real implementation would track actual usage
    return {
        "provider": provider_id,
        "daily_tokens": {"used": 1_200_000, "limit": 5_000_000},
        "monthly_cost": {"current": 14.82, "projected": 32.00},
        "active_sessions": 8,
    }


# ── Entry Point ──


def main() -> None:
    """Start the management API server."""
    uvicorn.run(
        "api.server:app",
        host="127.0.0.1",
        port=8642,
        reload=True,
    )


if __name__ == "__main__":
    main()
