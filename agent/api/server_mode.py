"""VoxAgent API Server Mode — headless operation for home automation.

Adds a /api/command endpoint for programmatic voice command execution
without audio I/O, enabling integration with n8n, Home Assistant, etc.
"""

from __future__ import annotations

import logging

import uvicorn
from fastapi import APIRouter

from api.server import app

logger = logging.getLogger("voxagent.api.server_mode")

server_router = APIRouter(prefix="/api", tags=["server-mode"])


@server_router.post("/command")
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
