"""Skill registry and plugin discovery for VoxAgent.

Allows dynamic registration and instantiation of skills.
"""

import importlib
import logging
import pkgutil
from typing import ClassVar

from api.exceptions import VoxAPIException
from skills.base import BaseSkill

logger = logging.getLogger("voxagent.skills")


class SkillRegistry:
    """Singleton registry for managing all available skills.

    Provides capabilities to register new skills and discover
    existing skills from the project structure.
    """

    _instance = None
    _skills: ClassVar[dict[str, BaseSkill]] = {}

    def __new__(cls) -> "SkillRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._skills = {}
        return cls._instance

    @classmethod
    def register(cls, skill_class: type[BaseSkill]) -> type[BaseSkill]:
        """Decorator to register a skill class."""
        if not skill_class.name:
            raise ValueError(f"Skill class {skill_class.__name__} must define a 'name'")

        # Instantiate and store the skill
        instance = skill_class()
        cls._skills[skill_class.name] = instance
        logger.debug("Registered skill: %s", skill_class.name)
        return skill_class

    def get_skill(self, name: str) -> BaseSkill:
        """Retrieve a registered skill by its name."""
        skill = self._skills.get(name)
        if not skill:
            raise VoxAPIException(
                message=f"Skill '{name}' not found in registry.",
                status_code=404,
                code="skill_not_found",
            )
        return skill

    def get_all_skills(self) -> dict[str, BaseSkill]:
        """Get a copy of the dictionary holding all registered skills."""
        return self._skills.copy()

    def discover_skills(self, package_name: str = "skills") -> None:
        """Dynamically load and register all skills from the skills package."""
        logger.info("Discovering skills in package '%s'...", package_name)
        try:
            package = importlib.import_module(package_name)
        except ImportError as e:
            logger.warning("Could not import skills package '%s': %s", package_name, e)
            return

        added_count = 0
        if not hasattr(package, "__path__"):
            return

        for _, module_name, is_pkg in pkgutil.walk_packages(
            package.__path__, package.__name__ + "."
        ):
            if not is_pkg:
                try:
                    importlib.import_module(module_name)
                    added_count += 1
                except (ImportError, AttributeError, TypeError) as e:
                    logger.error("Failed to load skill module '%s': %s", module_name, e)

        logger.info("Loaded %d skill modules from '%s'.", added_count, package_name)


# Create a global instance for easy access
registry = SkillRegistry()


def register_skill(skill_class: type[BaseSkill]) -> type[BaseSkill]:
    """Helper decorator that automatically uses the global registry."""
    return SkillRegistry.register(skill_class)
