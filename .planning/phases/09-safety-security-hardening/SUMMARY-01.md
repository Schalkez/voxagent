# Phase 09: Safety & Security Hardening — Summary

**Completed:** 2026-04-10
**Status:** All 8 requirements implemented and tested
**Tests:** 51 new tests (375 total, 0 regressions)

---

## Requirements Delivered

### SAFE-01: Terminal AST-based validation
- **File:** `agent/skills/terminal_validator.py`
- Commands are parsed via `shlex.split()` into tokens, then validated against a structural allowlist
- `_check_python_code_safety()` uses Python's `ast.parse()` to detect dangerous imports (`os`, `subprocess`, `shutil`, etc.), dangerous function calls (`eval`, `exec`, `__import__`), and syntax obfuscation
- Unicode bypass prevention: NFKC normalization + strip all non-printable ASCII
- Dangerous argument patterns blocked (e.g., `find -exec`, `del /s`)

### SAFE-02: python/pip/node/git removed from allowlist
- **File:** `agent/skills/terminal_validator.py` — `BANNED_COMMANDS` frozenset
- Completely banned: `python`, `python3`, `pip`, `pip3`, `node`, `npm`, `npx`, `bun`, `deno`, `git`, `ssh`, `bash`, `sh`, `powershell`, `curl`, `wget`, `sudo`, `rm`, `kill`, and 20+ more
- Only structural-safe commands remain: `ls`, `dir`, `echo`, `cat`, `head`, `tail`, `grep`, `find`, `pwd`, `date`, etc.

### SAFE-03: Type-safe parameter extraction (Pydantic)
- **File:** `agent/core/param_extractor.py`
- Pydantic models per skill: `TerminalParams`, `FileManagerParams`, `MediaControlParams`, `AppLauncherParams`, `SystemControlParams`, `GenericParams`
- `extract_params()` validates LLM tool call args, truncates oversize values, rejects overcount params
- Structured `ExtractionResult` with typed errors (`validation_error`, `invalid_type`, `param_overflow`)
- Wired into `Brain._try_llm_routing()` with raw fallback for backward compatibility

### SAFE-04: PromptGuard in Brain.process()
- **File:** `agent/core/brain.py` — `process()` method
- Every user input is checked by `PromptGuard.check()` BEFORE any tier routing
- Injection attempts return an `Intent(action="blocked")` with the rejection reason
- Blocked inputs are logged with structlog for audit trail

### SAFE-05: Per-skill execution timeout
- **File:** `agent/core/hands.py` — `_execute_with_timeout()`
- Uses `asyncio.timeout()` (Python 3.11+) around skill execution
- Default: 30 seconds, configurable via `skill_timeout_s` constructor param
- Capped at `MAX_SKILL_TIMEOUT_S = 300` to prevent unbounded execution
- Timeout produces `SkillResult.fail(error_code="timeout")` — pipeline continues

### SAFE-06: File operations directory restriction
- **File:** `agent/skills/file_manager.py`
- `_is_path_allowed()` checks resolved paths against configurable `allowed_directories`
- Default: user home directory only
- Empty list = no restrictions (backward compatible)
- Checked on: `_list_dir`, `_search`, `_move`, `_copy`, `_delete_file`
- Blocked paths return `error_code="path_not_allowed"`

### SAFE-07: Memory DB bounded growth
- **File:** `agent/core/memory.py` — `auto_prune()`, `prune_old_conversations()`, `enforce_max_conversations()`
- TTL-based: delete conversations older than `DEFAULT_CONVERSATION_TTL_DAYS = 30`
- Count-based: cap at `MAX_CONVERSATIONS_LIMIT = 100,000`
- TTL minimum enforced at 1 day (prevents accidental data loss)
- `auto_prune()` combines both strategies

### SAFE-08: API server authentication
- **File:** `agent/api/server.py`
- Bearer token auth via FastAPI dependency injection
- Token from `VOXAGENT_API_TOKEN` env var, or auto-generated at startup
- Public paths exempt: `/api/health`, `/api/docs`, `/openapi.json`
- Protected endpoints return 401 without valid token
- Existing test_api.py updated to use env-based auth

---

## Files Changed

| File | Change Type | Lines |
|------|-------------|-------|
| `agent/skills/terminal_validator.py` | **New** | 279 |
| `agent/core/param_extractor.py` | **New** | 242 |
| `agent/tests/test_phase09_safety.py` | **New** | 766 |
| `agent/core/brain.py` | Modified | +38 |
| `agent/core/hands.py` | Modified | +49 |
| `agent/core/memory.py` | Modified | +110 |
| `agent/skills/terminal.py` | Modified | +71/-58 |
| `agent/skills/file_manager.py` | Modified | +107 |
| `agent/api/server.py` | Modified | +82 |
| `agent/tests/test_api.py` | Modified | +23 |
| `agent/tests/test_security_phase1.py` | Modified | +6/-6 |

---

## Success Criteria Verification

| Criteria | Status | Evidence |
|----------|--------|----------|
| `python -c "import os; os.system('rm -rf /')"` rejected | PASS | Blocked by shell chars AND banned command list |
| python, pip, node, git removed from allowlist | PASS | In `BANNED_COMMANDS` frozenset, all tests pass |
| LLM tool call params validated via Pydantic | PASS | `ExtractionResult.fail()` with typed errors, 8 tests |
| PromptGuard runs on every input before Brain | PASS | 4 injection patterns tested, all blocked |
| Skill exceeding timeout forcefully cancelled | PASS | 0.5s timeout test with 10s sleep skill |

---

## Test Coverage

- 51 new tests in `test_phase09_safety.py`
- 2 updated tests in `test_security_phase1.py` (git status now blocked)
- 5 updated tests in `test_api.py` (auth token injection)
- **375 total tests passing, 0 regressions**
