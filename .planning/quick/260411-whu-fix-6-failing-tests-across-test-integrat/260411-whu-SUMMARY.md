# Quick Task 260411-whu: Fix 6 Failing Tests - Summary

**Status:** Complete
**Date:** 2026-04-11
**Commits:** 7e135b6, c23939e, f839bea

---

## What Was Fixed

### Task 1: PromptGuard system prompt extraction pattern (7e135b6)
- **File:** `agent/core/safety.py`
- Added `r"system\s+prompt"` regex pattern to `PromptGuard.INJECTION_PATTERNS`
- Now catches "reveal your system prompt" and similar extraction attempts
- **Test fixed:** `test_integration_safety.py::test_system_prompt_extraction_blocked`

### Task 2: Vietnamese diacritics in response templates (c23939e)
- **File:** `agent/core/mouth.py`
- Updated `RESPONSE_TEMPLATES` dict: ASCII Vietnamese -> proper Unicode diacritics
- `"Da phát nhạc roi nha"` -> `"Đã phát nhạc rồi nha"`
- `"Khong mở Chrome duoc vi"` -> `"Không mở Chrome được vì"`
- **Tests fixed:** `test_mouth.py::test_success_template`, `test_mouth.py::test_error_template`

### Task 3: Outdated test expectations in phase10 coverage (f839bea)
- **File:** `agent/tests/test_phase10_coverage.py`
- Fixed mock target: `skills.screen_reader.Eyes` -> `core.eyes.Eyes`
- Fixed import: `DependencyResolverSkill` -> `Dependency` dataclass
- Fixed enum: `PermissionLevel.NORMAL` -> `PermissionLevel.ELEVATED`
- **Tests fixed:** 3 tests in `test_phase10_coverage.py`

## Test Results

```
6 previously failing tests: ALL PASS
0 regressions introduced
```
