"""Tests for newly implemented features — marketplace, sync, permissions, dependencies."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar
from unittest.mock import AsyncMock, patch

import pytest

from core.sync import SyncManager
from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult
from skills.dependency_resolver import (
    Dependency,
    install_dependencies,
    is_installed,
    parse_dependencies,
    resolve_missing,
)
from skills.marketplace import SkillManifest, SkillMarketplace
from skills.permissions import PermissionLevel, PermissionManager

# ── Marketplace ──


class TestMarketplace:
    """Test the real marketplace install/publish/uninstall."""

    @pytest.mark.asyncio
    async def test_install_local(self, tmp_path: Path) -> None:
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        source = src_dir / "my_skill.py"
        source.write_text("# test skill\n", encoding="utf-8")
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()

        mp = SkillMarketplace()
        with patch("skills.marketplace._SKILLS_DIR", dest_dir), patch(
            "skills.marketplace._INSTALLED_MANIFEST", dest_dir / ".installed.json"
        ):
            result = await mp.install("my_skill", source_path=str(source))
        assert result is True

    @pytest.mark.asyncio
    async def test_install_local_missing_file(self) -> None:
        mp = SkillMarketplace()
        result = await mp.install("ghost", source_path="/nonexistent/skill.py")
        assert result is False

    @pytest.mark.asyncio
    async def test_install_local_non_py(self, tmp_path: Path) -> None:
        source = tmp_path / "bad.txt"
        source.write_text("not python")
        mp = SkillMarketplace()
        result = await mp.install("bad", source_path=str(source))
        assert result is False

    @pytest.mark.asyncio
    async def test_uninstall(self, tmp_path: Path) -> None:
        import json

        skill_file = tmp_path / "removeme.py"
        skill_file.write_text("# skill")
        manifest = tmp_path / ".installed.json"
        manifest.write_text(json.dumps({"removeme": {"version": "1.0", "source": "local"}}))

        mp = SkillMarketplace()
        with patch("skills.marketplace._SKILLS_DIR", tmp_path), patch(
            "skills.marketplace._INSTALLED_MANIFEST", manifest
        ):
            result = await mp.uninstall("removeme")
        assert result is True
        assert not skill_file.exists()

    @pytest.mark.asyncio
    async def test_uninstall_missing(self) -> None:
        mp = SkillMarketplace()
        with patch("skills.marketplace._INSTALLED_MANIFEST", Path("/nonexistent/.installed.json")):
            result = await mp.uninstall("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_installed(self, tmp_path: Path) -> None:
        import json

        manifest = tmp_path / ".installed.json"
        manifest.write_text(json.dumps({"foo": {"version": "1.0", "source": "registry"}}))

        mp = SkillMarketplace()
        with patch("skills.marketplace._INSTALLED_MANIFEST", manifest):
            installed = mp.list_installed()
        assert len(installed) == 1
        assert installed[0].name == "foo"

    @pytest.mark.asyncio
    async def test_publish_missing_source(self) -> None:
        mp = SkillMarketplace()
        manifest = SkillManifest(name="nope", version="1.0", author="test", description="")
        result = await mp.publish(manifest)
        assert result is False

    @pytest.mark.asyncio
    async def test_install_remote_failure(self) -> None:
        mp = SkillMarketplace()
        # Mock httpx inside the function scope to simulate connection failure
        with patch.dict("sys.modules", {"httpx": None}):
            result = await mp.install("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_search_failure(self) -> None:
        mp = SkillMarketplace()
        with patch.dict("sys.modules", {"httpx": None}):
            results = await mp.search("anything")
        assert results == []


# ── Sync ──


class TestSyncReal:
    """Test file-based sync manager."""

    @pytest.mark.asyncio
    async def test_register_and_list(self, tmp_path: Path) -> None:
        mgr = SyncManager(sync_dir=tmp_path)
        device = await mgr.register_device()
        assert device.hostname
        devices = await mgr.list_devices()
        assert len(devices) == 1
        assert devices[0].device_id == device.device_id

    @pytest.mark.asyncio
    async def test_sync_write_and_read(self, tmp_path: Path) -> None:
        mgr = SyncManager(sync_dir=tmp_path)
        await mgr.register_device()
        merged = await mgr.sync_preferences({"theme": "dark"})
        assert merged.get("theme") == "dark"

    @pytest.mark.asyncio
    async def test_remove_device(self, tmp_path: Path) -> None:
        mgr = SyncManager(sync_dir=tmp_path)
        device = await mgr.register_device()
        removed = await mgr.remove_device(device.device_id)
        assert removed is True
        devices = await mgr.list_devices()
        assert len(devices) == 0

    @pytest.mark.asyncio
    async def test_remove_nonexistent(self, tmp_path: Path) -> None:
        mgr = SyncManager(sync_dir=tmp_path)
        removed = await mgr.remove_device("fake-id")
        assert removed is False


# ── Permissions ──


class TestPermissionsEnforcement:
    """Test permission checking."""

    def test_check_permission_present(self) -> None:
        class Sk(BaseSkill):
            name = "test"
            description = "t"
            permissions: ClassVar[list[str]] = ["terminal:write"]
            execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]

            async def can_handle(self, intent: SkillIntent) -> bool:
                return True

            async def execute(self, intent: SkillIntent) -> SkillResult:
                return SkillResult(success=True)

        mgr = PermissionManager()
        assert mgr.check_permission(Sk(), "terminal:write") is True
        assert mgr.check_permission(Sk(), "file:read") is False

    def test_get_required_permissions(self) -> None:
        class Sk(BaseSkill):
            name = "test"
            description = "t"
            permissions: ClassVar[list[str]] = ["file:delete", "system:info"]
            execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]

            async def can_handle(self, intent: SkillIntent) -> bool:
                return True

            async def execute(self, intent: SkillIntent) -> SkillResult:
                return SkillResult(success=True)

        mgr = PermissionManager()
        perms = mgr.get_required_permissions(Sk())
        assert len(perms) == 2
        assert perms[0].level == PermissionLevel.DANGEROUS
        assert perms[1].level == PermissionLevel.SAFE

    def test_is_dangerous(self) -> None:
        class Sk(BaseSkill):
            name = "test"
            description = "t"
            permissions: ClassVar[list[str]] = ["terminal:write"]
            execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]

            async def can_handle(self, intent: SkillIntent) -> bool:
                return True

            async def execute(self, intent: SkillIntent) -> SkillResult:
                return SkillResult(success=True)

        mgr = PermissionManager()
        assert mgr.is_dangerous(Sk(), "run") is True


# ── Dependency resolver ──


class TestDependencyResolver:
    """Test dependency resolution logic."""

    def test_is_installed_stdlib(self) -> None:
        assert is_installed(Dependency(package="json")) is True

    def test_is_installed_missing(self) -> None:
        assert is_installed(Dependency(package="nonexistent_xyzzy_pkg")) is False

    def test_resolve_missing_filters(self) -> None:
        deps = [
            Dependency(package="json"),
            Dependency(package="nonexistent_xyzzy_pkg"),
        ]
        missing = resolve_missing(deps)
        assert len(missing) == 1
        assert missing[0].package == "nonexistent_xyzzy_pkg"

    def test_parse_string_deps(self) -> None:
        raw = ["httpx>=0.25", "pytest", "numpy==1.26"]
        result = parse_dependencies(raw)
        assert len(result) == 3
        assert result[0].pip_spec == "httpx>=0.25"
        assert result[1].pip_spec == "pytest"
        assert result[2].pip_spec == "numpy==1.26"

    def test_parse_dict_deps(self) -> None:
        raw = [{"package": "Pillow", "import_name": "PIL", "version": ">=10.0"}]
        result = parse_dependencies(raw)
        assert result[0].importable == "PIL"
        assert result[0].pip_spec == "Pillow>=10.0"

    def test_install_already_installed(self) -> None:
        deps = [Dependency(package="json")]
        installed, failed = install_dependencies(deps)
        assert installed == []
        assert failed == []


# ── Server mode ──


class TestServerMode:
    """Test server mode auth + rate limiting."""

    def test_rate_limit_store_import(self) -> None:
        from api.server_mode import RATE_LIMIT_MAX_REQUESTS
        assert RATE_LIMIT_MAX_REQUESTS == 60

    def test_api_key_header(self) -> None:
        from api.server_mode import API_KEY_HEADER
        assert API_KEY_HEADER == "X-VoxAgent-Key"


# ── Platform find_element ──


class TestPlatformFindElement:
    """Test macOS/Linux find_element implementations."""

    def test_macos_find_element_no_osascript(self) -> None:
        from system.macos import MacOSAutomation

        auto = MacOSAutomation()
        with patch("system.macos._run_osascript", side_effect=FileNotFoundError):
            result = auto.find_element("button", "OK")
        assert result is None

    def test_linux_find_element_no_xdotool(self) -> None:
        from system.linux import LinuxAutomation

        auto = LinuxAutomation()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = auto.find_element("button", "OK")
        assert result is None


# ── Planner ──


class TestPlanner:
    """Test the multi-step planner."""

    def test_needs_planning_simple(self) -> None:
        from unittest.mock import MagicMock

        from core.planner import Planner

        planner = Planner(registry=AsyncMock(), skills=[], config=MagicMock())
        assert planner.is_multi_step("open chrome") is False
        assert planner.is_multi_step("open chrome and then go to gmail") is True
        assert planner.is_multi_step("first open notepad, then type hello") is True
