"""Skill permission system — runtime enforcement.

Checks whether a skill has the required permissions for an action
and whether an action is classified as dangerous.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from skills.base import BaseSkill

logger = logging.getLogger("voxagent.skills.permissions")


class PermissionLevel(Enum):
    """Risk level of a permission."""

    SAFE = "safe"
    ELEVATED = "elevated"
    DANGEROUS = "dangerous"


@dataclass(frozen=True)
class SkillPermission:
    """A single permission declaration.

    Attributes:
        name: Permission identifier (e.g., 'terminal:write').
        level: Risk level.
        description: Human-readable description.
    """

    name: str
    level: PermissionLevel
    description: str = ""


# ── Known permission definitions ──

_PERMISSION_DB: dict[str, PermissionLevel] = {
    "media:control": PermissionLevel.SAFE,
    "app:launch": PermissionLevel.SAFE,
    "app:close": PermissionLevel.ELEVATED,
    "system:power": PermissionLevel.DANGEROUS,
    "system:lock": PermissionLevel.ELEVATED,
    "terminal:write": PermissionLevel.DANGEROUS,
    "system:info": PermissionLevel.SAFE,
    "file:read": PermissionLevel.SAFE,
    "file:write": PermissionLevel.ELEVATED,
    "file:delete": PermissionLevel.DANGEROUS,
    "browser:control": PermissionLevel.SAFE,
    "network:access": PermissionLevel.ELEVATED,
    "audio:record": PermissionLevel.DANGEROUS,
    "screen:read": PermissionLevel.ELEVATED,
}


class PermissionManager:
    """Manages skill permission checking at runtime."""

    def check_permission(self, skill: BaseSkill, permission_name: str) -> bool:
        """Check if a skill declares a given permission.

        Args:
            skill: The skill to check.
            permission_name: Permission to verify.

        Returns:
            True if the skill has the permission declared.
        """
        return permission_name in getattr(skill, "permissions", [])

    def get_required_permissions(self, skill: BaseSkill) -> list[SkillPermission]:
        """Get all permissions required by a skill.

        Args:
            skill: The skill to inspect.

        Returns:
            List of SkillPermission objects.
        """
        raw_perms: list[str] = getattr(skill, "permissions", [])
        return [
            SkillPermission(
                name=p,
                level=_PERMISSION_DB.get(p, PermissionLevel.SAFE),
            )
            for p in raw_perms
        ]

    def is_dangerous(self, skill: BaseSkill, action: str) -> bool:
        """Check if a skill action requires dangerous-level permission.

        Args:
            skill: The skill to check.
            action: The action name.

        Returns:
            True if any of the skill's permissions are DANGEROUS.
        """
        perms = self.get_required_permissions(skill)
        return any(p.level == PermissionLevel.DANGEROUS for p in perms)
