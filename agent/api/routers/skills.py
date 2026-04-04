"""Skills API Router."""

from fastapi import APIRouter, HTTPException

from api.schemas.skills import ToggleSkillRequest
from api.services.skills import get_all_skills, toggle_skill_state

router = APIRouter(prefix="/api/skills", tags=["skills"])

@router.get("")
async def list_skills_route() -> list[dict[str, object]]:
    """List all registered skills."""
    return get_all_skills()

@router.post("/{skill_id}/toggle")
async def toggle_skill_route(skill_id: str, body: ToggleSkillRequest) -> dict[str, object]:
    """Enable or disable a skill."""
    success = toggle_skill_state(skill_id, body.enabled)
    if not success:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")
    return {"success": True, "skill": skill_id, "enabled": body.enabled}
