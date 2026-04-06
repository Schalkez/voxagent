"""Skill marketplace: discover, install, and publish skills."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("voxagent.skills.marketplace")

_REGISTRY_URL = "https://registry.voxagent.dev/api/skills"


@dataclass(frozen=True)
class SkillManifest:
    """Metadata about a marketplace skill.

    Attributes:
        name: Skill identifier.
        version: Semantic version string.
        author: Author name or handle.
        description: Human-readable description.
        homepage: URL to the skill's homepage/repo.
        permissions: List of required permission identifiers.
    """

    name: str
    version: str
    author: str
    description: str
    homepage: str = ""
    permissions: tuple[str, ...] = ()


class SkillMarketplace:
    """Client for the VoxAgent skill registry."""

    async def search(self, query: str) -> list[SkillManifest]:
        """Search the marketplace for skills.

        Args:
            query: Search query string.

        Returns:
            List of matching SkillManifest objects.
        """
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{_REGISTRY_URL}/search", params={"q": query})
                resp.raise_for_status()
                data = resp.json()
                return [
                    SkillManifest(
                        name=s["name"],
                        version=s.get("version", "0.0.0"),
                        author=s.get("author", "unknown"),
                        description=s.get("description", ""),
                        homepage=s.get("homepage", ""),
                        permissions=tuple(s.get("permissions", [])),
                    )
                    for s in data.get("skills", [])
                ]
        except (ImportError, ConnectionError, OSError, KeyError):
            logger.warning("Failed to search marketplace")
            return []

    async def install(self, skill_name: str) -> bool:
        """Install a skill from the marketplace.

        Args:
            skill_name: Name of the skill to install.

        Returns:
            True if installation succeeded.
        """
        logger.info("Installing skill: %s (marketplace install not yet implemented)", skill_name)
        return False

    async def publish(self, manifest: SkillManifest) -> bool:
        """Publish a skill to the marketplace.

        Args:
            manifest: Skill metadata to publish.

        Returns:
            True if publication succeeded.
        """
        logger.info("Publishing skill: %s (marketplace publish not yet implemented)", manifest.name)
        return False

    def list_installed(self) -> list[SkillManifest]:
        """List locally installed marketplace skills.

        Returns:
            List of installed SkillManifest objects.
        """
        # Local skills are auto-discovered by skills/registry.py
        return []
