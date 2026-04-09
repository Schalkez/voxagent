# SUMMARY: Plan 01 - VoxError Exception Hierarchy

**Status:** Complete
**Date:** 2026-04-09

## What Was Done

Created a typed `VoxError` exception hierarchy with severity levels, Vietnamese user-facing messages, and retry flags. Migrated all bare `Exception`, `RuntimeError`, `KeyError`, and `VoxAPIException` catches in `core/` and `providers/` to use domain-specific `VoxError` subclasses.

### Error Classes Created
- `VoxError` (base) - severity, user_message, retryable, context
- `ProviderError` - for LLM/STT/TTS/Vision providers (retryable=True by default)
- `ProviderNotAvailableError` - unreachable/unregistered providers
- `AudioError` - audio capture/playback pipeline
- `PipelineError` - EARS/BRAIN/HANDS/MOUTH pipeline (with stage attribute)
- `ConfigError` - configuration issues (severity=CRITICAL by default)
- `SkillError` - skill execution failures (with skill_name attribute)

### Key Pipeline Boundary
`core/app.py` now catches `VoxError` at the main loop, logs with structured context, and speaks the `user_message` via TTS.

## Files Created
| File | Description |
|------|-------------|
| `agent/core/errors.py` | VoxError hierarchy (~155 lines) |
| `agent/tests/test_errors.py` | 14 test cases for hierarchy |

## Files Modified
| File | Change |
|------|--------|
| `agent/providers/registry.py` | `ProviderNotFoundError` now inherits `ProviderError` + `KeyError` |
| `agent/core/brain.py` | Typed catches: `ProviderError` re-raise, `PipelineError` on fallback failure |
| `agent/core/hands.py` | Replaced `VoxAPIException` with `SkillError`, added `VoxError` to tier catches |
| `agent/core/mouth.py` | `AudioError` wrapping for playback failures |
| `agent/core/ears.py` | `PipelineError` for not-started guard, `AudioError` for mic failures |
| `agent/core/eyes.py` | `ProviderError` in vision analysis catches |
| `agent/core/app.py` | `VoxError` catch at pipeline boundary with user_message speak |
| `agent/skills/registry.py` | Replaced `VoxAPIException` with `SkillError` (removed cross-boundary import) |
| `agent/tests/test_app_compliance.py` | Updated to expect `PipelineError` instead of `RuntimeError` |

## Test Results
```
283 passed in 2.43s - zero regressions
14 new error hierarchy tests all passing
```
