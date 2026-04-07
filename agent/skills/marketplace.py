"""Skill marketplace: discover, install, and publish skills.

Supports both remote registry (registry.voxagent.dev) and local
file-based installation for offline/development use.
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger("voxagent.skills.marketplace")

_REGISTRY_URL = "https://registry.voxagent.dev/api/skills"
_SKILLS_DIR = Path(__file__).resolve().parent
_INSTALLED_MANIFEST = _SKILLS_DIR / ".installed.json"


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


def _load_installed_db() -> dict[str, dict[str, str]]:
    """Load the installed-skills manifest from disk."""
    if not _INSTALLED_MANIFEST.exists():
        return {}
    try:
        return json.loads(_INSTALLED_MANIFEST.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Corrupt installed manifest — resetting")
        return {}


def _save_installed_db(db: dict[str, dict[str, str]]) -> None:
    """Persist the installed-skills manifest to disk."""
    _INSTALLED_MANIFEST.write_text(
        json.dumps(db, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


class SkillMarketplace:
    """Client for the VoxAgent skill registry.

    Supports two installation modes:
    - **Remote**: download from registry.voxagent.dev (when httpx is available)
    - **Local**: copy a skill .py file into the skills/ directory
    """

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

    async def install(self, skill_name: str, source_path: str | None = None) -> bool:
        """Install a skill from a local path or the remote registry.

        When *source_path* is given the file is copied into skills/.
        Otherwise the remote registry is queried.

        Args:
            skill_name: Name of the skill to install.
            source_path: Optional local .py file to install from.

        Returns:
            True if installation succeeded.
        """
        if source_path:
            return self._install_local(skill_name, Path(source_path))
        return await self._install_remote(skill_name)

    def _install_local(self, skill_name: str, source: Path) -> bool:
        """Copy a local skill file into the skills directory."""
        if not source.exists():
            logger.error("Source file not found: %s", source)
            return False
        if source.suffix != ".py":
            logger.error("Skill file must be a .py file: %s", source)
            return False

        dest = _SKILLS_DIR / f"{skill_name}.py"
        try:
            shutil.copy2(source, dest)
        except OSError:
            logger.exception("Failed to copy skill file")
            return False

        db = _load_installed_db()
        db[skill_name] = {"version": "local", "source": str(source)}
        _save_installed_db(db)

        logger.info("Installed skill '%s' from %s", skill_name, source)
        return True

    async def _install_remote(self, skill_name: str) -> bool:
        """Download and install a skill from the remote registry."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(f"{_REGISTRY_URL}/{skill_name}/download")
                resp.raise_for_status()
                data = resp.json()

                code = data.get("code", "")
                version = data.get("version", "0.0.0")
                if not code:
                    logger.error("Empty skill code from registry")
                    return False

                dest = _SKILLS_DIR / f"{skill_name}.py"
                dest.write_text(code, encoding="utf-8")

                db = _load_installed_db()
                db[skill_name] = {"version": version, "source": "registry"}
                _save_installed_db(db)

                logger.info("Installed skill '%s' v%s from registry", skill_name, version)
                return True
        except ImportError:
            logger.error("httpx required for remote install")
            return False
        except (ConnectionError, OSError, KeyError):
            logger.exception("Failed to install '%s' from registry", skill_name)
            return False

    async def publish(self, manifest: SkillManifest) -> bool:
        """Publish a skill to the marketplace.

        Uploads the skill source code and metadata to the registry.

        Args:
            manifest: Skill metadata to publish.

        Returns:
            True if publication succeeded.
        """
        source = _SKILLS_DIR / f"{manifest.name}.py"
        if not source.exists():
            logger.error("Skill source not found: %s", source)
            return False

        try:
            import httpx

            code = source.read_text(encoding="utf-8")
            payload = {**asdict(manifest), "code": code}
            # Convert tuple to list for JSON
            payload["permissions"] = list(manifest.permissions)

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(f"{_REGISTRY_URL}/publish", json=payload)
                resp.raise_for_status()
                logger.info("Published skill '%s' v%s", manifest.name, manifest.version)
                return True
        except ImportError:
            logger.error("httpx required for publish")
            return False
        except (ConnectionError, OSError):
            logger.exception("Failed to publish '%s'", manifest.name)
            return False

    async def uninstall(self, skill_name: str) -> bool:
        """Remove an installed marketplace skill.

        Args:
            skill_name: Name of the skill to remove.

        Returns:
            True if uninstall succeeded.
        """
        db = _load_installed_db()
        if skill_name not in db:
            logger.warning("Skill '%s' not in installed manifest", skill_name)
            return False

        target = _SKILLS_DIR / f"{skill_name}.py"
        try:
            if target.exists():
                target.unlink()
        except OSError:
            logger.exception("Failed to delete skill file")
            return False

        del db[skill_name]
        _save_installed_db(db)
        logger.info("Uninstalled skill '%s'", skill_name)
        return True

    def list_installed(self) -> list[SkillManifest]:
        """List locally installed marketplace skills.

        Returns:
            List of installed SkillManifest objects.
        """
        db = _load_installed_db()
        return [
            SkillManifest(
                name=name,
                version=info.get("version", "unknown"),
                author="local",
                description=f"Installed from {info.get('source', 'unknown')}",
            )
            for name, info in db.items()
        ]
