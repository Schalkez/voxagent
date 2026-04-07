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
| `system_skill` | get_volume, set_volume | 1 |

## Skill Marketplace

VoxAgent includes a built-in Skill Marketplace that lets you discover, install, and share skills.

### Searching for Skills

Use the marketplace search to find community-contributed skills by name, keyword, or category:

```python
from skills.marketplace import search_skills

results = await search_skills("spotify")
# Returns a list of SkillPackage entries with name, author, description, and rating.
```

### Installing Skills

Skills can be installed from a **local path** (a directory containing a valid skill module) or from the **remote marketplace** by package name:

```python
from skills.marketplace import install_skill

# Install from the remote marketplace
await install_skill("spotify_control")

# Install from a local directory
await install_skill("/path/to/my_custom_skill", local=True)
```

Installed skills are placed in `skills/community/` and automatically registered on the next startup (or immediately if hot-reload is enabled).

### Publishing Skills

To share a skill with the community, package it and publish:

```python
from skills.marketplace import publish_skill

await publish_skill("my_skill", author="your_name", description="Does something useful.")
```

Published skills must declare their `permissions` and `execution_tiers` so users can review them before installing.

### Uninstalling Skills

Remove an installed community skill by its identifier:

```python
from skills.marketplace import uninstall_skill

await uninstall_skill("spotify_control")
```

This removes the skill module from `skills/community/` and deregisters it from the runtime.

## Dependency Resolver

When a skill declares Python package dependencies, VoxAgent automatically resolves and installs them on first load. Each skill can specify its requirements in a `requirements` class attribute:

```python
@register_skill
class SpotifySkill(BaseSkill):
    name = "spotify_control"
    requirements = ["spotipy>=2.23.0", "requests"]
    # ...
```

On skill registration the dependency resolver:

1. Reads the skill's `requirements` list.
2. Checks which packages are already installed in the current environment.
3. Runs `pip install` for any missing packages, pinned to the versions specified.
4. Logs all install activity to `logs/dependency_resolver.log`.
5. Raises a clear error and disables the skill if installation fails (e.g., network issues or version conflicts).

This ensures community and custom skills work out of the box without manual `pip install` steps.
