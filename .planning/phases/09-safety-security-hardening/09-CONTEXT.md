# Phase 09: Safety & Security Hardening - Context

**Date:** 2026-04-09
**Phase:** 09 of 10
**Dependency:** Phase 1 (Error Foundation) -- completed

## Current State Analysis

### Terminal Safety (SAFE-01, SAFE-02)
- `terminal.py` uses regex-based `ALLOWED_COMMAND_PREFIXES` allowlist
- `python`, `pip`, `node`, `npm`, `git` are in the allowlist -- arbitrary code execution vectors
- `DANGEROUS_SHELL_CHARS` regex catches metacharacters but not semantic danger
- Pitfall P7.1: AST parsing alone can't make `python -c` safe -- remove these entirely
- Pitfall P7.3: Unicode normalization bypass possible (RTL overrides, zero-width chars)

### Type-Safe Parameters (SAFE-03)
- `brain.py` extracts tool call params with manual `str()` casts and `.get()` calls
- No Pydantic validation -- malformed LLM output can crash the pipeline
- `args.get("confidence", 0.9)` wrapped in try/except -- fragile

### PromptGuard (SAFE-04)
- `safety.py` exists with comprehensive injection patterns
- Has `check()` and `sanitize()` methods
- **Never called** from `brain.py:process()` -- completely unwired

### Execution Timeouts (SAFE-05)
- `hands.py` has no timeout on `skill.execute(intent)`
- A hung skill blocks the entire pipeline indefinitely
- Terminal skill has its own `COMMAND_TIMEOUT_S = 30` but other skills have none

### File Sandboxing (SAFE-06)
- `file_manager.py` uses `Path.resolve()` but has no allowed-directory jail
- Any file path is accepted -- can read/write/delete anywhere on the filesystem

### Memory Pruning (SAFE-07)
- `memory.py` stores conversations with no growth limit
- No cleanup/prune method exists
- DB will grow unboundedly over time

### API Auth (SAFE-08)
- `server.py` has no authentication middleware
- Any request to `127.0.0.1:8642` is accepted
- CORS is configured but no token validation

## Implementation Plan

1. **SAFE-01 + SAFE-02**: Create `terminal_validator.py` with AST-based validation, remove dangerous prefixes
2. **SAFE-03**: Create `param_extractor.py` with Pydantic models for type-safe extraction
3. **SAFE-04**: Wire PromptGuard into `brain.py:process()` before intent routing
4. **SAFE-05**: Add `asyncio.timeout()` wrapper in `hands.py:execute()`
5. **SAFE-06**: Add configurable `allowed_directories` to `file_manager.py`
6. **SAFE-07**: Add `auto_prune()` method to `memory.py` with configurable TTL
7. **SAFE-08**: Add bearer token auth middleware to `server.py`

## Files Modified
- `agent/skills/terminal_validator.py` (new)
- `agent/skills/terminal.py` (modified)
- `agent/core/param_extractor.py` (new)
- `agent/core/brain.py` (modified)
- `agent/core/hands.py` (modified)
- `agent/skills/file_manager.py` (modified)
- `agent/core/memory.py` (modified)
- `agent/api/server.py` (modified)
- `tests/test_phase09_safety.py` (new)
