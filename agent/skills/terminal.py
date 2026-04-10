"""Terminal Skill: Execute shell commands and capture output.

Uses asyncio.to_thread + subprocess.run for safe async execution.
Commands are validated via AST-based structural parsing (not regex).
python/pip/node/git are removed from the allowlist -- they are
arbitrary code execution vectors by design.
"""

from __future__ import annotations

import asyncio
import platform
import subprocess
from typing import ClassVar

from core.logging import get_logger
from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult
from skills.registry import register_skill
from skills.terminal_validator import validate_command

logger = get_logger(module="skills.terminal")

_IS_WINDOWS = platform.system() == "Windows"

COMMAND_TIMEOUT_S = 30


def _is_command_safe(command: str) -> bool:
    """Check if a command passes AST-based validation.

    Thin wrapper around ``validate_command`` for backward compatibility.

    Args:
        command: Raw shell command string.

    Returns:
        True if the command is considered safe to execute.
    """
    return validate_command(command).is_safe


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

        return SkillResult.fail(
            error=f"Unsupported action: {action}",
            tts_response=f"Hành động '{action}' không hỗ trợ bởi terminal.",
            error_code="unsupported_action",
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
            return SkillResult.fail(
                error="No command provided.",
                tts_response="Anh muốn chạy lệnh gì?",
                error_code="invalid_params",
                tier_used=ExecutionTier.SHELL,
            )

        validation = validate_command(command)
        if not validation.is_safe:
            logger.warning(
                "command blocked by validator",
                command=command,
                reason=validation.reason,
            )
            return SkillResult.fail(
                error=f"Command blocked by safety filter: {validation.reason}",
                tts_response="Lệnh này bị chặn vì lý do an toàn.",
                error_code="command_blocked",
                error_severity="warning",
                tier_used=ExecutionTier.SHELL,
            )

        # Use the pre-parsed args from the validator
        cmd_args = list(validation.parsed_args)

        try:
            # Handle Windows built-ins like 'dir' or 'echo' which fail without shell=True
            if _IS_WINDOWS and cmd_args and cmd_args[0].lower() in {"dir", "echo", "type"}:
                cmd_args = ["cmd.exe", "/c", *cmd_args]

            result = await asyncio.to_thread(
                subprocess.run,
                cmd_args,
                shell=False,
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT_S,
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            if result.returncode == 0:
                logger.info("command succeeded", command=command)
                stdout = stdout[:200] if stdout else "(không có output)"
                return SkillResult.ok(
                    tts_response="Đã chạy lệnh thành công.",
                    data={"stdout": stdout, "stderr": stderr, "returncode": str(result.returncode)},
                    tier_used=ExecutionTier.SHELL,
                )

            logger.warning("command failed", returncode=result.returncode, command=command)
            return SkillResult.fail(
                error=f"Exit code {result.returncode}: {stderr or stdout}",
                tts_response="Lệnh chạy không thành công.",
                error_code="command_failed",
                data={"stdout": stdout, "stderr": stderr, "returncode": str(result.returncode)},
                tier_used=ExecutionTier.SHELL,
            )

        except subprocess.TimeoutExpired:
            return SkillResult.fail(
                error=f"Command timed out after {COMMAND_TIMEOUT_S}s",
                tts_response="Lệnh đã quá thời gian chờ.",
                error_code="timeout",
                tier_used=ExecutionTier.SHELL,
            )
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning("failed to execute command", command=command, error=str(e))
            return SkillResult.fail(
                error=str(e),
                tts_response="Không thể chạy lệnh này.",
                error_code="execution_error",
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
            return SkillResult.ok(
                tts_response=f"Đang có {len(lines)} tiến trình hiển thị.",
                data={"processes": lines},
                tier_used=ExecutionTier.SHELL,
            )
        except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError) as e:
            return SkillResult.fail(
                error=str(e),
                tts_response="Không thể lấy danh sách tiến trình.",
                error_code="execution_error",
                tier_used=ExecutionTier.SHELL,
            )
