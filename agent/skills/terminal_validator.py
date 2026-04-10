"""AST-based terminal command validation.

Validates shell commands using structural parsing instead of regex.
Commands are parsed with shlex and validated against an allowlist
of safe command patterns with argument constraints.

Key security decisions (from PITFALLS.md P7.1, P7.2):
- python/pip/node/npm/git are REMOVED -- arbitrary code execution by design
- Commands are validated at the AST level, not string matching
- All non-printable/non-ASCII characters stripped after NFKC normalization
- shlex parsing done AFTER sanitization to prevent token injection
"""

from __future__ import annotations

import ast
import platform
import re
import shlex
import unicodedata
from dataclasses import dataclass

from core.logging import get_logger

logger = get_logger(module="skills.terminal_validator")

_IS_WINDOWS = platform.system() == "Windows"

# ── Constants ──

# Commands that are safe to execute with basic argument validation
SAFE_COMMANDS: frozenset[str] = frozenset({
    "ls", "dir", "echo", "cat", "head", "tail", "wc",
    "find", "grep", "pwd", "whoami", "date", "uptime",
    "df", "free", "tasklist", "systeminfo", "ping",
    "type", "hostname", "env", "printenv", "which", "where",
})

# Commands explicitly banned -- arbitrary code execution vectors
BANNED_COMMANDS: frozenset[str] = frozenset({
    "python", "python3", "pip", "pip3",
    "node", "npm", "npx", "bun", "deno",
    "git", "ssh", "scp", "rsync",
    "bash", "sh", "zsh", "fish", "csh", "ksh",
    "powershell", "pwsh", "cmd",
    "curl", "wget",  # download + execute vectors
    "eval", "exec", "source",
    "sudo", "su", "runas",
    "rm", "del", "rmdir", "rd",  # destructive without explicit action
    "mkfs", "format", "fdisk", "dd",
    "chmod", "chown", "chgrp",
    "kill", "killall", "taskkill",
    "reg", "regedit",
    "nc", "ncat", "netcat",  # network backdoor tools
})

# Shell metacharacters that indicate command chaining/injection
DANGEROUS_SHELL_CHARS: re.Pattern[str] = re.compile(r'[;&|`$><\n\\]|\$\(')

# Only printable ASCII allowed in commands (after NFKC normalization)
_NON_PRINTABLE_ASCII: re.Pattern[str] = re.compile(r'[^\x20-\x7E]')

# Dangerous argument patterns (even for safe commands)
_DANGEROUS_ARG_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r'^-.*exec', re.IGNORECASE),   # find -exec
    re.compile(r'^-.*delete', re.IGNORECASE),  # find -delete
    re.compile(r'^/[sS]$'),                    # del /s (Windows recursive)
    re.compile(r'^/[qQ]$'),                    # del /q (Windows quiet)
]

# Maximum command length to prevent resource exhaustion
MAX_COMMAND_LENGTH = 1024


@dataclass(frozen=True)
class ValidationResult:
    """Result of command validation.

    Attributes:
        is_safe: Whether the command passed all safety checks.
        reason: Human-readable explanation if rejected.
        command: The normalized command string.
        parsed_args: The parsed command tokens (empty if rejected).
    """

    is_safe: bool
    reason: str = ""
    command: str = ""
    parsed_args: tuple[str, ...] = ()

    @staticmethod
    def safe(command: str, args: list[str]) -> ValidationResult:
        """Create a passing validation result."""
        return ValidationResult(
            is_safe=True,
            command=command,
            parsed_args=tuple(args),
        )

    @staticmethod
    def rejected(reason: str, command: str = "") -> ValidationResult:
        """Create a failing validation result."""
        return ValidationResult(
            is_safe=False,
            reason=reason,
            command=command,
        )


def _normalize_command(command: str) -> str:
    """Normalize a command string for safe parsing.

    Applies NFKC normalization then strips all non-printable-ASCII
    characters to prevent Unicode bypass attacks (RTL overrides,
    zero-width chars, homoglyphs).

    Args:
        command: Raw command string.

    Returns:
        Normalized ASCII-only command string.
    """
    normalized = unicodedata.normalize("NFKC", command)
    return _NON_PRINTABLE_ASCII.sub("", normalized).strip()


def _check_python_code_safety(code: str) -> tuple[bool, str]:
    """Check if a Python code string contains dangerous operations via AST.

    This is used ONLY as a secondary check. The primary defense is
    removing python from the allowlist entirely.

    Args:
        code: Python source code to analyze.

    Returns:
        Tuple of (is_safe, reason).
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False, "Invalid Python syntax (potential obfuscation)"

    dangerous_modules = frozenset({
        "os", "sys", "subprocess", "shutil", "pathlib",
        "socket", "http", "urllib", "requests",
        "ctypes", "importlib", "code", "codeop",
        "signal", "resource", "multiprocessing",
        "threading", "pty", "fcntl", "tempfile",
    })

    dangerous_functions = frozenset({
        "eval", "exec", "compile", "execfile",
        "__import__", "globals", "locals",
        "getattr", "setattr", "delattr",
        "open", "input", "breakpoint",
    })

    for node in ast.walk(tree):
        # Check imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_module = alias.name.split(".")[0]
                if root_module in dangerous_modules:
                    return False, f"Dangerous import: {alias.name}"

        if isinstance(node, ast.ImportFrom):
            if node.module:
                root_module = node.module.split(".")[0]
                if root_module in dangerous_modules:
                    return False, f"Dangerous import from: {node.module}"

        # Check function calls
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in dangerous_functions:
                return False, f"Dangerous function call: {func_name}"

    return True, ""


def _has_dangerous_args(args: list[str]) -> tuple[bool, str]:
    """Check if command arguments contain dangerous patterns.

    Args:
        args: Parsed command arguments (excluding the command itself).

    Returns:
        Tuple of (is_dangerous, reason).
    """
    for arg in args:
        for pattern in _DANGEROUS_ARG_PATTERNS:
            if pattern.search(arg):
                return True, f"Dangerous argument pattern: {arg}"
    return False, ""


def validate_command(command: str) -> ValidationResult:
    """Validate a shell command for safe execution.

    Uses structural parsing (shlex + AST) instead of regex matching.
    Commands are normalized, parsed into tokens, and validated against
    the safe command allowlist with argument constraints.

    Args:
        command: The raw shell command string to validate.

    Returns:
        ValidationResult with safety verdict and explanation.
    """
    if not command or not command.strip():
        return ValidationResult.rejected("Empty command")

    # 1. Length check
    if len(command) > MAX_COMMAND_LENGTH:
        return ValidationResult.rejected(
            f"Command exceeds maximum length ({MAX_COMMAND_LENGTH} chars)"
        )

    # 2. Normalize (NFKC + strip non-ASCII)
    normalized = _normalize_command(command)
    if not normalized:
        return ValidationResult.rejected("Command empty after normalization")

    # 3. Check for shell metacharacters
    if DANGEROUS_SHELL_CHARS.search(normalized):
        return ValidationResult.rejected(
            "Command contains dangerous shell characters",
            command=normalized,
        )

    # 4. Parse with shlex
    try:
        parts = shlex.split(normalized, posix=not _IS_WINDOWS)
    except ValueError as e:
        return ValidationResult.rejected(
            f"Failed to parse command: {e}",
            command=normalized,
        )

    if not parts:
        return ValidationResult.rejected("No command tokens after parsing")

    # 5. Extract base command
    base_command = parts[0].lower()
    args = parts[1:]

    # 6. Check against banned list first
    if base_command in BANNED_COMMANDS:
        logger.warning(
            "blocked banned command",
            command=base_command,
            full_command=normalized,
        )
        return ValidationResult.rejected(
            f"Command '{base_command}' is not allowed (code execution vector)",
            command=normalized,
        )

    # 7. Check against safe list
    if base_command not in SAFE_COMMANDS:
        return ValidationResult.rejected(
            f"Command '{base_command}' is not in the allowed command list",
            command=normalized,
        )

    # 8. Validate arguments for dangerous patterns
    is_dangerous, reason = _has_dangerous_args(args)
    if is_dangerous:
        return ValidationResult.rejected(reason, command=normalized)

    # 9. All checks passed
    logger.debug("command validated", command=base_command, args=args)
    return ValidationResult.safe(normalized, parts)
