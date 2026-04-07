"""Plugin dependency resolver for marketplace skills.

Resolves and installs Python package dependencies declared
in a skill's manifest before the skill is loaded.
"""

from __future__ import annotations

import importlib
import logging
import subprocess
import sys
from dataclasses import dataclass

logger = logging.getLogger("voxagent.skills.dependency_resolver")

MAX_INSTALL_TIMEOUT_S = 120


@dataclass(frozen=True)
class Dependency:
    """A single skill dependency.

    Attributes:
        package: PyPI package name (e.g., 'httpx').
        import_name: Python import name if different from package (e.g., 'PIL' for 'Pillow').
        version: Optional version constraint (e.g., '>=2.0').
    """

    package: str
    import_name: str = ""
    version: str = ""

    @property
    def importable(self) -> str:
        """Name to use with importlib."""
        return self.import_name or self.package

    @property
    def pip_spec(self) -> str:
        """Pip install specifier (e.g., 'httpx>=0.25')."""
        if self.version:
            return f"{self.package}{self.version}"
        return self.package


def is_installed(dep: Dependency) -> bool:
    """Check if a dependency is already importable.

    Args:
        dep: Dependency to check.

    Returns:
        True if the package can be imported.
    """
    try:
        importlib.import_module(dep.importable)
        return True
    except ImportError:
        return False


def resolve_missing(deps: list[Dependency]) -> list[Dependency]:
    """Filter dependencies to only those not yet installed.

    Args:
        deps: Full list of dependencies.

    Returns:
        List of missing dependencies that need installation.
    """
    return [d for d in deps if not is_installed(d)]


def install_dependencies(deps: list[Dependency]) -> tuple[list[str], list[str]]:
    """Install missing dependencies via pip.

    Args:
        deps: Dependencies to install.

    Returns:
        Tuple of (installed, failed) package name lists.
    """
    missing = resolve_missing(deps)
    if not missing:
        return [], []

    installed: list[str] = []
    failed: list[str] = []

    for dep in missing:
        spec = dep.pip_spec
        logger.info("Installing dependency: %s", spec)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", spec, "--quiet"],
                capture_output=True,
                text=True,
                check=False,
                timeout=MAX_INSTALL_TIMEOUT_S,
            )
            if result.returncode == 0:
                installed.append(dep.package)
                logger.info("Installed: %s", spec)
            else:
                failed.append(dep.package)
                logger.error("pip install %s failed: %s", spec, result.stderr.strip())
        except (subprocess.TimeoutExpired, OSError):
            failed.append(dep.package)
            logger.exception("Failed to install %s", spec)

    return installed, failed


def parse_dependencies(raw: list[str | dict[str, str]]) -> list[Dependency]:
    """Parse dependency declarations from a skill manifest.

    Accepts both string format ('httpx>=0.25') and dict format
    ({'package': 'Pillow', 'import_name': 'PIL', 'version': '>=10.0'}).

    Args:
        raw: Raw dependency list from manifest.

    Returns:
        List of parsed Dependency objects.
    """
    deps: list[Dependency] = []
    for item in raw:
        if isinstance(item, str):
            # Parse 'package>=version' format
            for op in (">=", "<=", "==", "!=", ">", "<"):
                if op in item:
                    pkg, ver = item.split(op, 1)
                    deps.append(Dependency(package=pkg.strip(), version=f"{op}{ver.strip()}"))
                    break
            else:
                deps.append(Dependency(package=item.strip()))
        elif isinstance(item, dict):
            deps.append(
                Dependency(
                    package=item.get("package", ""),
                    import_name=item.get("import_name", ""),
                    version=item.get("version", ""),
                )
            )
    return deps
