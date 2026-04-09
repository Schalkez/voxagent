"""App Launcher Skill: Open and close applications.

Uses os.startfile on Windows (Tier A), subprocess as fallback.
"""

from __future__ import annotations

import asyncio
import logging
import platform
import subprocess
from typing import ClassVar

from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult
from skills.registry import register_skill

logger = logging.getLogger("voxagent.skills.app_launcher")

_IS_WINDOWS = platform.system() == "Windows"

# Common app name → executable mapping (Windows)
_APP_MAP: dict[str, str] = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "firefox": "firefox",
    "notepad": "notepad",
    "calculator": "calc",
    "máy tính": "calc",
    "explorer": "explorer",
    "file explorer": "explorer",
    "paint": "mspaint",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "cmd": "cmd",
    "terminal": "wt",
    "vscode": "code",
    "code": "code",
    "spotify": "spotify",
    "discord": "discord",
    "slack": "slack",
    "teams": "teams",
    "zoom": "zoom",
}


@register_skill
class AppLauncherSkill(BaseSkill):
    """Opens and closes desktop applications."""

    name = "app_launcher"
    description = "Open, close, and switch between desktop applications."
    keywords: ClassVar[list[str]] = [
        "open",
        "launch",
        "start",
        "close",
        "quit",
        "exit",
        "switch",
        "mở",
        "đóng",
        "tắt",
        "chạy",
        "khởi động",
    ]
    execution_tiers: ClassVar[list[ExecutionTier]] = [
        ExecutionTier.NATIVE_API,
        ExecutionTier.SHELL,
    ]
    permissions: ClassVar[list[str]] = ["app:launch", "app:close"]

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Determine if this skill can handle the given intent."""
        return intent.skill_name == self.name

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Execute app launcher action.

        Supported actions: open, close, list_running.
        """
        action = intent.action
        app_name = intent.params.get("app", intent.params.get("name", ""))

        if action in ("open", "launch", "start"):
            return await self._open_app(app_name)

        if action in ("close", "quit", "exit"):
            return await self._close_app(app_name)

        if action == "list_running":
            return await self._list_running()

        return SkillResult.fail(
            error=f"Unsupported action: {action}",
            tts_response=f"Hành động '{action}' không hỗ trợ.",
            error_code="unsupported_action",
            tier_used=ExecutionTier.NATIVE_API,
        )

    async def _open_app(self, app_name: str) -> SkillResult:
        """Open an application by name."""
        if not app_name:
            return SkillResult.fail(
                error="No app name provided.",
                tts_response="Anh muốn mở ứng dụng nào?",
                error_code="invalid_params",
                tier_used=ExecutionTier.NATIVE_API,
            )

        executable = _APP_MAP.get(app_name.lower(), app_name)

        try:
            if _IS_WINDOWS:
                import os

                await asyncio.to_thread(os.startfile, executable)
            else:
                await asyncio.to_thread(
                    subprocess.Popen,
                    [executable],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            logger.info("Opened app: %s (executable: %s)", app_name, executable)
            return SkillResult.ok(
                tts_response=f"Đã mở {app_name} rồi nha.",
                data={"app": app_name, "executable": executable},
                tier_used=ExecutionTier.NATIVE_API,
            )
        except (OSError, FileNotFoundError, subprocess.SubprocessError) as e:
            logger.warning("Failed to open %s: %s", app_name, e)
            return SkillResult.fail(
                error=str(e),
                tts_response=f"Không mở được {app_name}.",
                error_code="execution_error",
                tier_used=ExecutionTier.NATIVE_API,
            )

    async def _close_app(self, app_name: str) -> SkillResult:
        """Close an application by name."""
        if not app_name:
            return SkillResult.fail(
                error="No app name provided.",
                tts_response="Anh muốn tắt ứng dụng nào?",
                error_code="invalid_params",
                tier_used=ExecutionTier.NATIVE_API,
            )

        executable = _APP_MAP.get(app_name.lower(), app_name)

        try:
            if _IS_WINDOWS:
                await asyncio.to_thread(
                    subprocess.run,
                    ["taskkill", "/IM", f"{executable}.exe", "/F"],
                    capture_output=True,
                    check=True,
                    timeout=10,
                )
            else:
                await asyncio.to_thread(
                    subprocess.run,
                    ["pkill", "-f", executable],
                    capture_output=True,
                    check=False,
                    timeout=10,
                )

            logger.info("Closed app: %s", app_name)
            return SkillResult.ok(
                tts_response=f"Đã tắt {app_name} rồi.",
                tier_used=ExecutionTier.SHELL,
            )
        except subprocess.TimeoutExpired:
            return SkillResult.fail(
                error="Timeout closing app",
                tts_response=f"Không tắt được {app_name}, quá thời gian chờ.",
                error_code="timeout",
                tier_used=ExecutionTier.SHELL,
            )
        except (subprocess.SubprocessError, OSError) as e:
            return SkillResult.fail(
                error=str(e),
                tts_response=f"Không tắt được {app_name}.",
                error_code="execution_error",
                tier_used=ExecutionTier.SHELL,
            )

    async def _list_running(self) -> SkillResult:
        """List currently running applications."""
        try:
            import psutil

            processes = []
            for proc in psutil.process_iter(["name", "pid", "memory_info"]):
                try:
                    info = proc.info
                    mem_mb = (info.get("memory_info") or proc.memory_info()).rss / (1024 * 1024)
                    processes.append(
                        {"name": info["name"], "pid": info["pid"], "memory_mb": round(mem_mb, 1)}
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            processes.sort(key=lambda p: p["memory_mb"], reverse=True)
            top_5 = processes[:5]
            app_list = ", ".join(p["name"] for p in top_5)

            return SkillResult.ok(
                tts_response=f"Các ứng dụng đang chạy nhiều nhất: {app_list}.",
                data={"processes": processes[:20]},
                tier_used=ExecutionTier.NATIVE_API,
            )
        except ImportError:
            return SkillResult.fail(
                error="psutil not installed",
                error_code="provider_unavailable",
                tier_used=ExecutionTier.NATIVE_API,
            )
