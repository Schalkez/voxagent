# Skills Development

## Creating a Custom Skill

```python
from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult
from skills.registry import register_skill

@register_skill
class MySkill(BaseSkill):
    name = "my_skill"
    description = "What this skill does — used by LLM for routing"
    keywords = ["trigger", "words", "từ khoá"]
    execution_tiers = [ExecutionTier.NATIVE_API]
    permissions = ["file:read"]

    async def can_handle(self, intent: SkillIntent) -> bool:
        return intent.skill_name == self.name

    async def execute(self, intent: SkillIntent) -> SkillResult:
        action = intent.action
        if action == "my_action":
            return SkillResult(
                success=True,
                tts_response="Xong rồi!",
                tier_used=ExecutionTier.NATIVE_API,
            )
        return SkillResult(success=False, error="Unknown action")
```

## Execution Tiers

| Tier | Name | Speed | Example |
|------|------|-------|---------|
| A | `NATIVE_API` | < 50ms | ctypes, Win32 API |
| B | `APP_API` | < 500ms | REST API calls |
| C | `SHELL` | < 2s | subprocess commands |
| D | `KEYBOARD` | < 1s | Simulated keystrokes |

## Permissions

Skills declare permissions: `media:control`, `app:launch`, `terminal:write`, `file:delete`, etc. Dangerous permissions trigger voice confirmation before execution.

## Built-in Skills

| Skill | Actions | Phase |
|-------|---------|-------|
| `media_control` | play, pause, next, volume | 1 |
| `app_launcher` | open, close, list_running | 1 |
| `system_control` | shutdown, restart, sleep, lock | 1 |
| `terminal` | run_command, list_processes | 2 |
| `file_manager` | list_dir, search, delete | 2 |
| `browser_control` | open_url, search_web | 2 |
| `screen_reader` | read_text, describe_screen | 3 |
| `code_reviewer` | review_visible | 3 |
