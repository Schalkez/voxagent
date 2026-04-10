"""File Manager Skill: List, search, move, copy, delete files.

Uses pathlib for all file operations with async wrappers.
Delete operations are marked as DANGEROUS and require confirmation.
File operations are restricted to user-configurable allowed directories.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from typing import ClassVar

from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult
from skills.registry import register_skill

logger = logging.getLogger("voxagent.skills.file_manager")

MAX_SEARCH_RESULTS = 50

# ── Default allowed directories ──
# Users can override via config. Empty list means all paths allowed (backward compat).
_DEFAULT_ALLOWED_DIRS: list[str] = [
    str(Path.home()),
]


def _resolve_allowed_dirs(allowed: list[str] | None = None) -> list[Path]:
    """Resolve allowed directory paths to absolute Path objects.

    Args:
        allowed: List of directory path strings. None uses defaults.

    Returns:
        List of resolved Path objects.
    """
    dirs = allowed if allowed is not None else _DEFAULT_ALLOWED_DIRS
    return [Path(d).resolve() for d in dirs if d]


def _is_path_allowed(target: Path, allowed_dirs: list[Path]) -> bool:
    """Check if a path falls within any allowed directory.

    Args:
        target: The resolved path to check.
        allowed_dirs: List of allowed directory roots.

    Returns:
        True if path is within an allowed directory, or if no
        restrictions are configured (empty list).
    """
    if not allowed_dirs:
        return True

    resolved = target.resolve()
    return any(
        resolved == allowed or allowed in resolved.parents
        for allowed in allowed_dirs
    )


@register_skill
class FileManagerSkill(BaseSkill):
    """Lists, searches, moves, copies, and deletes files.

    File operations are restricted to allowed directories (configurable).
    """

    name = "file_manager"
    description = "Manage files and folders: list, search, move, copy, delete."
    keywords: ClassVar[list[str]] = [
        "file",
        "folder",
        "directory",
        "find",
        "search",
        "move",
        "copy",
        "delete",
        "tìm file",
        "xóa",
        "di chuyển",
        "sao chép",
    ]
    execution_tiers: ClassVar[list[ExecutionTier]] = [
        ExecutionTier.NATIVE_API,
        ExecutionTier.SHELL,
    ]
    permissions: ClassVar[list[str]] = ["file:read", "file:write", "file:delete"]

    def __init__(self, allowed_directories: list[str] | None = None) -> None:
        """Initialize the FileManagerSkill.

        Args:
            allowed_directories: List of directory paths that file
                operations are restricted to. None uses defaults
                (user home directory).
        """
        super().__init__()
        self._allowed_dirs = _resolve_allowed_dirs(allowed_directories)

    def _check_path_allowed(self, path: Path) -> SkillResult | None:
        """Return a failure SkillResult if path is outside allowed dirs.

        Args:
            path: Resolved path to validate.

        Returns:
            SkillResult.fail if blocked, None if allowed.
        """
        if _is_path_allowed(path, self._allowed_dirs):
            return None

        logger.warning("path blocked by directory restriction: %s", path)
        return SkillResult.fail(
            error=f"Path outside allowed directories: {path}",
            tts_response="Đường dẫn này nằm ngoài vùng cho phép.",
            error_code="path_not_allowed",
            error_severity="warning",
            tier_used=ExecutionTier.NATIVE_API,
        )

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Determine if this skill can handle the given intent."""
        return intent.skill_name == self.name

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Execute file manager action.

        Supported actions: list_dir, search, move, copy, delete_file.
        """
        action = intent.action

        if action == "list_dir":
            return await self._list_dir(intent.params.get("path", "."))

        if action == "search":
            return await self._search(
                intent.params.get("query", ""),
                intent.params.get("path", "."),
            )

        if action == "move":
            return await self._move(
                intent.params.get("source", ""),
                intent.params.get("destination", ""),
            )

        if action == "copy":
            return await self._copy(
                intent.params.get("source", ""),
                intent.params.get("destination", ""),
            )

        if action == "delete_file":
            return await self._delete_file(intent.params.get("path", ""))

        return SkillResult.fail(
            error=f"Unsupported action: {action}",
            tts_response=f"Hành động '{action}' không hỗ trợ bởi file_manager.",
            error_code="unsupported_action",
            tier_used=ExecutionTier.NATIVE_API,
        )

    async def _list_dir(self, path_str: str) -> SkillResult:
        """List contents of a directory.

        Args:
            path_str: Path to the directory to list.

        Returns:
            SkillResult with file/folder listing in data.
        """
        try:
            target = Path(path_str).resolve()

            # SAFE-06: Directory restriction check
            blocked = self._check_path_allowed(target)
            if blocked is not None:
                return blocked

            if not target.is_dir():
                return SkillResult.fail(
                    error=f"Not a directory: {target}",
                    tts_response="Đường dẫn không phải là thư mục.",
                    error_code="invalid_params",
                    tier_used=ExecutionTier.NATIVE_API,
                )

            entries = await asyncio.to_thread(list, target.iterdir())
            items = [
                {
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                    "size": str(entry.stat().st_size) if entry.is_file() else "",
                }
                for entry in sorted(entries, key=lambda e: (not e.is_dir(), e.name))
            ]

            count = len(items)
            return SkillResult.ok(
                tts_response=f"Thư mục có {count} mục.",
                data={"path": str(target), "items": items},
                tier_used=ExecutionTier.NATIVE_API,
            )
        except PermissionError:
            return SkillResult.fail(
                error=f"Permission denied: {path_str}",
                tts_response="Không có quyền truy cập thư mục này.",
                error_code="permission_denied",
                tier_used=ExecutionTier.NATIVE_API,
            )
        except OSError as e:
            return SkillResult.fail(
                error=str(e),
                tts_response="Không thể đọc thư mục.",
                error_code="io_error",
                tier_used=ExecutionTier.NATIVE_API,
            )

    async def _search(self, query: str, path_str: str) -> SkillResult:
        """Search for files matching a query pattern.

        Args:
            query: Glob pattern or filename substring to search.
            path_str: Root directory to search from.

        Returns:
            SkillResult with matching file paths in data.
        """
        if not query:
            return SkillResult.fail(
                error="No search query provided.",
                tts_response="Anh muốn tìm file gì?",
                error_code="invalid_params",
                tier_used=ExecutionTier.NATIVE_API,
            )

        try:
            target = Path(path_str).resolve()

            # SAFE-06: Directory restriction check
            blocked = self._check_path_allowed(target)
            if blocked is not None:
                return blocked

            pattern = f"*{query}*" if "*" not in query else query

            matches = await asyncio.to_thread(
                lambda: [str(p) for p in target.rglob(pattern)][:MAX_SEARCH_RESULTS]
            )

            if not matches:
                return SkillResult.ok(
                    tts_response=f"Không tìm thấy file nào khớp với '{query}'.",
                    data={"matches": []},
                    tier_used=ExecutionTier.NATIVE_API,
                )

            return SkillResult.ok(
                tts_response=f"Tìm thấy {len(matches)} file.",
                data={"matches": matches},
                tier_used=ExecutionTier.NATIVE_API,
            )
        except (PermissionError, OSError) as e:
            return SkillResult.fail(
                error=str(e),
                tts_response="Không thể tìm kiếm file.",
                error_code="io_error",
                tier_used=ExecutionTier.NATIVE_API,
            )

    async def _move(self, source: str, destination: str) -> SkillResult:
        """Move a file or directory.

        Args:
            source: Path to the source file or directory.
            destination: Path to move the source to.

        Returns:
            SkillResult indicating success or failure.
        """
        if not source or not destination:
            return SkillResult.fail(
                error="Source and destination paths required.",
                tts_response="Cần cung cấp đường dẫn nguồn và đích.",
                error_code="invalid_params",
                tier_used=ExecutionTier.NATIVE_API,
            )

        try:
            src = Path(source).resolve()
            dst = Path(destination).resolve()

            # SAFE-06: Directory restriction check for both paths
            for check_path in (src, dst):
                blocked = self._check_path_allowed(check_path)
                if blocked is not None:
                    return blocked

            await asyncio.to_thread(shutil.move, str(src), str(dst))

            logger.info("Moved: %s → %s", src, dst)
            return SkillResult.ok(
                tts_response="Đã di chuyển file thành công.",
                data={"source": str(src), "destination": str(dst)},
                tier_used=ExecutionTier.NATIVE_API,
            )
        except (FileNotFoundError, PermissionError, OSError) as e:
            return SkillResult.fail(
                error=str(e),
                tts_response="Không thể di chuyển file.",
                error_code="io_error",
                tier_used=ExecutionTier.NATIVE_API,
            )

    async def _copy(self, source: str, destination: str) -> SkillResult:
        """Copy a file or directory.

        Args:
            source: Path to the source file or directory.
            destination: Path to copy the source to.

        Returns:
            SkillResult indicating success or failure.
        """
        if not source or not destination:
            return SkillResult.fail(
                error="Source and destination paths required.",
                tts_response="Cần cung cấp đường dẫn nguồn và đích.",
                error_code="invalid_params",
                tier_used=ExecutionTier.NATIVE_API,
            )

        try:
            src = Path(source).resolve()
            dst = Path(destination).resolve()

            # SAFE-06: Directory restriction check for both paths
            for check_path in (src, dst):
                blocked = self._check_path_allowed(check_path)
                if blocked is not None:
                    return blocked

            if src.is_dir():
                await asyncio.to_thread(shutil.copytree, str(src), str(dst))
            else:
                await asyncio.to_thread(shutil.copy2, str(src), str(dst))

            logger.info("Copied: %s → %s", src, dst)
            return SkillResult.ok(
                tts_response="Đã sao chép file thành công.",
                data={"source": str(src), "destination": str(dst)},
                tier_used=ExecutionTier.NATIVE_API,
            )
        except (FileNotFoundError, PermissionError, OSError) as e:
            return SkillResult.fail(
                error=str(e),
                tts_response="Không thể sao chép file.",
                error_code="io_error",
                tier_used=ExecutionTier.NATIVE_API,
            )

    async def _delete_file(self, path_str: str) -> SkillResult:
        """Delete a file or directory.

        This action is marked as DANGEROUS and requires confirmation
        through the HANDS module before execution.

        Args:
            path_str: Path to the file or directory to delete.

        Returns:
            SkillResult indicating success or failure.
        """
        if not path_str:
            return SkillResult.fail(
                error="No path provided.",
                tts_response="Anh muốn xóa file nào?",
                error_code="invalid_params",
                tier_used=ExecutionTier.NATIVE_API,
            )

        try:
            target = Path(path_str).resolve()

            # SAFE-06: Directory restriction check
            blocked = self._check_path_allowed(target)
            if blocked is not None:
                return blocked

            if not target.exists():
                return SkillResult.fail(
                    error=f"Path not found: {target}",
                    tts_response="Không tìm thấy file này.",
                    error_code="not_found",
                    tier_used=ExecutionTier.NATIVE_API,
                )

            if target.is_dir():
                await asyncio.to_thread(shutil.rmtree, str(target))
            else:
                await asyncio.to_thread(target.unlink)

            logger.info("Deleted: %s", target)
            return SkillResult.ok(
                tts_response=f"Đã xóa {target.name} rồi.",
                data={"deleted": str(target)},
                tier_used=ExecutionTier.NATIVE_API,
            )
        except (PermissionError, OSError) as e:
            return SkillResult.fail(
                error=str(e),
                tts_response="Không thể xóa file này.",
                error_code="io_error",
                tier_used=ExecutionTier.NATIVE_API,
            )
