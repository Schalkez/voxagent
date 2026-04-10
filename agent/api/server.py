"""VoxAgent Management API Server.

Provides REST endpoints for the React dashboard to manage providers,
API keys, and system configuration. Requires authentication token
for all API routes.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.exceptions import VoxAPIException
from api.routers import providers, routing, settings, skills
from core.logging import get_logger
from providers.registry import ProviderRegistry

logger = get_logger(module="api")

# ── Auth Configuration ──

# Token can be set via VOXAGENT_API_TOKEN env var.
# If not set, a random token is generated at startup and printed to stderr.
_AUTH_TOKEN: str = ""

# Routes that do not require authentication
_PUBLIC_PATHS: frozenset[str] = frozenset({
    "/api/docs",
    "/docs",
    "/openapi.json",
    "/api/health",
})

_bearer_scheme = HTTPBearer(auto_error=False)


def _init_auth_token() -> str:
    """Initialize the API authentication token.

    Reads from VOXAGENT_API_TOKEN env var. If not set, generates
    a cryptographically secure random token.

    Returns:
        The authentication token string.
    """
    env_token = os.environ.get("VOXAGENT_API_TOKEN", "").strip()
    if env_token:
        return env_token

    generated = secrets.token_urlsafe(32)
    logger.info("generated API auth token (set VOXAGENT_API_TOKEN to use a fixed token)")
    return generated


async def verify_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """Verify the Bearer token for protected routes.

    Public paths (docs, health) are exempt from auth.

    Args:
        request: The incoming HTTP request.
        credentials: The parsed Bearer credentials, if present.

    Raises:
        VoxAPIException: If auth fails (401).
    """
    if request.url.path in _PUBLIC_PATHS:
        return

    if not _AUTH_TOKEN:
        return  # Auth disabled (empty token)

    if credentials is None or credentials.credentials != _AUTH_TOKEN:
        raise VoxAPIException(
            message="Invalid or missing authentication token",
            status_code=401,
            code="unauthorized",
        )

# ── Lifespan & Dependencies ──


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage the application lifecycle and globals."""
    # 0. Initialize auth
    global _AUTH_TOKEN  # noqa: PLW0603
    _AUTH_TOKEN = _init_auth_token()
    app.state.auth_token = _AUTH_TOKEN

    # 1. Initialize Provider Registry
    registry = ProviderRegistry()

    # Register providers dynamically or statically
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
    try:
        from providers.deepseek_provider import DeepSeekProvider

        registry.register_llm("deepseek", DeepSeekProvider)
    except ImportError:
        pass
    try:
        from providers.mistral_provider import MistralProvider

        registry.register_llm("mistral", MistralProvider)
    except ImportError:
        pass
    try:
        from providers.openrouter_provider import OpenRouterProvider

        registry.register_llm("openrouter", OpenRouterProvider)
    except ImportError:
        pass

    # Attach to app state
    app.state.provider_registry = registry
    logger.info("provider registry initialized")

    # Register STT providers
    try:
        from providers.stt.whisper_local import WhisperLocalProvider

        registry.register_stt("whisper_local", WhisperLocalProvider)
    except ImportError:
        pass
    try:
        from providers.stt.openai_whisper import OpenAIWhisperProvider

        registry.register_stt("openai_whisper", OpenAIWhisperProvider)
    except ImportError:
        pass

    # Register TTS providers
    try:
        from providers.tts.edge_tts_provider import EdgeTTSProvider

        registry.register_tts("edge_tts", EdgeTTSProvider)
    except ImportError:
        pass

    logger.info("STT/TTS providers registered")

    yield  # Yield control to FastAPI to serve requests

    # 3. Teardown
    logger.info("shutting down API server")
    del app.state.provider_registry


# ── App Setup ──

app = FastAPI(
    title="VoxAgent Management API",
    version="0.1.0",
    docs_url="/api/docs",
    lifespan=lifespan,
    dependencies=[Depends(verify_token)],
)

# ── Exception Handlers ──


@app.exception_handler(VoxAPIException)
async def vox_api_exception_handler(_: Request, exc: VoxAPIException) -> JSONResponse:
    """Global handler for VoxAgent domain exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": exc.code,
            "message": exc.detail,
            "details": exc.details,
        },
    )


# ── CORS Middleware ──

# Dynamic parse of CORS Origins from ENV (e.g., "http://localhost:5173,https://vox.local")
cors_env = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
allowed_origins = [o.strip() for o in cors_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Mount Routers ──

app.include_router(providers.router)
app.include_router(routing.router)
app.include_router(skills.router)
app.include_router(settings.router)


# ── Dashboard Status Endpoint ──


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Public health check endpoint (no auth required)."""
    return {"status": "ok"}


@app.get("/api/status")
async def get_system_status() -> dict[str, object]:
    """Return system status for the dashboard home page."""
    from skills.registry import registry as skill_registry

    all_skills = skill_registry.get_all_skills()
    active_count = len(all_skills)

    registered = app.state.provider_registry.list_registered()

    return {
        "status": "online",
        "listening": False,
        "skills": {
            "active": active_count,
            "total": active_count,
        },
        "providers": registered,
        "stats": {
            "daily_commands": 0,
            "avg_latency_ms": 0,
            "uptime_seconds": 0,
        },
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
