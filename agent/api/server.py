"""VoxAgent Management API Server.

Provides REST endpoints for the React dashboard to manage providers,
API keys, and system configuration.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.exceptions import VoxAPIException
from api.routers import providers, routing, settings, skills
from providers.registry import ProviderRegistry

logger = logging.getLogger("voxagent.api")

# ── Lifespan & Dependencies ──


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage the application lifecycle and globals."""
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

    # Attach to app state
    app.state.provider_registry = registry
    logger.info("Provider registry initialized with models.")

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

    logger.info("STT/TTS providers registered.")

    yield  # Yield control to FastAPI to serve requests

    # 3. Teardown
    logger.info("Shutting down API server and releasing resources.")
    del app.state.provider_registry


# ── App Setup ──

app = FastAPI(
    title="VoxAgent Management API",
    version="0.1.0",
    docs_url="/api/docs",
    lifespan=lifespan,
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
