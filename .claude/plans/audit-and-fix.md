# VoxAgent Full Audit — Bug Fixes & Production Hardening Plan

## Audit Results: 28 Issues Found

### 🔴 CRITICAL (5) — Will crash or break at runtime

| # | File | Line | Issue | Fix |
|---|------|------|-------|-----|
| C1 | `core/app.py` | 100-103 | **Brain.__init__() signature mismatch** — `app.py` passes `config=self._config` but `brain.py` expects `routing_config: dict[str, Any]`. Will **crash at startup**. | Pass `routing_config=self._config.routing.__dict__` or update Brain to accept VoxAgentConfig |
| C2 | `core/app.py` | 60-61 | **signal.add_signal_handler() crashes on Windows** — `add_signal_handler` is Unix-only. On Windows (primary platform), this throws `NotImplementedError`. | Wrap in try/except or use `signal.signal()` for Windows |
| C3 | `core/brain.py` | 160 | **bare `except Exception` still remains** — the only file we missed in compliance pass. Violates CONTRIBUTING.md rule. | Replace with specific exceptions |
| C4 | `skills/registry.py` | 80 | **bare `except Exception` in discover_skills** — catches everything including KeyboardInterrupt. | Replace with `except (ImportError, AttributeError, TypeError)` |
| C5 | `api/server.py` | 163 | **Accessing private attrs `_llm_providers`** in /api/status — fragile, breaks if registry internals change. | Add public method `list_providers()` to ProviderRegistry |

### 🟠 HIGH (8) — Incorrect behavior or security concern

| # | File | Line | Issue | Fix |
|---|------|------|-------|-----|
| H1 | `core/hands.py` | 102 | **bare `except Exception`** catching skill fetch errors — should catch `VoxAPIException` specifically | Replace with `except (VoxAPIException, KeyError)` |
| H2 | `skills/app_launcher.py` | 132, 184 | **Two bare `except Exception`** remaining — missed in compliance pass | Replace with specific types |
| H3 | `providers/registry.py` | 66, 79, 92, 105 | **Provider instantiation via `class()` with no args** — but OpenAI/Groq/Anthropic constructors need API key lookup at init. Creates **new instance every call** = wasteful repeated keyring lookups | Cache instances or use lazy singletons |
| H4 | `core/mouth.py` | 84, 144 | **`_play_wav` is async but calls `sd.play/sd.wait()` which BLOCKS** the event loop | Wrap in `asyncio.to_thread()` |
| H5 | `providers/stt/whisper_local.py` | 72-84 | **`transcribe` is async but `self._model.transcribe()` BLOCKS** the event loop — Whisper inference can take seconds | Wrap in `asyncio.to_thread()` |
| H6 | `api/services/routing.py` | 15 | **`global routing_config_state`** but variable is imported, not module-level — the `global` does nothing, mutation happens via `.clear()/.update()` which works by accident | Remove misleading `global` statement |
| H7 | `system/factory.py` | 28 | **Module-level singleton `automation = _get_system_automation()`** — crashes on import on macOS/Linux with `NotImplementedError` | Use lazy initialization |
| H8 | `core/ears.py` | 156 | **`stop_listening()` is public API but `stop()` is what `app.py` calls** (line 192: `await self._ears.stop()`). `stop()` doesn't exist on Ears class. | Add `stop()` alias or fix app.py to call `stop_listening()` |

### 🟡 MEDIUM (10) — Code quality, compliance, minor bugs

| # | File | Line | Issue | Fix |
|---|------|------|-------|-----|
| M1 | `core/app.py` | 34 | **VoxAgentApp `@dataclass` not frozen** — ARCHITECTURE.md says prefer frozen dataclasses | Can't freeze due to mutable state — add comment explaining |
| M2 | `core/app.py` | 48 | **`_hands: Hands = field(default_factory=Hands)`** — Hands() gets no mouth/ears, will always deny dangerous actions | Wire mouth/ears after init in `_init_modules` |
| M3 | `skills/system_skill.py` | 29 | **set_volume doesn't actually call system automation** — just returns hardcoded response | Wire to `WindowsAutomation.set_volume()` |
| M4 | `core/brain.py` | 124 | **`except KeyError` but ProviderRegistry raises `ProviderNotFoundError`** (subclass of KeyError) — semantically imprecise | Catch `ProviderNotFoundError` explicitly |
| M5 | `providers/__init__.py` | 7 | **Eager imports of ALL providers at package level** — importing `providers` triggers keyring lookups for OpenAI/Groq/Anthropic | Use lazy imports or remove from `__init__.py` |
| M6 | `core/config.py` | 119 | **VoxAgentConfig not frozen** — mutable by accident | Cannot freeze (has mutable dict field) — document |
| M7 | `core/ears.py` | 50-51 | **`EarsEvent` not frozen** — should be `@dataclass(frozen=True)` per conventions | Add `frozen=True` |
| M8 | `api/server.py` | 147-172 | **/api/status endpoint not returning from request state** — imports skill_registry at function level each call | Import once at module level |
| M9 | `providers/stt/openai_whisper.py` | 77 | **Hardcoded confidence=0.95** — OpenAI API doesn't return confidence, but hardcoding masks this | Add comment or use sentinel value |
| M10 | `dashboard/src/features/dashboard/containers/DashboardView.tsx` | - | Removed Component Testing Sandbox but it contained useful UI testing | Fine — was intentional cleanup |

### 🔵 LOW (5) — Style, dead code, minor improvements

| # | File | Line | Issue | Fix |
|---|------|------|-------|-----|
| L1 | `providers/stt/__init__.py`, `providers/tts/__init__.py` | - | **Empty `__init__.py` files** — no barrel exports | Add exports for discoverability |
| L2 | `core/audio/__init__.py`, `core/__init__.py` | - | **Empty `__init__.py` files** | Fine — namespace packages |
| L3 | `core/mouth.py` | 89-98 | **`play_earcon()` is unimplemented** — just logs | Add TODO comment or remove from public API |
| L4 | `CONTRIBUTING.md` | 10, 241 | **Still has `your-org` placeholder URLs** | Replace with `voxagent` |
| L5 | `api/deps.py` | 18-19 | **`from typing import cast` imported inside function** | Move to top |

---

## Fix Plan (ordered by priority)

### Step 1: Fix CRITICAL bugs (C1-C5)
1. **C1**: Fix Brain constructor call in `app.py` to match actual signature
2. **C2**: Add Windows-safe signal handling in `app.py`
3. **C3**: Replace bare `except Exception` in `brain.py:160`
4. **C5**: Add `list_registered()` method to ProviderRegistry; use in `/api/status`
5. **C4**: Replace bare `except Exception` in `skills/registry.py:80`

### Step 2: Fix HIGH bugs (H1-H8)
1. **H8**: Fix `Ears.stop()` method name mismatch — add `stop()` alias
2. **H4**: Wrap `sd.play/sd.wait()` in `asyncio.to_thread()`
3. **H5**: Wrap whisper_local `transcribe()` blocking call in `asyncio.to_thread()`
4. **H1, H2**: Replace remaining bare `except Exception` in hands.py and app_launcher.py
5. **H3**: Cache provider instances in registry
6. **H6**: Remove misleading `global` in routing service
7. **H7**: Make system/factory.py use lazy init

### Step 3: Fix MEDIUM issues (M1-M9)
1. **M2**: Wire Hands with mouth/ears in `_init_modules`
2. **M3**: Wire system_skill to actual automation
3. **M4, M5, M7**: Fix imports, frozen dataclass, exception types
4. **M8, L5**: Clean up import patterns

### Step 4: Fix LOW issues (L1-L4)
1. **L4**: Fix remaining placeholder URLs in docs
2. **L3**: Document play_earcon as TODO
3. **L1**: Add barrel exports to STT/TTS __init__.py

### Step 5: Run all tests, lint, dashboard build — verify 0 regressions
