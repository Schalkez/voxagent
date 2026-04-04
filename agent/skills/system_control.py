"""System Control Skill: Shutdown, restart, sleep, lock.

All actions are marked as DANGEROUS and require voice confirmation
before execution. Uses native OS commands via subprocess.
"""

from __future__ import annotations

import asyncio
import logging
import platform
import subprocess
from typing import ClassVar

from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult
from skills.registry import register_skill

logger = logging.getLogger("voxagent.skills.system_control")

_IS_WINDOWS = platform.system() == "Windows"


@register_skill
class SystemControlSkill(BaseSkill):
    """Controls system power and lock state."""

    name = "system_control"
    description = "Shutdown, restart, sleep, or lock the computer."
    keywords: ClassVar[list[str]] = [
        "shutdown",
        "restart",
        "reboot",
        "sleep",
        "lock",
        "hibernate",
        "tắt máy",
        "khởi động lại",
        "ngủ",
        "khóa",
        "khóa màn hình",
    ]
    execution_tiers: ClassVar[list[ExecutionTier]] = [ExecutionTier.NATIVE_API]
    permissions: ClassVar[list[str]] = ["system:power", "system:lock"]

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Determine if this skill can handle the given intent."""
        return intent.skill_name == self.name

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Execute system control action.

        Supported actions: shutdown, restart, sleep, lock, hibernate.
        """
        action = intent.action
        delay = intent.params.get("delay", "60")

        if action == "shutdown":
            return await self._shutdown(delay)
        if action == "restart":
            return await self._restart(delay)
        if action == "sleep":
            return await self._sleep()
        if action == "lock":
            return await self._lock()
        if action == "hibernate":
            return await self._hibernate()

        return SkillResult(
            success=False,
            error=f"Hành động '{action}' không hỗ trợ bởi {self.name} skill.",
            tier_used=ExecutionTier.NATIVE_API,
        )

    async def _shutdown(self, delay: str) -> SkillResult:
        """Schedule system shutdown."""
        return await self._run_power_cmd(
            win_cmd=["shutdown", "/s", "/t", delay],
            unix_cmd=["shutdown", "-h", f"+{int(delay) // 60}"],
            description=f"tắt máy sau {delay} giây",
        )

    async def _restart(self, delay: str) -> SkillResult:
        """Schedule system restart."""
        return await self._run_power_cmd(
            win_cmd=["shutdown", "/r", "/t", delay],
            unix_cmd=["shutdown", "-r", f"+{int(delay) // 60}"],
            description=f"khởi động lại sau {delay} giây",
        )

    async def _sleep(self) -> SkillResult:
        """Put system to sleep."""
        return await self._run_power_cmd(
            win_cmd=["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
            unix_cmd=["systemctl", "suspend"],
            description="đưa máy vào chế độ ngủ",
        )

    async def _lock(self) -> SkillResult:
        """Lock the screen."""
        return await self._run_power_cmd(
            win_cmd=["rundll32.exe", "user32.dll,LockWorkStation"],
            unix_cmd=["loginctl", "lock-session"],
            description="khóa màn hình",
        )

    async def _hibernate(self) -> SkillResult:
        """Hibernate the system."""
        return await self._run_power_cmd(
            win_cmd=["shutdown", "/h"],
            unix_cmd=["systemctl", "hibernate"],
            description="đưa máy vào chế độ ngủ đông",
        )

    async def _run_power_cmd(
        self,
        win_cmd: list[str],
        unix_cmd: list[str],
        description: str,
    ) -> SkillResult:
        """Run a platform-specific power management command.

        Args:
            win_cmd: Command for Windows.
            unix_cmd: Command for Linux/macOS.
            description: Vietnamese description for TTS response.

        Returns:
            SkillResult indicating success or failure.
        """
        cmd = win_cmd if _IS_WINDOWS else unix_cmd

        try:
            await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                check=True,
                timeout=10,
            )
            logger.info("Executed system command: %s", " ".join(cmd))
            return SkillResult(
                success=True,
                tts_response=f"Đã {description} rồi nha.",
                tier_used=ExecutionTier.NATIVE_API,
            )
        except subprocess.TimeoutExpired:
            return SkillResult(
                success=False,
                error="Command timed out",
                tts_response="Lệnh hệ thống quá thời gian chờ.",
                tier_used=ExecutionTier.NATIVE_API,
            )
        except Exception as e:
            logger.exception("System command failed: %s", cmd)
            return SkillResult(
                success=False,
                error=str(e),
                tts_response=f"Không {description} được.",
                tier_used=ExecutionTier.NATIVE_API,
            )
