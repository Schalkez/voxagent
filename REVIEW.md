---
reviewed: 2026-04-07T22:25:00+07:00
depth: deep
files_reviewed: 100+
findings:
  critical: 5
  warning: 8
  info: 4
  total: 17
status: issues_found
---

# 🔍 VoxAgent — GSD Deep Code Review

**Reviewed:** 2026-04-07
**Depth:** Deep (cross-file + architecture audit)
**Score:** 7.0 / 10

---

## Score Breakdown

| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Architecture | 8.0 | 20% | 1.60 |
| Code Quality | 7.5 | 20% | 1.50 |
| Testing | 5.5 | 15% | 0.83 |
| Security | 7.0 | 15% | 1.05 |
| DevOps / CI | 7.5 | 10% | 0.75 |
| Documentation | 7.0 | 10% | 0.70 |
| Dashboard (FE) | 5.5 | 10% | 0.55 |
| **Total** | | **100%** | **6.98 → 7.0** |

---

## Critical Issues

### CR-01: Coverage Gaming — Artificial 80% Metric

**Files:**
- `agent/tests/test_coverage_boost.py` (194 LOC)
- `agent/tests/test_push_80.py` (328 LOC)
- `agent/tests/test_final_coverage.py` (377 LOC)

**Issue:** 899 LOC of tests exist solely to push coverage from ~60% to 80%. Many tests lack assertions (e.g., `test_play_earcon_with_various_sounds` loops without asserting).

**Fix:** Rewrite with behavioral assertions or remove; honestly report ~55-60% real coverage.

### CR-02: 1,027 LOC Production Code Excluded from Coverage

**File:** `agent/pyproject.toml:134-150`

**Issue:** 16 omit patterns hide critical production code: `core/app.py` (373 LOC), `core/ears.py` (286 LOC), ALL providers, ALL platform modules, `api/server_mode.py`.

**Fix:** Remove omits, mark tests as `@pytest.mark.integration` instead.

### CR-03: Terminal `shell=True` Security Hole

**File:** `agent/skills/terminal.py:113`

**Issue:** `subprocess.run(command, shell=True)` with user input. `BLOCKED_PATTERNS` only blocks 3 strings — trivially bypassed via unicode tricks, path variations, or command chaining.

**Fix:** Whitelist approach, or parse into list args, or restrict to predefined commands.

### CR-04: Dead Modules Not Wired to Pipeline

**Files:**
- `agent/core/autopilot.py` — Full implementation, but `app.py` never imports or starts it
- `agent/core/eyes.py` — Full implementation, but `brain.py` has no vision flow

**Issue:** README promises "khi Cursor idle thì prompt tiếp" and "nhìn màn hình" — these features don't actually work end-to-end.

**Fix:** Wire Autopilot.run() as asyncio task in VoxAgentApp.start(). Add Eyes context injection in Brain.process().

### CR-05: API Key Timing Attack

**File:** `agent/api/server_mode.py:85`

**Issue:** `provided_key != expected_key` — string comparison vulnerable to timing attacks.

**Fix:** Use `hmac.compare_digest(provided_key, expected_key)`.

---

## Warnings

### WR-01: Dead Code in terminal.py

**File:** `agent/skills/terminal.py:124`

**Issue:** `stdout[:200] if stdout else "(không có output)"` — expression result discarded, not assigned.

### WR-02: Blocking I/O in Async SyncManager

**File:** `agent/core/sync.py:86-89, 108-118, 124-136`

**Issue:** `Path.write_text()` / `Path.read_text()` called synchronously inside `async` methods.

**Fix:** Use `asyncio.to_thread()` wrapping.

### WR-03: Magic Confidence = 0.9

**File:** `agent/core/brain.py:177`

**Issue:** LLM routing always returns `confidence=0.9` hardcoded, doesn't reflect actual LLM certainty.

### WR-04: Brain Re-created Per API Request

**File:** `agent/api/server_mode.py:120-126`

**Issue:** `execute_command()` creates new `Brain` instance every request. Memory waste + no context reuse.

### WR-05: Setup Wizard Crashes on Invalid Input

**File:** `agent/core/app.py:364`

**Issue:** `int(choice) - 1` crashes with `ValueError` if user types non-numeric input.

### WR-06: Server Binds 0.0.0.0 by Default

**File:** `agent/api/server_mode.py:145`

**Issue:** Exposes API to entire LAN without explicit opt-in. Should default to `127.0.0.1`.

### WR-07: Rate Limit Store Grows Unbounded

**File:** `agent/api/server_mode.py:27`

**Issue:** `defaultdict(list)` never evicts old IPs. Memory grows under sustained attack.

### WR-08: Dashboard TypeScript Errors

**File:** `dashboard/tsc_errors.log` (17 errors)

**Issue:** Missing module declarations, implicit `any` types. Build claims clean but strict checking reveals issues.

---

## Info

### IN-01: output.py Leftover

**File:** `agent/output.py` (52 bytes) — Unused stub file.

### IN-02: CI Missing interrogate + vulture

**File:** `.github/workflows/ci.yml` — Configured in pyproject.toml but not run in CI.

### IN-03: Missing Referenced Docs

- `CONTRIBUTING.md` — referenced in README:207 but doesn't exist
- `ARCHITECTURE.md` — referenced in README:100 but doesn't exist

### IN-04: Ruff Exclude Typo

**File:** `agent/pyproject.toml:62` — `.agent/` should be `.agents/` or removed.

---

_Reviewed: 2026-04-07T22:25:00+07:00_
_Reviewer: Antigravity (GSD Deep Review Protocol)_
_Depth: deep_
