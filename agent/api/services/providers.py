"""Provider business logic and orchestrations."""

import time
from dataclasses import asdict

from api.schemas.providers import ProviderInfo, TestResult
from api.state.store import PROVIDER_META
from core.keyring_manager import list_provider_keys, save_key
from providers.base import LLMProvider
from providers.registry import ProviderNotFoundError, ProviderRegistry


def get_all_providers() -> list[dict[str, object]]:
    """Get all registered providers and their status."""
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


def store_provider_key(provider_id: str, api_key: str) -> None:
    """Store the API key for a provider."""
    save_key(provider_id, api_key)


async def check_provider_health(registry: ProviderRegistry, provider_id: str) -> dict[str, object]:
    """Check health/latency of a target provider."""
    start = time.monotonic()
    try:
        provider: LLMProvider = registry.get_llm(provider_id)
        ok = await provider.health_check()
        latency = int((time.monotonic() - start) * 1000)

        message = "Connection successful" if ok else "Provider unreachable"

        # Special casing Ollama for models
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


def get_provider_usage(provider_id: str) -> dict[str, object]:
    """Get mock usage statistics for a provider."""
    return {
        "provider": provider_id,
        "daily_tokens": {"used": 1_200_000, "limit": 5_000_000},
        "monthly_cost": {"current": 14.82, "projected": 32.00},
        "active_sessions": 8,
    }
