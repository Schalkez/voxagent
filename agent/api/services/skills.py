"""Skills business logic."""

from api.state.store import SkillEntry, save_state, skills_state


def get_all_skills() -> list[SkillEntry]:
    """Get all skills from state."""
    return skills_state


def toggle_skill_state(skill_id: str, enabled: bool) -> bool:
    """Toggle a skill's enabled state and persist to disk."""
    for skill in skills_state:
        if skill["id"] == skill_id:
            skill["enabled"] = enabled
            save_state()
            return True
    return False
