---
description: how to add a new skill to VoxAgent
---

1. Create a new file in `skills/` directory, e.g. `skills/my_skill.py`
2. The skill MUST extend `BaseSkill` from `skills/base.py`
3. Required fields:
   - `name`: unique snake_case identifier
   - `description`: what this skill does (used by LLM for routing)
   - `keywords`: list of Tier 0 trigger words
   - `tier`: minimum routing tier required (0-3)
   - `execution_tiers`: list of `ExecutionTier` values, ordered by priority (Tier A→D)
   - `permissions`: list of required permissions

4. Required methods:
   - `can_handle(self, intent) -> bool`
   - `execute(self, intent, context) -> SkillResult`

5. Create a matching `skill.json` manifest with permissions and os_support

6. Example skeleton:
```python
from skills.base import BaseSkill, SkillResult, ExecutionTier

class MySkill(BaseSkill):
    name = "my_skill"
    description = "Does something useful"
    keywords = ["do thing", "make thing"]
    tier = 1
    execution_tiers = [
        ExecutionTier.SHELL,      # Try CLI first
        ExecutionTier.APP_API,    # Then app API
        ExecutionTier.UI,         # Then UI automation
    ]
    permissions = ["filesystem:read"]

    async def can_handle(self, intent) -> bool:
        return intent.skill_name == self.name

    async def execute(self, intent, context) -> SkillResult:
        # Implementation here
        return SkillResult(success=True, tts_response="Done!")
```

7. Register the skill in `skills/__init__.py`

8. Write tests in `tests/test_skills.py`:
```python
async def test_my_skill_execute():
    skill = MySkill()
    result = await skill.execute(mock_intent, mock_context)
    assert result.success is True
```

9. Verify:
```bash
python -m pytest tests/test_skills.py -v -k "my_skill"
```
