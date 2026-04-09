# Plan 02: Structured Logging via structlog

**Phase:** 01 - Error Foundation & Shared Primitives
**Requirement:** ERRH-04
**Depends on:** Plan 01 (VoxError hierarchy -- uses `VoxError.context` for structured fields)
**Estimated complexity:** Low (~30 lines of config + find-and-replace across ~10 modules)

---

## Objective

Replace `logging.getLogger("voxagent.*")` with `structlog` across all modules modified in Plan 01. Log output must include structured fields: `provider`, `skill`, `latency`, and any context from `VoxError.context`. The stdlib `logging` integration mode is used so existing log handlers (file, console) continue working unchanged.

---

## Step 1: Add structlog dependency to `pyproject.toml`

**File:** `agent/pyproject.toml`

### Changes at line 9 (dependencies list):

Add `"structlog>=25.5.0"` to the `dependencies` list. Insert it alphabetically near the end:

```toml
dependencies = [
    "sounddevice>=0.5.1",
    "numpy>=1.26",
    "keyring>=25.0",
    "pydantic>=2.9",
    "aiosqlite>=0.20",
    "httpx>=0.28",
    "pyyaml>=6.0",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "edge-tts>=6.1",
    "pydub>=0.25",
    "psutil>=5.9",
    "pystray>=0.19",
    "Pillow>=10.0",
    "structlog>=25.5.0",
]
```

Also add `"structlog"` to the mypy overrides if needed (structlog ships types, so this may not be necessary -- verify after install).

---

## Step 2: Create `core/logging.py` (NEW FILE)

**File:** `agent/core/logging.py`

This is the single-point structlog configuration module. It configures structlog to wrap stdlib logging so all existing handlers/formatters continue working.

```python
"""Structured logging configuration for VoxAgent.

Configures structlog to wrap the stdlib logging module.
All modules should use `get_logger()` from this module instead
of `logging.getLogger()`.

Usage:
    from core.logging import get_logger
    logger = get_logger()
    logger.info("transcription complete", provider="whisper", latency_ms=245)
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(*, debug: bool = False) -> None:
    """Configure structlog + stdlib logging for the entire application.

    Must be called once at application startup (in app.py or server.py)
    before any logger is used.

    Args:
        debug: If True, set log level to DEBUG and use ConsoleRenderer
               for human-readable dev output. If False, use JSON renderer
               for production.
    """
    log_level = logging.DEBUG if debug else logging.INFO

    # Configure stdlib root logger
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        stream=sys.stderr,
        force=True,
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if debug:
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(
            colors=True,
        )
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Also configure a formatter for stdlib handlers to use structlog processing
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # Apply formatter to all existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)


def get_logger(**initial_context: object) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        **initial_context: Key-value pairs to bind to every log entry
                          from this logger (e.g., module="brain").

    Returns:
        A structlog BoundLogger that supports .info(), .warning(), etc.
        with keyword arguments for structured fields.

    Example:
        logger = get_logger(module="brain")
        logger.info("intent resolved", skill="media_control", latency_ms=42)
    """
    return structlog.get_logger(**initial_context)
```

### Design Decisions

- **stdlib integration mode**: structlog wraps stdlib `logging`, so all existing handlers (file rotation, external log collectors) keep working.
- **`merge_contextvars`**: Enables `structlog.contextvars.bind_contextvars(provider="openai")` at request boundaries, automatically included in all log entries within that context.
- **JSON in production, Console in debug**: `debug=True` gives colorized human-readable output; `debug=False` gives machine-parseable JSON.
- **`get_logger()`**: Single import replaces `logging.getLogger("voxagent.xyz")`. The module name is auto-detected by structlog.

---

## Step 3: Wire `configure_logging()` into application startup

### 3a. `core/app.py`

**File:** `agent/core/app.py`

Replace the `logging.basicConfig()` call in `main()` (line 321-324):

```python
# BEFORE (lines 321-324):
logging.basicConfig(
    level=logging.DEBUG if getattr(args, "debug", False) else logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

# AFTER:
from core.logging import configure_logging
configure_logging(debug=getattr(args, "debug", False))
```

Remove `import logging` from top-level imports if it becomes unused (it's still used for `logging.DEBUG` check, but that's handled by `configure_logging` now).

### 3b. `api/server.py`

If `api/server.py` has its own `logging.basicConfig()`, replace it similarly. Read the file first to verify.

---

## Step 4: Migrate logger instances in modified modules

Replace `logging.getLogger("voxagent.X")` with `get_logger()` in all modules touched by Plan 01. The migration is mechanical:

### 4a. `core/brain.py`

```python
# BEFORE (line 13, 26):
import logging
logger = logging.getLogger("voxagent.brain")

# AFTER:
from core.logging import get_logger
logger = get_logger(module="brain")
```

**Usage changes in brain.py:**

```python
# BEFORE (line 165):
logger.warning("Failed to inject screen context: %s", e)

# AFTER:
logger.warning("failed to inject screen context", error=str(e))
```

```python
# BEFORE (line 201):
logger.error("Failed to extract intent from LLM response: %s", e)

# AFTER:
logger.error("failed to extract intent from LLM response", error=str(e), tier=target_tier.value)
```

### 4b. `core/hands.py`

```python
# BEFORE (line 14, 25):
import logging
logger = logging.getLogger("voxagent.hands")

# AFTER:
from core.logging import get_logger
logger = get_logger(module="hands")
```

**Usage changes:**

```python
# BEFORE (line 121):
logger.warning("Skill '%s' blocked — missing dangerous permissions: %s", skill.name, names)

# AFTER:
logger.warning("skill blocked — missing dangerous permissions", skill=skill.name, permissions=names)
```

```python
# BEFORE (line 139):
logger.debug("Trying tier %s for skill %s", tier.value, skill.name)

# AFTER:
logger.debug("trying execution tier", tier=tier.value, skill=skill.name)
```

### 4c. `core/mouth.py`

```python
# BEFORE (line 11, 21):
import logging
logger = logging.getLogger("voxagent.mouth")

# AFTER:
from core.logging import get_logger
logger = get_logger(module="mouth")
```

**Usage changes:**

```python
# BEFORE (line 86):
logger.debug("Spoke: '%s' (voice=%s)", text[:50], cfg.voice)

# AFTER:
logger.debug("spoke", text=text[:50], voice=cfg.voice)
```

### 4d. `core/ears.py`

```python
# BEFORE (line 12, 29):
import logging
logger = logging.getLogger("voxagent.ears")

# AFTER:
from core.logging import get_logger
logger = get_logger(module="ears")
```

**Usage changes:**

```python
# BEFORE (line 184):
logger.info("Wake word detected — recording speech")

# AFTER:
logger.info("wake word detected — recording speech")
```

```python
# BEFORE (line 285):
logger.info("Transcription: '%s' (confidence=%.2f)", result.text, result.confidence)

# AFTER:
logger.info("transcription complete", text=result.text, confidence=result.confidence, duration_ms=duration_ms)
```

### 4e. `core/eyes.py`

```python
# BEFORE (line 11, 16):
import logging
logger = logging.getLogger("voxagent.eyes")

# AFTER:
from core.logging import get_logger
logger = get_logger(module="eyes")
```

### 4f. `core/app.py`

```python
# BEFORE (line 14, 30):
import logging
logger = logging.getLogger("voxagent.app")

# AFTER:
from core.logging import get_logger
logger = get_logger(module="app")
```

### 4g. `providers/registry.py`

This file does not currently have a logger. Add one:

```python
from core.logging import get_logger

logger = get_logger(module="providers.registry")
```

Use it in `get_llm_with_fallback()` to log provider attempts:
```python
logger.info("trying fallback provider", provider=name)
```

### 4h. `skills/registry.py`

```python
# BEFORE (line 4, 14):
import logging
logger = logging.getLogger("voxagent.skills")

# AFTER:
from core.logging import get_logger
logger = get_logger(module="skills.registry")
```

### 4i. `skills/permissions.py`

```python
# BEFORE (line 9, 15):
import logging
logger = logging.getLogger("voxagent.skills.permissions")

# AFTER:
from core.logging import get_logger
logger = get_logger(module="skills.permissions")
```

---

## Step 5: Add latency logging at pipeline boundaries

**File:** `agent/core/app.py` -- `_run_loop()` method (line 236-283)

Add timing instrumentation around the pipeline stages:

```python
import time

# Inside the while loop:
t0 = time.monotonic()
intent = await self._brain.process(transcription.text)
brain_latency_ms = int((time.monotonic() - t0) * 1000)
logger.info("intent resolved", skill=intent.skill_name, action=intent.action, tier=intent.tier_used.value, latency_ms=brain_latency_ms)

t0 = time.monotonic()
result = await self._hands.execute(skill_intent)
hands_latency_ms = int((time.monotonic() - t0) * 1000)
logger.info("skill executed", skill=intent.skill_name, success=result.success, latency_ms=hands_latency_ms)
```

Also bind request-scoped context vars per command:

```python
import structlog

# At the top of each loop iteration:
structlog.contextvars.clear_contextvars()
structlog.contextvars.bind_contextvars(command=transcription.text[:100])
```

---

## Step 6: Add structlog context in VoxError catch blocks

**File:** `agent/core/app.py`

In the VoxError catch block added by Plan 01:

```python
except VoxError as ve:
    logger.error(
        "pipeline error",
        error=str(ve),
        severity=ve.severity.value,
        retryable=ve.retryable,
        **ve.context,
    )
    if ve.user_message:
        await self._mouth.speak(ve.user_message)
    await asyncio.sleep(0.5)
```

This unpacks `ve.context` (which includes `provider`, `skill`, `stage` depending on the subclass) directly into the structured log entry.

---

## Step 7: Write Tests

**File:** `tests/test_logging.py` (NEW FILE)

```python
"""Tests for structured logging configuration."""

import logging

import structlog
import pytest

from core.logging import configure_logging, get_logger


class TestConfigureLogging:
    """Tests for logging configuration."""

    def test_configures_without_error(self) -> None:
        """configure_logging should not raise."""
        configure_logging(debug=True)

    def test_debug_mode_sets_debug_level(self) -> None:
        configure_logging(debug=True)
        assert logging.getLogger().level == logging.DEBUG

    def test_production_mode_sets_info_level(self) -> None:
        configure_logging(debug=False)
        assert logging.getLogger().level == logging.INFO


class TestGetLogger:
    """Tests for the get_logger factory."""

    def test_returns_bound_logger(self) -> None:
        configure_logging(debug=True)
        logger = get_logger(module="test")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_bound_context_persists(self) -> None:
        configure_logging(debug=True)
        logger = get_logger(module="test_module")
        # Should not raise — structured fields are accepted
        logger.info("test event", provider="openai", latency_ms=42)

    def test_multiple_loggers_independent(self) -> None:
        configure_logging(debug=True)
        logger_a = get_logger(module="a")
        logger_b = get_logger(module="b")
        # Both should work independently
        logger_a.info("from a")
        logger_b.info("from b")


class TestContextVars:
    """Tests for request-scoped context variables."""

    def test_bind_and_clear(self) -> None:
        configure_logging(debug=True)
        structlog.contextvars.bind_contextvars(request_id="abc123")
        structlog.contextvars.clear_contextvars()
        # After clear, context should be empty (no assertion needed, just no crash)
```

---

## Verification

After all changes:

1. `pip install structlog>=25.5.0` -- installs cleanly
2. `ruff check agent/core/logging.py` -- no lint errors
3. `mypy agent/core/logging.py` -- passes strict mode
4. `pytest tests/test_logging.py -v` -- all tests pass
5. `pytest tests/ -v` -- existing tests still pass (zero regressions)
6. `grep -rn "logging.getLogger" agent/core/brain.py agent/core/hands.py agent/core/mouth.py agent/core/ears.py agent/core/eyes.py agent/core/app.py` -- should return zero matches (all replaced with `get_logger()`)

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `agent/pyproject.toml` | MODIFY | Add `structlog>=25.5.0` to dependencies |
| `agent/core/logging.py` | CREATE | structlog config + `get_logger()` factory (~70 lines) |
| `agent/core/app.py` | MODIFY | Replace `logging.basicConfig()` with `configure_logging()`, add latency instrumentation, add context vars |
| `agent/core/brain.py` | MODIFY | Replace `logging.getLogger()` with `get_logger()`, structured log calls |
| `agent/core/hands.py` | MODIFY | Replace `logging.getLogger()` with `get_logger()`, structured log calls |
| `agent/core/mouth.py` | MODIFY | Replace `logging.getLogger()` with `get_logger()`, structured log calls |
| `agent/core/ears.py` | MODIFY | Replace `logging.getLogger()` with `get_logger()`, structured log calls |
| `agent/core/eyes.py` | MODIFY | Replace `logging.getLogger()` with `get_logger()`, structured log calls |
| `agent/providers/registry.py` | MODIFY | Add logger, log fallback attempts |
| `agent/skills/registry.py` | MODIFY | Replace `logging.getLogger()` with `get_logger()` |
| `agent/skills/permissions.py` | MODIFY | Replace `logging.getLogger()` with `get_logger()` |
| `tests/test_logging.py` | CREATE | 8+ test cases for logging config |

---

## Key Convention Notes

- **Log message style**: lowercase, no trailing period, descriptive. E.g., `"intent resolved"` not `"Intent resolved."`.
- **Structured fields**: always keyword args. E.g., `logger.info("done", skill="media", latency_ms=42)`.
- **No `%s` formatting**: structlog uses keyword args, not printf-style. Replace all `logger.info("X: %s", val)` with `logger.info("x", val=val)`.
- **Context vars**: Set at request boundary (top of `_run_loop` iteration), cleared at end. Automatically included in all log entries.
