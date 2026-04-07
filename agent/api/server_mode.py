"""VoxAgent API Server Mode — headless operation for home automation.

Adds a /api/command endpoint for programmatic voice command execution
without audio I/O, enabling integration with n8n, Home Assistant, etc.
"""

from __future__ import annotations

import logging
import os
import time
from collections import defaultdict

import uvicorn
from fastapi import APIRouter, Depends, HTTPException, Request

from api.server import app

logger = logging.getLogger("voxagent.api.server_mode")

# --- Constants ---
API_KEY_HEADER = "X-VoxAgent-Key"
RATE_LIMIT_MAX_REQUESTS = 60
RATE_LIMIT_WINDOW_SECONDS = 60

# --- In-memory rate limit store: {ip: [timestamp, ...]} ---
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def _get_client_ip(request: Request) -> str:
    """Extract client IP from the request.

    Args:
        request: The incoming FastAPI request.

    Returns:
        Client IP address string.
    """
    if not request.client:
        return "unknown"
    return request.client.host


def _check_rate_limit(request: Request) -> None:
    """Enforce per-IP rate limiting (max 60 requests/minute).

    Args:
        request: The incoming FastAPI request.

    Raises:
        HTTPException: 429 if rate limit exceeded.
    """
    client_ip = _get_client_ip(request)
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS

    # Prune expired timestamps
    timestamps = _rate_limit_store[client_ip]
    _rate_limit_store[client_ip] = [t for t in timestamps if t > cutoff]

    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    _rate_limit_store[client_ip].append(now)


def _check_api_key(request: Request) -> None:
    """Validate API key from request header.

    Auth is disabled when VOXAGENT_API_KEY env var is not set (open access).

    Args:
        request: The incoming FastAPI request.

    Raises:
        HTTPException: 401 if key is missing or invalid.
    """
    expected_key = os.environ.get("VOXAGENT_API_KEY")
    if not expected_key:
        return

    provided_key = request.headers.get(API_KEY_HEADER)
    if not provided_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    if provided_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


server_router = APIRouter(prefix="/api", tags=["server-mode"])


@server_router.get("/server/health")
async def health_check() -> dict[str, str]:
    """Return server health status.

    Returns:
        JSON with status 'ok'.
    """
    return {"status": "ok"}


@server_router.post(
    "/command",
    dependencies=[Depends(_check_rate_limit), Depends(_check_api_key)],
)
async def execute_command(body: dict[str, str]) -> dict[str, object]:
    """Execute a text command and return the skill result.

    Args:
        body: JSON with "text" field containing the command.

    Returns:
        Skill execution result.
    """
    text = body.get("text", "").strip()
    if not text:
        return {"success": False, "error": "No command text provided"}

    # Import here to avoid circular imports
    from core.brain import Brain
    from providers.registry import ProviderRegistry
    from skills.registry import registry as skill_registry

    registry = getattr(app.state, "provider_registry", ProviderRegistry())
    all_skills = list(skill_registry.get_all_skills().values())
    brain = Brain(registry=registry, skills=all_skills)

    intent = await brain.process(text)

    return {
        "success": True,
        "intent": {
            "skill": intent.skill_name,
            "action": intent.action,
            "params": intent.params,
            "confidence": intent.confidence,
        },
    }


# Mount the server-mode router
app.include_router(server_router)


def run_server_mode(host: str = "0.0.0.0", port: int = 8642) -> None:
    """Run VoxAgent in headless server mode (no audio, no tray).

    Args:
        host: Bind address. Default 0.0.0.0 for network access.
        port: Port number. Default 8642.
    """
    logger.info("Starting VoxAgent in server mode on %s:%d", host, port)
    uvicorn.run(app, host=host, port=port)
