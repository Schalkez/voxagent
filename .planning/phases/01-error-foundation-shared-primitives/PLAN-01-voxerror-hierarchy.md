# Plan 01: VoxError Exception Hierarchy

**Phase:** 01 - Error Foundation & Shared Primitives
**Requirement:** ERRH-01
**Estimated complexity:** Medium (~50 lines of new code + migration across ~10 files)

---

## Objective

Create a custom `VoxError` exception hierarchy with severity levels, user-facing messages, and retry flags. Then migrate all bare `Exception`, `RuntimeError`, `KeyError`, and `OSError` raises in `core/` and `providers/` to use `VoxError` subclasses. This gives every subsequent phase typed error propagation instead of stringly-typed catch blocks.

---

## Step 1: Create `core/errors.py` (NEW FILE)

Create the file `agent/core/errors.py` with the following:

### 1a. ErrorSeverity Enum

```python
class ErrorSeverity(Enum):
    """Severity level for VoxAgent errors."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
```

### 1b. VoxError Base Class

```python
class VoxError(Exception):
    """Base exception for all VoxAgent domain errors.

    Attributes:
        message: Technical error description for logs.
        severity: How bad is this? (info/warning/critical).
        user_message: Human-readable message safe to speak via TTS (Vietnamese).
        retryable: Whether the operation can be retried.
        context: Optional dict of structured context (provider, skill, etc.).
    """

    def __init__(
        self,
        message: str,
        *,
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        user_message: str = "",
        retryable: bool = False,
        context: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.severity = severity
        self.user_message = user_message or "Da co loi xay ra."
        self.retryable = retryable
        self.context = context or {}
```

### 1c. Domain-Specific Subclasses

Define exactly these subclasses (one per domain boundary):

```python
class ProviderError(VoxError):
    """Error from an LLM/STT/TTS/Vision provider."""

    def __init__(
        self,
        message: str,
        *,
        provider_name: str = "",
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        user_message: str = "Khong ket noi duoc nha cung cap.",
        retryable: bool = True,
        context: dict[str, object] | None = None,
    ) -> None:
        ctx = {**(context or {}), "provider": provider_name}
        super().__init__(
            message,
            severity=severity,
            user_message=user_message,
            retryable=retryable,
            context=ctx,
        )
        self.provider_name = provider_name


class ProviderNotAvailableError(ProviderError):
    """Raised when a requested provider is not registered or unreachable."""

    def __init__(self, provider_name: str, available: list[str] | None = None) -> None:
        detail = f"Provider '{provider_name}' not available"
        if available:
            detail += f". Available: {available}"
        super().__init__(
            detail,
            provider_name=provider_name,
            severity=ErrorSeverity.WARNING,
            user_message=f"Khong tim thay nha cung cap {provider_name}.",
            retryable=False,
        )


class AudioError(VoxError):
    """Error in the audio capture/playback pipeline."""

    def __init__(
        self,
        message: str,
        *,
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        user_message: str = "Co loi voi am thanh.",
        retryable: bool = False,
        context: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message,
            severity=severity,
            user_message=user_message,
            retryable=retryable,
            context=context,
        )


class PipelineError(VoxError):
    """Error in the EARS->BRAIN->HANDS->MOUTH pipeline."""

    def __init__(
        self,
        message: str,
        *,
        stage: str = "",
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        user_message: str = "Co loi trong qua trinh xu ly.",
        retryable: bool = False,
        context: dict[str, object] | None = None,
    ) -> None:
        ctx = {**(context or {}), "stage": stage}
        super().__init__(
            message,
            severity=severity,
            user_message=user_message,
            retryable=retryable,
            context=ctx,
        )
        self.stage = stage


class ConfigError(VoxError):
    """Error in configuration loading or validation."""

    def __init__(
        self,
        message: str,
        *,
        severity: ErrorSeverity = ErrorSeverity.CRITICAL,
        user_message: str = "Cau hinh bi loi.",
        retryable: bool = False,
        context: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message,
            severity=severity,
            user_message=user_message,
            retryable=retryable,
            context=context,
        )


class SkillError(VoxError):
    """Error during skill execution."""

    def __init__(
        self,
        message: str,
        *,
        skill_name: str = "",
        severity: ErrorSeverity = ErrorSeverity.WARNING,
        user_message: str = "Khong the thuc hien ky nang nay.",
        retryable: bool = False,
        context: dict[str, object] | None = None,
    ) -> None:
        ctx = {**(context or {}), "skill": skill_name}
        super().__init__(
            message,
            severity=severity,
            user_message=user_message,
            retryable=retryable,
            context=ctx,
        )
        self.skill_name = skill_name
```

### Design Rules

- `VoxError` is the ONLY base exception the codebase should catch at pipeline boundaries.
- Each subclass adds ONE domain-specific attribute (e.g., `provider_name`, `stage`, `skill_name`).
- `user_message` is always Vietnamese, suitable for TTS. English descriptions go in `message`.
- `retryable=True` by default only for `ProviderError` (transient network failures). All others default `False`.
- `context` dict flows into structlog (Plan 02) for structured fields.

---

## Step 2: Migrate `providers/registry.py`

**File:** `agent/providers/registry.py`

### Current state (lines 20-21):
```python
class ProviderNotFoundError(KeyError):
    """Raised when a requested provider is not registered."""
```

### Changes:
1. Keep `ProviderNotFoundError(KeyError)` as a **deprecated alias** for backward compatibility (the API layer and tests reference it).
2. Import `ProviderNotAvailableError` from `core.errors`.
3. In all `get_llm()`, `get_stt()`, `get_tts()`, `get_vision()` methods: raise `ProviderNotAvailableError` instead of `ProviderNotFoundError`.
4. Make `ProviderNotFoundError` a subclass of both `KeyError` and `ProviderNotAvailableError` for isinstance compatibility:

```python
from core.errors import ProviderNotAvailableError

class ProviderNotFoundError(ProviderNotAvailableError, KeyError):
    """Backward-compatible alias. Prefer ProviderNotAvailableError."""

    def __init__(self, msg: str) -> None:
        ProviderNotAvailableError.__init__(self, provider_name="", available=None)
        KeyError.__init__(self, msg)
```

Actually, **simpler approach**: Keep `ProviderNotFoundError` name but change its base class to `ProviderError` while also inheriting `KeyError` for backward compat:

```python
from core.errors import ProviderError, ErrorSeverity

class ProviderNotFoundError(ProviderError, KeyError):
    """Raised when a requested provider is not registered."""

    def __init__(self, msg: str) -> None:
        ProviderError.__init__(
            self,
            msg,
            provider_name="",
            severity=ErrorSeverity.WARNING,
            user_message="Khong tim thay nha cung cap.",
            retryable=False,
        )
```

This keeps all existing `except ProviderNotFoundError` and `except KeyError` catches working.

### In `get_llm_with_fallback()` (line 157-166):
Replace the final `raise ProviderNotFoundError(msg)` with:
```python
raise ProviderNotFoundError(msg)
```
(No change needed since the class itself is now a VoxError subclass.)

---

## Step 3: Migrate `core/brain.py`

**File:** `agent/core/brain.py`

### Changes:

1. **Line 20:** Add import: `from core.errors import PipelineError, ProviderError`
2. **Line 165 (`except Exception as e`):** Currently catches a broad tuple. Replace with VoxError-aware catch:

In `_try_llm_routing()` around line 199:
```python
# BEFORE:
except (ProviderNotFoundError, KeyError, json.JSONDecodeError, TypeError, ValueError) as e:
    logger.error("Failed to extract intent from LLM response: %s", e)

# AFTER:
except ProviderError:
    raise  # Let provider errors propagate for fallback handling
except (KeyError, json.JSONDecodeError, TypeError, ValueError) as e:
    logger.error("Failed to extract intent from LLM response: %s", e)
```

3. **Line 148-149 (fallback to ollama):** Wrap in ProviderError:
```python
# BEFORE:
except ProviderNotFoundError:
    llm = self.registry.get_llm("ollama")

# AFTER:
except ProviderNotFoundError:
    try:
        llm = self.registry.get_llm("ollama")
    except ProviderNotFoundError as fallback_err:
        raise PipelineError(
            "No LLM providers available",
            stage="brain",
            user_message="Khong co mo hinh AI nao san sang.",
        ) from fallback_err
```

4. **Line 165 (screen context):** Catch VoxError instead of bare Exception:
```python
# BEFORE:
except Exception as e:
    logger.warning("Failed to inject screen context: %s", e)

# AFTER:
except (OSError, RuntimeError) as e:
    logger.warning("Failed to inject screen context: %s", e)
```

---

## Step 4: Migrate `core/hands.py`

**File:** `agent/core/hands.py`

### Changes:

1. **Line 16:** Replace `from api.exceptions import VoxAPIException` with `from core.errors import SkillError`.
2. **Line 109 (`except (VoxAPIException, KeyError, ValueError)`):** Replace with:
```python
except (SkillError, KeyError, ValueError) as e:
```
3. **Line 144 (`except (RuntimeError, OSError, TypeError, ValueError)`):** Replace with:
```python
except (VoxError, RuntimeError, OSError, TypeError, ValueError) as exc:
    last_error = f"Tier {tier.value} failed: {exc}"
```
(Import `VoxError` from `core.errors` to catch any VoxError subclass that skills might raise.)

4. **Line 199 (`except (TimeoutError, RuntimeError, OSError)`):** Add VoxError:
```python
except (VoxError, TimeoutError, RuntimeError, OSError):
```

---

## Step 5: Migrate `core/mouth.py`

**File:** `agent/core/mouth.py`

### Changes:

1. Add import: `from core.errors import AudioError`
2. **Line 87-88:** Replace `except (RuntimeError, OSError)` with:
```python
except (AudioError, RuntimeError, OSError):
    logger.exception("Failed to speak: '%s'", text[:50])
```
3. **`_play_wav()` line 152-153:** Wrap playback failure in AudioError:
```python
except (OSError, ValueError, wave.Error) as e:
    raise AudioError(
        f"Audio playback failed: {e}",
        user_message="Khong the phat am thanh.",
    ) from e
```

---

## Step 6: Migrate `core/ears.py`

**File:** `agent/core/ears.py`

### Changes:

1. Add import: `from core.errors import AudioError, PipelineError`
2. **`_ensure_started()` line 219:** Replace `raise RuntimeError(...)` with:
```python
raise PipelineError(
    "Ears not started. Call start_listening() first.",
    stage="ears",
    user_message="He thong nghe chua san sang.",
)
```
3. **`start_listening()`:** Wrap potential RuntimeError from recorder:
```python
try:
    await self._recorder.start()
except (RuntimeError, OSError) as e:
    raise AudioError(
        f"Failed to start microphone: {e}",
        user_message="Khong the khoi dong micro.",
    ) from e
```

---

## Step 7: Migrate `core/eyes.py`

**File:** `agent/core/eyes.py`

### Changes:

1. Add import: `from core.errors import PipelineError, ProviderError`
2. **Line 102-104 (`except (NotImplementedError, OSError, RuntimeError)`):** Keep as-is (graceful degradation to empty WindowInfo is correct behavior).
3. **Line 248 (`except (KeyError, RuntimeError, ConnectionError)`):** Replace with:
```python
except (ProviderError, KeyError, RuntimeError, ConnectionError) as e:
    logger.warning("Vision analysis failed: %s", e)
    return f"Vision analysis failed: {e}"
```

---

## Step 8: Migrate `core/app.py`

**File:** `agent/core/app.py`

### Changes:

1. Add import: `from core.errors import VoxError`
2. **Line 281 (`except (RuntimeError, OSError, KeyError)`):** Replace with:
```python
except VoxError as ve:
    logger.error("Pipeline error (stage=%s): %s", ve.context.get("stage", "unknown"), ve)
    if ve.user_message:
        await self._mouth.speak(ve.user_message)
    await asyncio.sleep(0.5)
except (RuntimeError, OSError, KeyError):
    logger.exception("Unexpected error in main loop")
    await asyncio.sleep(0.5)
```

This is the **key pipeline boundary** where VoxErrors are caught, logged with context, and spoken to the user.

---

## Step 9: Update `skills/registry.py`

**File:** `agent/skills/registry.py`

### Changes:

1. **Line 5:** Replace `from api.exceptions import VoxAPIException` with `from core.errors import SkillError`.
2. **Lines 49-53:** Replace `raise VoxAPIException(...)` with:
```python
raise SkillError(
    f"Skill '{name}' not found in registry.",
    skill_name=name,
    user_message="Toi khong tim thay ky nang nay.",
)
```

This removes the cross-boundary import from `skills/` -> `api/` (skills layer should not import from api layer per architecture rules in CONVENTIONS.md).

---

## Step 10: Write Tests

**File:** `tests/test_errors.py` (NEW FILE)

```python
"""Tests for VoxError hierarchy."""

import pytest

from core.errors import (
    AudioError,
    ConfigError,
    ErrorSeverity,
    PipelineError,
    ProviderError,
    SkillError,
    VoxError,
)


class TestVoxError:
    """Tests for the base VoxError class."""

    def test_basic_creation(self) -> None:
        err = VoxError("something broke")
        assert str(err) == "something broke"
        assert err.severity == ErrorSeverity.WARNING
        assert err.retryable is False
        assert err.context == {}

    def test_custom_fields(self) -> None:
        err = VoxError(
            "network timeout",
            severity=ErrorSeverity.CRITICAL,
            user_message="Loi mang.",
            retryable=True,
            context={"provider": "openai"},
        )
        assert err.severity == ErrorSeverity.CRITICAL
        assert err.user_message == "Loi mang."
        assert err.retryable is True
        assert err.context["provider"] == "openai"

    def test_is_exception(self) -> None:
        assert issubclass(VoxError, Exception)

    def test_can_be_caught_as_exception(self) -> None:
        with pytest.raises(Exception):
            raise VoxError("test")


class TestProviderError:
    """Tests for ProviderError subclass."""

    def test_default_retryable(self) -> None:
        err = ProviderError("timeout", provider_name="openai")
        assert err.retryable is True
        assert err.provider_name == "openai"
        assert err.context["provider"] == "openai"

    def test_inherits_voxerror(self) -> None:
        err = ProviderError("test", provider_name="groq")
        assert isinstance(err, VoxError)


class TestPipelineError:
    def test_stage_in_context(self) -> None:
        err = PipelineError("bad state", stage="brain")
        assert err.stage == "brain"
        assert err.context["stage"] == "brain"


class TestSkillError:
    def test_skill_name_in_context(self) -> None:
        err = SkillError("crash", skill_name="terminal")
        assert err.skill_name == "terminal"
        assert err.context["skill"] == "terminal"


class TestAudioError:
    def test_default_not_retryable(self) -> None:
        err = AudioError("mic disconnected")
        assert err.retryable is False


class TestConfigError:
    def test_default_critical(self) -> None:
        err = ConfigError("missing yaml key")
        assert err.severity == ErrorSeverity.CRITICAL


class TestErrorHierarchy:
    """Verify isinstance relationships for catch blocks."""

    def test_provider_error_caught_by_voxerror(self) -> None:
        with pytest.raises(VoxError):
            raise ProviderError("test", provider_name="x")

    def test_pipeline_error_caught_by_voxerror(self) -> None:
        with pytest.raises(VoxError):
            raise PipelineError("test", stage="y")

    def test_skill_error_caught_by_voxerror(self) -> None:
        with pytest.raises(VoxError):
            raise SkillError("test", skill_name="z")

    def test_audio_error_caught_by_voxerror(self) -> None:
        with pytest.raises(VoxError):
            raise AudioError("test")
```

---

## Verification

After all changes:

1. `ruff check agent/core/errors.py` -- no lint errors
2. `mypy agent/core/errors.py` -- passes strict mode
3. `pytest tests/test_errors.py -v` -- all tests pass
4. `pytest tests/ -v` -- existing tests still pass (zero regressions)
5. `grep -rn "raise Exception\|raise RuntimeError" agent/core/ agent/providers/` -- should return zero matches in modified files

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `agent/core/errors.py` | CREATE | VoxError hierarchy (~100 lines) |
| `agent/providers/registry.py` | MODIFY | ProviderNotFoundError inherits ProviderError + KeyError |
| `agent/core/brain.py` | MODIFY | Import VoxError types, typed catches |
| `agent/core/hands.py` | MODIFY | Replace VoxAPIException import, typed catches |
| `agent/core/mouth.py` | MODIFY | AudioError wrapping |
| `agent/core/ears.py` | MODIFY | PipelineError + AudioError raises |
| `agent/core/eyes.py` | MODIFY | ProviderError in vision catches |
| `agent/core/app.py` | MODIFY | VoxError catch at pipeline boundary with user_message speak |
| `agent/skills/registry.py` | MODIFY | Replace VoxAPIException with SkillError |
| `tests/test_errors.py` | CREATE | 15+ test cases for hierarchy |
