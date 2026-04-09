# Plan 03: Standardized SkillResult Error Format

**Phase:** 01 - Error Foundation & Shared Primitives
**Requirement:** ERRH-05
**Depends on:** Plan 01 (VoxError hierarchy -- `SkillError` and `ErrorSeverity` used in SkillResult)
**Estimated complexity:** Low (~20 lines of changes to SkillResult + migration across ~10 skill files)

---

## Objective

Extend the existing `SkillResult` dataclass with typed error fields (`error_code`, `error_severity`, `retryable`) so all skills return structured, machine-readable error information. Then migrate every skill implementation to use these fields consistently. No skill should return raw strings as errors or raise untyped exceptions past the skill boundary.

---

## Step 1: Extend `SkillResult` in `skills/base.py`

**File:** `agent/skills/base.py`

### Current SkillResult (lines 33-51):

```python
@dataclass(frozen=True)
class SkillResult:
    success: bool
    tts_response: str = ""
    data: dict[str, object] = field(default_factory=dict)
    error: str | None = None
    cancelled: bool = False
    tier_used: ExecutionTier | None = None
```

### New SkillResult:

Add three new fields. Import `ErrorSeverity` from `core.errors`. The new fields have defaults to maintain backward compatibility (all existing call sites continue working unchanged).

```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from core.errors import ErrorSeverity


class ExecutionTier(Enum):
    # ... (unchanged)


@dataclass(frozen=True)
class SkillResult:
    """Result returned by a skill execution.

    Attributes:
        success: Whether the skill completed successfully.
        tts_response: Text for the MOUTH module to speak.
        data: Optional structured data from the skill.
        error: Error message if the skill failed (technical, for logs).
        error_code: Machine-readable error code (e.g., 'command_blocked', 'timeout').
        error_severity: Severity level from ErrorSeverity enum.
        retryable: Whether the failed operation can be retried.
        cancelled: True if the user cancelled a dangerous action.
        tier_used: Which execution tier was used.
    """

    success: bool
    tts_response: str = ""
    data: dict[str, object] = field(default_factory=dict)
    error: str | None = None
    error_code: str = ""
    error_severity: str = "warning"  # Use string to avoid import at runtime; values: "info", "warning", "critical"
    retryable: bool = False
    cancelled: bool = False
    tier_used: ExecutionTier | None = None
```

### Design Decisions

1. **`error_code`** is a `str`, not an enum -- skills can define their own codes without a central registry. Convention: `snake_case`, e.g. `"command_blocked"`, `"provider_unavailable"`, `"permission_denied"`, `"timeout"`, `"unsupported_action"`, `"not_found"`.
2. **`error_severity`** is a `str` (not `ErrorSeverity` enum) to avoid a runtime import from `core.errors` in `skills/base.py`. Values match `ErrorSeverity`: `"info"`, `"warning"`, `"critical"`. This avoids a cross-layer import (`skills/` -> `core/`). Skills that need the enum can import it for their own logic.
3. **`retryable`** defaults to `False` for safety -- a skill must explicitly opt-in to retry.
4. All three new fields have defaults, so **every existing `SkillResult(...)` call site continues working unchanged** with zero modifications required.
5. Field ordering: new fields go after `error` and before `cancelled` to group error-related fields together.

### Add a convenience constructor (static method):

```python
@dataclass(frozen=True)
class SkillResult:
    # ... fields as above ...

    @staticmethod
    def ok(
        tts_response: str = "",
        data: dict[str, object] | None = None,
        tier_used: ExecutionTier | None = None,
    ) -> SkillResult:
        """Create a successful SkillResult.

        Args:
            tts_response: Text for TTS to speak.
            data: Optional structured output data.
            tier_used: Which execution tier succeeded.

        Returns:
            A SkillResult with success=True.
        """
        return SkillResult(
            success=True,
            tts_response=tts_response,
            data=data or {},
            tier_used=tier_used,
        )

    @staticmethod
    def fail(
        error: str,
        *,
        tts_response: str = "",
        error_code: str = "",
        error_severity: str = "warning",
        retryable: bool = False,
        data: dict[str, object] | None = None,
        tier_used: ExecutionTier | None = None,
    ) -> SkillResult:
        """Create a failed SkillResult with structured error info.

        Args:
            error: Technical error message for logs.
            tts_response: User-facing Vietnamese message for TTS.
            error_code: Machine-readable error code.
            error_severity: Severity level ('info', 'warning', 'critical').
            retryable: Whether the operation can be retried.
            data: Optional structured data (e.g., partial results).
            tier_used: Which execution tier was attempted.

        Returns:
            A SkillResult with success=False and typed error fields.
        """
        return SkillResult(
            success=False,
            tts_response=tts_response,
            data=data or {},
            error=error,
            error_code=error_code,
            error_severity=error_severity,
            retryable=retryable,
            tier_used=tier_used,
        )
```

These static methods are optional sugar -- skills can still use the raw constructor. But they enforce consistency and make the intent clear.

---

## Step 2: Define standard error codes

**File:** `agent/skills/base.py` -- add constants after the ExecutionTier enum

```python
# -- Standard Skill Error Codes --
# Skills may define custom codes; these are the shared conventions.
SKILL_ERR_UNSUPPORTED_ACTION = "unsupported_action"
SKILL_ERR_PERMISSION_DENIED = "permission_denied"
SKILL_ERR_NOT_FOUND = "not_found"
SKILL_ERR_TIMEOUT = "timeout"
SKILL_ERR_COMMAND_BLOCKED = "command_blocked"
SKILL_ERR_INVALID_PARAMS = "invalid_params"
SKILL_ERR_PLATFORM_UNSUPPORTED = "platform_unsupported"
SKILL_ERR_PROVIDER_UNAVAILABLE = "provider_unavailable"
SKILL_ERR_CANCELLED = "cancelled"
```

---

## Step 3: Migrate `core/hands.py` to use new error fields

**File:** `agent/core/hands.py`

### 3a. Line 99-104 (cancelled result):

```python
# BEFORE:
return SkillResult(
    success=False,
    error="User cancelled dangerous action",
    cancelled=True,
    tts_response="Da huy thao tac.",
)

# AFTER:
return SkillResult.fail(
    error="User cancelled dangerous action",
    tts_response="Da huy thao tac.",
    error_code=SKILL_ERR_CANCELLED,
    error_severity="info",
)
# Note: cancelled flag is no longer needed since error_code="cancelled" conveys the same info.
# But keep cancelled=True for backward compat if anything checks it.
# Actually, SkillResult.fail() doesn't set cancelled. Use raw constructor:
return SkillResult(
    success=False,
    error="User cancelled dangerous action",
    error_code="cancelled",
    error_severity="info",
    cancelled=True,
    tts_response="Da huy thao tac.",
)
```

### 3b. Lines 110-114 (skill not found):

```python
# BEFORE:
return SkillResult(
    success=False,
    error=str(e),
    tts_response="Toi khong tim thay ky nang nay.",
)

# AFTER:
return SkillResult.fail(
    error=str(e),
    tts_response="Toi khong tim thay ky nang nay.",
    error_code="not_found",
)
```

### 3c. Lines 123-126 (permission denied):

```python
# BEFORE:
return SkillResult(
    success=False,
    error=f"Permission denied: {names}",
    tts_response="Ky nang nay can quyen truy cap nguy hiem ma chua duoc cap.",
)

# AFTER:
return SkillResult.fail(
    error=f"Permission denied: {names}",
    tts_response="Ky nang nay can quyen truy cap nguy hiem ma chua duoc cap.",
    error_code="permission_denied",
    error_severity="warning",
)
```

### 3d. Lines 131-133 (can't handle):

```python
# AFTER:
return SkillResult.fail(
    error="Skill assigned could not handle the intent.",
    error_code="unsupported_action",
)
```

### 3e. Lines 149-154 (tier failures):

```python
# AFTER:
return SkillResult.fail(
    error=last_error or "No execution tier succeeded",
    tts_response="Da co loi xay ra trong qua trinh thao tac.",
    error_code="tier_exhausted",
)
```

### 3f. Lines 156-160 (no tier succeeded):

```python
# AFTER:
return SkillResult.fail(
    error="No execution tier succeeded",
    tts_response="Khong the thuc hien lenh nay.",
    error_code="tier_exhausted",
)
```

---

## Step 4: Migrate `skills/media_control.py`

**File:** `agent/skills/media_control.py`

### 4a. Line 109-114 (unsupported action):

```python
# BEFORE:
return SkillResult(
    success=False,
    error=f"Hanh dong '{action}' khong ho tro boi media_control.",
    tier_used=ExecutionTier.NATIVE_API,
)

# AFTER:
return SkillResult.fail(
    error=f"Unsupported action: {action}",
    tts_response=f"Hanh dong '{action}' khong ho tro boi media_control.",
    error_code="unsupported_action",
    tier_used=ExecutionTier.NATIVE_API,
)
```

### 4b. Lines 119-123 (success):

```python
# BEFORE:
return SkillResult(
    success=True,
    tts_response=f"Da {description} roi nha.",
    tier_used=ExecutionTier.NATIVE_API,
)

# AFTER:
return SkillResult.ok(
    tts_response=f"Da {description} roi nha.",
    tier_used=ExecutionTier.NATIVE_API,
)
```

### 4c. Lines 125-130 (platform not supported):

```python
# AFTER:
return SkillResult.fail(
    error="Media key simulation not available on this platform.",
    tts_response="Khong the dieu khien media tren nen tang nay.",
    error_code="platform_unsupported",
    tier_used=ExecutionTier.NATIVE_API,
)
```

---

## Step 5: Migrate `skills/terminal.py`

**File:** `agent/skills/terminal.py`

### 5a. Lines 105-109 (unsupported action):

```python
return SkillResult.fail(
    error=f"Unsupported action: {action}",
    tts_response=f"Hanh dong '{action}' khong ho tro boi terminal.",
    error_code="unsupported_action",
    tier_used=ExecutionTier.SHELL,
)
```

### 5b. Lines 121-126 (no command):

```python
return SkillResult.fail(
    error="No command provided.",
    tts_response="Anh muon chay lenh gi?",
    error_code="invalid_params",
    tier_used=ExecutionTier.SHELL,
)
```

### 5c. Lines 128-134 (command blocked):

```python
return SkillResult.fail(
    error=f"Command blocked by safety filter: {command}",
    tts_response="Lenh nay bi chan vi ly do an toan.",
    error_code="command_blocked",
    error_severity="warning",
    tier_used=ExecutionTier.SHELL,
)
```

### 5d. Lines 154-162 (success):

```python
return SkillResult.ok(
    tts_response="Da chay lenh thanh cong.",
    data={"stdout": stdout, "stderr": stderr, "returncode": str(result.returncode)},
    tier_used=ExecutionTier.SHELL,
)
```

### 5e. Lines 164-170 (command failed):

```python
return SkillResult.fail(
    error=f"Exit code {result.returncode}: {stderr or stdout}",
    tts_response="Lenh chay khong thanh cong.",
    error_code="command_failed",
    data={"stdout": stdout, "stderr": stderr, "returncode": str(result.returncode)},
    tier_used=ExecutionTier.SHELL,
)
```

### 5f. Lines 173-179 (timeout):

```python
return SkillResult.fail(
    error=f"Command timed out after {COMMAND_TIMEOUT_S}s",
    tts_response="Lenh da qua thoi gian cho.",
    error_code="timeout",
    tier_used=ExecutionTier.SHELL,
)
```

### 5g. Lines 180-186 (OS error):

```python
return SkillResult.fail(
    error=str(e),
    tts_response="Khong the chay lenh nay.",
    error_code="execution_error",
    tier_used=ExecutionTier.SHELL,
)
```

---

## Step 6: Migrate `skills/file_manager.py`

**File:** `agent/skills/file_manager.py`

Apply the same pattern to all `SkillResult` returns in this file:

- Success cases: use `SkillResult.ok(...)`
- Error cases: use `SkillResult.fail(error=..., error_code=..., tts_response=...)`

Error codes to use:
- `"unsupported_action"` -- unknown action
- `"invalid_params"` -- missing path/query
- `"permission_denied"` -- PermissionError catches
- `"not_found"` -- FileNotFoundError catches
- `"io_error"` -- generic OSError catches

Example for `_list_dir` (line 103-106):

```python
# BEFORE:
return SkillResult(
    success=False,
    error=f"Not a directory: {target}",
    tts_response="Duong dan khong phai la thu muc.",
    tier_used=ExecutionTier.NATIVE_API,
)

# AFTER:
return SkillResult.fail(
    error=f"Not a directory: {target}",
    tts_response="Duong dan khong phai la thu muc.",
    error_code="invalid_params",
    tier_used=ExecutionTier.NATIVE_API,
)
```

---

## Step 7: Migrate remaining skills

Apply the same mechanical transformation to:

- `agent/skills/app_launcher.py`
- `agent/skills/browser_control.py`
- `agent/skills/code_reviewer.py`
- `agent/skills/system_control.py`
- `agent/skills/system_skill.py`
- `agent/skills/screen_reader.py`
- `agent/skills/marketplace.py`

For each file:
1. Read the file to identify all `SkillResult(...)` calls
2. Success cases -> `SkillResult.ok(...)`
3. Error cases -> `SkillResult.fail(error=..., error_code=..., tts_response=...)`
4. Choose the appropriate error_code from the standard codes or create a skill-specific one

---

## Step 8: Update tests

### 8a. Extend `tests/test_skills.py`

**File:** `tests/test_skills.py`

Add tests for the new fields and convenience methods:

```python
class TestSkillResultNewFields:
    """Tests for the new typed error fields."""

    def test_error_code_default_empty(self) -> None:
        result = SkillResult(success=False, error="something")
        assert result.error_code == ""

    def test_error_severity_default_warning(self) -> None:
        result = SkillResult(success=False, error="something")
        assert result.error_severity == "warning"

    def test_retryable_default_false(self) -> None:
        result = SkillResult(success=False, error="something")
        assert result.retryable is False

    def test_retryable_explicit_true(self) -> None:
        result = SkillResult(success=False, error="timeout", retryable=True)
        assert result.retryable is True

    def test_backward_compat_no_new_fields(self) -> None:
        """Existing code that doesn't use new fields should still work."""
        result = SkillResult(success=True, tts_response="Done!")
        assert result.error_code == ""
        assert result.error_severity == "warning"
        assert result.retryable is False


class TestSkillResultOk:
    """Tests for SkillResult.ok() convenience method."""

    def test_basic_ok(self) -> None:
        result = SkillResult.ok(tts_response="Done!")
        assert result.success is True
        assert result.tts_response == "Done!"
        assert result.error is None

    def test_ok_with_data(self) -> None:
        result = SkillResult.ok(data={"key": "value"})
        assert result.data == {"key": "value"}

    def test_ok_with_tier(self) -> None:
        result = SkillResult.ok(tier_used=ExecutionTier.NATIVE_API)
        assert result.tier_used == ExecutionTier.NATIVE_API


class TestSkillResultFail:
    """Tests for SkillResult.fail() convenience method."""

    def test_basic_fail(self) -> None:
        result = SkillResult.fail(error="broke")
        assert result.success is False
        assert result.error == "broke"

    def test_fail_with_code(self) -> None:
        result = SkillResult.fail(
            error="timeout",
            error_code="timeout",
            error_severity="warning",
            retryable=True,
        )
        assert result.error_code == "timeout"
        assert result.error_severity == "warning"
        assert result.retryable is True

    def test_fail_with_tts(self) -> None:
        result = SkillResult.fail(
            error="blocked",
            tts_response="Lenh bi chan.",
            error_code="command_blocked",
        )
        assert result.tts_response == "Lenh bi chan."
```

---

## Verification

After all changes:

1. `ruff check agent/skills/base.py` -- no lint errors
2. `mypy agent/skills/base.py` -- passes strict mode
3. `pytest tests/test_skills.py -v` -- all tests pass (old + new)
4. `pytest tests/ -v` -- zero regressions in existing tests
5. Verify no skill returns a raw string or dict instead of SkillResult:
   ```
   grep -rn "return \"" agent/skills/ --include="*.py" | grep -v "def \|#\|docstring"
   ```
   Should return no matches.
6. Verify all skill error returns use error_code:
   ```
   grep -rn "SkillResult.fail\|SkillResult(success=False" agent/skills/ --include="*.py"
   ```
   Each match should include `error_code=`.

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `agent/skills/base.py` | MODIFY | Add `error_code`, `error_severity`, `retryable` fields + `ok()`/`fail()` static methods + error code constants |
| `agent/core/hands.py` | MODIFY | Use SkillResult.fail() with error_codes for all error returns |
| `agent/skills/media_control.py` | MODIFY | Migrate to SkillResult.ok()/fail() with error_codes |
| `agent/skills/terminal.py` | MODIFY | Migrate to SkillResult.ok()/fail() with error_codes |
| `agent/skills/file_manager.py` | MODIFY | Migrate to SkillResult.ok()/fail() with error_codes |
| `agent/skills/app_launcher.py` | MODIFY | Migrate to SkillResult.ok()/fail() with error_codes |
| `agent/skills/browser_control.py` | MODIFY | Migrate to SkillResult.ok()/fail() with error_codes |
| `agent/skills/code_reviewer.py` | MODIFY | Migrate to SkillResult.ok()/fail() with error_codes |
| `agent/skills/system_control.py` | MODIFY | Migrate to SkillResult.ok()/fail() with error_codes |
| `agent/skills/system_skill.py` | MODIFY | Migrate to SkillResult.ok()/fail() with error_codes |
| `agent/skills/screen_reader.py` | MODIFY | Migrate to SkillResult.ok()/fail() with error_codes |
| `agent/skills/marketplace.py` | MODIFY | Migrate to SkillResult.ok()/fail() with error_codes |
| `tests/test_skills.py` | MODIFY | Add 12+ tests for new fields and convenience methods |

---

## Incremental Adoption Note (Pitfall P5)

Per research pitfall P5: "Error hierarchy must be adopted incrementally, not defined and forgotten."

This plan can be executed in two passes:
1. **Pass 1 (blocking):** Modify `skills/base.py` to add new fields + update `hands.py` + update `test_skills.py`. This establishes the contract.
2. **Pass 2 (non-blocking):** Migrate each skill file one at a time. Since all new fields have defaults, skills that haven't been migrated yet continue working. The migration can be verified per-file.

This ensures no big-bang change that breaks everything at once.
