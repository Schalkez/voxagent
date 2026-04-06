"""Terminal Skill: Execute shell commands and capture output.

Uses asyncio.to_thread + subprocess.run for safe async execution.
Dangerous commands are blocked by a sanitization step.
"""

from __future__ import annotations

import asyncio
import logging
import platform
import subprocess
from typing import ClassVar

from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult
from skills.registry import register_skill

logger = logging.getLogger("voxagent.skills.terminal")

_IS_WINDOWS = platform.system() == "Windows"

COMMAND_TIMEOUT_S = 30

BLOCKED_PATTERNS = frozenset({"rm -rf /", "format", "del /s /q"})


def _is_command_safe(command: str) -> bool:
    """Check if a command is safe to execute.

    Args:
        command: The shell command string to validate.

    Returns:
        True if the command passes safety checks.
    """
    command_lower = command.lower().strip()
    return all(pattern not in command_lower for pattern in BLOCKED_PATTERNS)


@register_skill
class TerminalSkill(BaseSkill):
    """Executes shell commands and captures output."""

    name = "terminal"
    description = "Execute terminal commands, capture output, and list processes."
    keywords: ClassVar[list[str]] = [
        "run",
        "execute",
        "command",
        "terminal",
        "shell",
        "cmd",
        "chạy lệnh",
        "thực thi",
    ]
    execution_tiers: ClassVar[list[ExecutionTier]] = [
        ExecutionTier.SHELL,
    ]
    permissions: ClassVar[list[str]] = ["terminal:write", "system:info"]

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Determine if this skill can handle the given intent."""
        return intent.skill_name == self.name

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Execute terminal action.

        Supported actions: run_command, list_processes.
        """
        action = intent.action

        if action == "run_command":
            return await self._run_command(intent.params.get("command", ""))

        if action == "list_processes":
            return await self._list_processes()

        return SkillResult(
            success=False,
            error=f"Hành động '{action}' không hỗ trợ bởi terminal.",
            tier_used=ExecutionTier.SHELL,
        )

    async def _run_command(self, command: str) -> SkillResult:
        """Run a shell command and capture output.

        Args:
            command: The shell command string to execute.

        Returns:
            SkillResult with stdout/stderr in data.
        """
        if not command:
            return SkillResult(
                success=False,
                error="No command provided.",
                tts_response="Anh muốn chạy lệnh gì?",
                tier_used=ExecutionTier.SHELL,
            )

        if not _is_command_safe(command):
            return SkillResult(
                success=False,
                error=f"Command blocked by safety filter: {command}",
                tts_response="Lệnh này bị chặn vì lý do an toàn.",
                tier_used=ExecutionTier.SHELL,
            )

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT_S,
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            if result.returncode == 0:
                logger.info("Command succeeded: %s", command)
                stdout[:200] if stdout else "(không có output)"
                return SkillResult(
                    success=True,
                    tts_response="Đã chạy lệnh thành công.",
                    data={"stdout": stdout, "stderr": stderr, "returncode": str(result.returncode)},
                    tier_used=ExecutionTier.SHELL,
                )

            logger.warning("Command failed (rc=%d): %s", result.returncode, command)
            return SkillResult(
                success=False,
                error=f"Exit code {result.returncode}: {stderr or stdout}",
                tts_response="Lệnh chạy không thành công.",
                data={"stdout": stdout, "stderr": stderr, "returncode": str(result.returncode)},
                tier_used=ExecutionTier.SHELL,
            )

        except subprocess.TimeoutExpired:
            return SkillResult(
                success=False,
                error=f"Command timed out after {COMMAND_TIMEOUT_S}s",
                tts_response="Lệnh đã quá thời gian chờ.",
                tier_used=ExecutionTier.SHELL,
            )
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning("Failed to execute command '%s': %s", command, e)
            return SkillResult(
                success=False,
                error=str(e),
                tts_response="Không thể chạy lệnh này.",
                tier_used=ExecutionTier.SHELL,
            )

    async def _list_processes(self) -> SkillResult:
        """List currently running processes.

        Returns:
            SkillResult with top processes in data.
        """
        try:
            if _IS_WINDOWS:
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["tasklist", "/FO", "CSV", "/NH"],
                    capture_output=True,
                    text=True,
                    timeout=COMMAND_TIMEOUT_S,
                )
            else:
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["ps", "aux", "--sort=-rss"],
                    capture_output=True,
                    text=True,
                    timeout=COMMAND_TIMEOUT_S,
                )

            lines = result.stdout.strip().split("\n")[:20]
            return SkillResult(
                success=True,
                tts_response=f"Đang có {len(lines)} tiến trình hiển thị.",
                data={"processes": lines},
                tier_used=ExecutionTier.SHELL,
            )
        except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError) as e:
            return SkillResult(
                success=False,
                error=str(e),
                tts_response="Không thể lấy danh sách tiến trình.",
                tier_used=ExecutionTier.SHELL,
            )
