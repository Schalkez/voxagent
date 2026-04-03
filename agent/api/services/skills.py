"""Skills business logic."""

from typing import Any
from api.state.store import skills_state

def get_all_skills() -> list[dict[str, Any]]:
    """Get all skills from state."""
    return skills_state

def toggle_skill_state(skill_id: str, enabled: bool) -> bool:
    """Toggle a skill's enabled state."""
    for skill in skills_state:
        if skill["id"] == skill_id:
            skill["enabled"] = enabled
            return True
    return False
