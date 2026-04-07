import pytest

from skills.base import SkillIntent
from skills.terminal import TerminalSkill, _is_command_safe


def test_terminal_security():
    # Safe allowed commands
    assert _is_command_safe("echo hello") is True
    assert _is_command_safe("dir C:\\") is True
    assert _is_command_safe("git status") is True

    # Blocked by missing prefix (not in whitelist)
    assert _is_command_safe("wget https://malicious.com") is False
    assert _is_command_safe("curl http://evil.com") is False
    assert _is_command_safe("powershell -c something") is False

    # Blocked by dangerous characters
    assert _is_command_safe("echo hello; whoami") is False
    assert _is_command_safe("echo hello && dir") is False
    assert _is_command_safe("echo hello | grep h") is False
    assert _is_command_safe("echo `whoami`") is False
    assert _is_command_safe("echo $(whoami)") is False
    assert _is_command_safe("echo hello > out.txt") is False

    # Unicode bypass attempt normalization check
    # fullwidth semicolon will normalize to normal semicolon, which is blocked
    assert _is_command_safe("echo hello ； whoami") is False  # noqa: RUF001

    # Unclosed quotes (shlex failure)
    assert _is_command_safe("echo \"unclosed quote") is False

@pytest.mark.asyncio
async def test_terminal_execution_fixes():
    skill = TerminalSkill()

    # Test valid execution intent formats
    intent = SkillIntent(skill_name="terminal", action="run_command", params={"command": "echo test"}, raw_text="run echo test")
    result = await skill.execute(intent)
    assert result.success is True
    # The output from 'echo test' depending on OS could have trailing newline or quotes
    assert "test" in str(result.data.get("stdout", ""))

    # Test blocked action execution
    intent_blocked = SkillIntent(skill_name="terminal", action="run_command", params={"command": "curl google.com"}, raw_text="curl google")
    result_blocked = await skill.execute(intent_blocked)
    assert result_blocked.success is False
    assert "blocked by safety filter" in str(result_blocked.error)
