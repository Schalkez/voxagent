"""Skills schemas for the API."""

from pydantic import BaseModel


class ToggleSkillRequest(BaseModel):
    """Request body for toggling a skill."""

    enabled: bool
