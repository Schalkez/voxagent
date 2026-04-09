# VoxAgent: Technical Concerns Register

> Generated: 2026-04-09 | Scope: Full codebase audit (agent/, dashboard/, tests/)

---

## 1. Security Vulnerabilities

### 1.1 CRITICAL: Remote Code Execution via Skill Marketplace

**Location:** `agent/skills/marketplace.py:141-170`

The `_install_remote` method downloads Python source code from a remote registry and writes it directly to disk as a `.py` file. This code is then auto-discovered and executed by the `SkillRegistry.discover_skills()` importer.

- No code signature verification or checksum validation
- No sandboxing of downloaded skill code
- No permission review before execution
- The registry URL (`registry.voxagent.dev`) is hardcoded with no certificate pinning
- A compromised registry or MITM attack could inject arbitrary Python into the runtime

**Risk:** Remote code execution. A malicious skill can access the full system.

### 1.2 CRITICAL: Prompt Injection via Screen Context

**Location:** `agent/core/brain.py:158-164`

When certain keywords are detected (`màn hình`, `screen`, `đọc`, `nhìn`, `thấy`), the Brain module captures screen text via OCR and injects it raw into the LLM system prompt:

```python
sys_prompt += f"\n\nCURRENT SCREEN TEXT CONTEXT:\n{screen_content}"
```

The `PromptGuard` in `core/safety.py` exists but is **never called** anywhere in the pipeline. Screen content could contain adversarial text designed to override system instructions, and it flows directly into the LLM unsanitized.

**Risk:** Indirect prompt injection. Malicious content on screen can hijack agent behavior.

### 1.3 HIGH: API Server Has No Authentication by Default

**Location:** `agent/api/server.py`, `agent/api/server_mode.py:78-97`

The FastAPI management API (`server.py`) has **zero authentication**. Any process on the machine (or network, if bound to `0.0.0.0`) can:

- Save/replace API keys via `POST /api/providers/{id}/key`
- Modify routing configuration
- Enable/disable skills
- Execute commands via `/api/command`

The server mode has optional API key auth via `VOXAGENT_API_KEY` env var, but:
- It defaults to **open access** when the env var is not set
- The management API (`server.py`) has no auth at all
- `run_server_mode` docstring says `Default 0.0.0.0 for network access` but code says `127.0.0.1`

### 1.4 HIGH: Path Traversal in File Manager Skill

**Location:** `agent/skills/file_manager.py:90-320`

The `FileManagerSkill` uses `Path(path_str).resolve()` which does resolve symlinks, but there is **no jail/sandbox check** to restrict operations to safe directories. An LLM-generated intent with `params={"path": "/etc/passwd"}` or `params={"path": "C:\\Windows\\System32"}` would be executed without any containment.

The `delete_file` action uses `shutil.rmtree` on directories, which is recursive and irreversible.

### 1.5 HIGH: Terminal Allowlist Bypass Potential

**Location:** `agent/skills/terminal.py:29-64`

The `ALLOWED_COMMAND_PREFIXES` allowlist includes `python` and `pip`, which are effectively arbitrary code execution vectors. `python -c "import os; os.system('rm -rf /')"` would pass the prefix check. The `DANGEROUS_SHELL_CHARS` regex blocks `$` and `;` which mitigates some attacks, but:

- `python -c` commands don't need shell metacharacters to be dangerous
- `git` is allowed and can execute arbitrary commands via hooks
- `node` and `npm` can execute arbitrary JavaScript

### 1.6 MEDIUM: Dependency Resolver Runs pip Without Validation

**Location:** `agent/skills/dependency_resolver.py:75-112`

`install_dependencies` runs `pip install` with user-supplied package names from marketplace skill manifests. A malicious manifest could install a typosquatted or backdoored package. No hash verification, no trusted-host restriction, no `--require-hashes`.

### 1.7 MEDIUM: CORS Configuration Accepts Wildcard Methods/Headers

**Location:** `agent/api/server.py:145-151`

```python
allow_methods=["*"],
allow_headers=["*"],
```

While origins are restricted, wildcard methods and headers weaken CORS protection.

---

## 2. Architectural & Design Debt

### 2.1 HIGH: Duplicated Provider Registration (DRY Violation)

**Location:** `agent/core/app.py:125-187` and `agent/api/server.py:33-103`

The provider registration block is copy-pasted verbatim between `VoxAgentApp._register_providers()` and the API `lifespan()` function. Both contain the exact same 15+ try/except/import blocks. Any new provider must be added in two places.

**Fix:** Extract a shared `register_all_providers(registry)` function.

### 2.2 HIGH: SkillRegistry Singleton Uses ClassVar State

**Location:** `agent/skills/registry.py:17-27`

`SkillRegistry` uses `__new__` singleton pattern with `ClassVar[dict]` for `_skills`. This means:
- All instances share state via the class, not the instance
- Tests cannot create isolated registries without contaminating global state
- The `__new__` guard creates one instance, but `_skills` lives on the class itself

### 2.3 MEDIUM: Planner Module Is Not Integrated

**Location:** `agent/core/planner.py`

The `Planner` class exists and is fully implemented, but it is **never instantiated or called** from `VoxAgentApp` or `Brain`. The `Brain.process()` method always returns a single intent. Multi-step commands are silently reduced to single actions.

### 2.4 MEDIUM: Eyes Creates New ProviderRegistry on Each Call

**Location:** `agent/core/eyes.py:238-240`

```python
registry = ProviderRegistry()
vision_providers = registry.list_registered().get("vision", [])
```

`analyze_screen` creates a fresh `ProviderRegistry()` each time, which has no providers registered. Vision analysis will always return "No vision provider configured." The registry from `VoxAgentApp` is never injected into Eyes.

### 2.5 MEDIUM: Brain Creates a New Eyes Instance Every Time

**Location:** `agent/core/brain.py:80`

```python
self.eyes = Eyes()
```

Brain creates its own `Eyes` instance. Since Eyes has an OCR cache, this means the cache TTL optimization is working per-Brain-instance, but if multiple Brains exist (e.g., in server mode where one is lazily created at `server_mode.py:138`), their caches are independent and may cause redundant OCR processing.

### 2.6 MEDIUM: Hands Iterates Tiers But Always Calls Same execute()

**Location:** `agent/hands.py:136-148`

The tier iteration loop calls `skill.execute(intent)` identically for every tier. Skills don't receive which tier to attempt, so the "try Tier A, fall back to Tier B" pattern is not actually implemented - the same code path runs N times.

### 2.7 LOW: Duplicate WindowInfo/UIElement Dataclasses

**Location:** `agent/core/eyes.py:28-55` vs `agent/system/base.py:13-45`

`WindowInfo` and `UIElement` are defined independently in both `core/eyes.py` and `system/base.py` with identical fields. Eyes manually copies fields between them (`eyes.py:96-104`), which is fragile and violates DRY.

### 2.8 LOW: Two Separate ProviderNotFoundError Classes

**Location:** `agent/providers/registry.py:21` vs `agent/api/exceptions.py:30`

Two distinct `ProviderNotFoundError` classes exist with different base classes (`KeyError` vs `VoxAPIException`). Code catching one won't catch the other.

---

## 3. Performance Concerns

### 3.1 HIGH: New httpx.AsyncClient Per LLM Request

**Location:** All providers (`openai_provider.py`, `groq_provider.py`, `ollama_provider.py`, `anthropic_provider.py`, etc.)

Every `chat()` and `chat_with_tools()` call creates a new `httpx.AsyncClient(...)` via `async with`. This means:
- A new TCP connection is established for every single LLM call
- No connection pooling or keep-alive
- No reuse of TLS sessions
- Significant latency overhead on each request (especially for cloud providers)

In a voice pipeline where latency is critical, this adds 50-200ms per request.

### 3.2 MEDIUM: OCREngine Re-Initialized on Every Screen Read

**Location:** `agent/core/eyes.py:202-203`

```python
engine = OCREngine()
text = await engine.extract_text(image)
```

A new `OCREngine()` is created on every `read_screen_text()` call. While it lazy-loads the PaddleOCR model, the initialization check and import overhead still occurs each time. The OCR engine should be a persistent instance.

### 3.3 MEDIUM: Memory Module Commits After Every Single Write

**Location:** `agent/core/memory.py:125, 170, 224`

Each `add_conversation`, `set_preference`, and `set_skill_state` call immediately does `await self._db.commit()`. For burst writes (e.g., logging a conversation pair), this causes two separate fsync operations. Should batch commits or use WAL mode.

### 3.4 MEDIUM: Health Checks Make Full API Calls

**Location:** `agent/providers/openai_provider.py:73-84`, `groq_provider.py:73-84`, `anthropic_provider.py:91-102`

Provider health checks send a real chat message (`"ping"` with `max_tokens=1`). This:
- Incurs API costs on every health check
- Is slower than necessary (a simple auth check would suffice)
- May hit rate limits if health checks are frequent

### 3.5 LOW: Autopilot Polls All Tasks Every Second

**Location:** `agent/core/autopilot.py:116-139`

The autopilot loop iterates all registered tasks every 1 second and calls `task.condition()` synchronously via `asyncio.to_thread`. For time-based tasks, a priority queue with next-fire-time would be much more efficient.

### 3.6 LOW: AudioRecorder Queue Has No Max Size

**Location:** `agent/core/audio/recorder.py:50`

```python
self._audio_queue: asyncio.Queue[np.ndarray] = asyncio.Queue()
```

Unbounded queue. If processing stalls (e.g., slow STT), audio chunks accumulate in memory indefinitely. With 80ms chunks at 16kHz mono int16, each chunk is ~2.5KB. A 30-second stall would only be ~1MB, but the principle is fragile.

---

## 4. Reliability & Error Handling

### 4.1 HIGH: Broad Exception Catch in Planner

**Location:** `agent/core/planner.py:141`

```python
except Exception as e:
```

Bare `Exception` catch swallows all errors including programming bugs. This violates the project's own "Strict Clean Catch" rule and makes debugging difficult.

### 4.2 HIGH: Signal Handler Race in VoxAgentApp

**Location:** `agent/core/app.py:66-70`

```python
loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
```

The lambda captures `self` by reference. On Windows fallback, `asyncio.create_task()` is called from the signal handler context, which may not have a running event loop. This can silently fail, leaving the app in a zombie state.

### 4.3 MEDIUM: No Retry/Backoff on LLM Calls

**Location:** `agent/core/brain.py:169-209`

The `_try_llm_routing` method makes one attempt at the configured tier. If it fails, it falls back to "unknown" intent. There is no:
- Retry with exponential backoff
- Fallback to the next tier in the chain
- Use of `ProviderRegistry.get_llm_with_fallback()`

The fallback chain exists in the registry but Brain never uses it.

### 4.4 MEDIUM: Silent Failures Throughout Pipeline

Multiple locations silently swallow errors and return empty/default results:
- `Eyes.get_active_window()` returns empty `WindowInfo` on failure (`eyes.py:102-104`)
- `Mouth.speak()` logs and returns on TTS failure (`mouth.py:86-88`)
- `_get_stt_provider()` returns `None` on failure, leading to API-only mode (`app.py:198-201`)
- All provider imports wrapped in bare `try/except ImportError: pass` (`app.py:127-187`)

While graceful degradation is intentional, there's no aggregate health reporting. The user has no way to know which modules are degraded.

### 4.5 MEDIUM: Config Docstring Says Pydantic But Uses Dataclasses

**Location:** `agent/core/config.py:1-4`

The module docstring says "Uses Pydantic for typed configuration access" but the implementation uses `@dataclass(frozen=True)`. No Pydantic is used. This is misleading documentation.

### 4.6 LOW: Autopilot task.condition() Runs in Main Thread

**Location:** `agent/core/autopilot.py:119`

```python
if task.condition():
```

Task conditions are called synchronously in the main async loop. A slow condition function blocks the entire autopilot. Only actions are wrapped in `asyncio.to_thread`. The condition itself is not.

---

## 5. Testing Gaps

### 5.1 HIGH: Test Files Named for Coverage Goals, Not Behavior

Multiple test files appear to be written for coverage metrics rather than behavioral validation:
- `test_coverage_boost.py` (196 lines)
- `test_push_80.py` (331 lines)
- `test_final_coverage.py` (383 lines)

This pattern suggests tests were added to hit coverage targets rather than to verify critical functionality. These tests likely mock aggressively and may not catch real regressions.

### 5.2 HIGH: No Integration Tests for the Full Pipeline

The test suite contains no integration test that exercises the actual EARS -> BRAIN -> HANDS -> MOUTH flow end-to-end with real (mocked provider) dependencies. Individual modules are tested in isolation, but the wiring between them is untested.

### 5.3 MEDIUM: Duplicate Test Directories

Tests exist in two locations:
- `agent/tests/` (24 files, 3329 total lines)
- `tests/` (5 files, root-level)

The root `tests/` directory has its own `conftest.py` and test files (`test_brain.py`, `test_ears.py`, `test_skills.py`) that may duplicate or contradict `agent/tests/`. It's unclear which is canonical.

### 5.4 MEDIUM: No Tests for Security-Critical Code Paths

- `marketplace.py` remote install (arbitrary code download) - not tested
- `file_manager.py` delete operations - only basic path testing
- `terminal.py` command sanitization - needs adversarial test cases
- `server_mode.py` API key validation - minimal testing
- `safety.py` prompt guard - tested but never integrated

### 5.5 LOW: No Dashboard Tests

The React dashboard (`dashboard/`) has no test files (no `*.test.ts`, `*.test.tsx`, or `*.spec.ts`). The dashboard is pure UI with hooks that call the API, but there are zero component tests or hook tests.

---

## 6. Missing Features & Stubs

### 6.1 Stub Implementations (Not Functional)

| Module | Stub Location | Description |
|--------|---------------|-------------|
| `code_reviewer.py:54-60` | `_review_visible()` | Returns "đang được phát triển" hardcoded |
| `screen_reader.py:89-95` | `_describe_screen()` | Returns "đang được phát triển" hardcoded |
| `mouth.py:99` | `play_earcon()` | TODO comment, no implementation |
| `windows.py:66-72` | `find_element()` | Returns None always, "not fully implemented" |
| `windows.py:100-106` | `read_notifications()` | Returns empty list always |
| `windows.py:129-134` | `get_volume()` | Returns hardcoded `50` always |
| `system_skill.py:48-54` | mute/unmute actions | Return success without actually toggling |

### 6.2 Vision Providers Exist But Are Never Registered

**Location:** `agent/providers/vision/` (3 files: `anthropic_vision.py`, `gemini_vision.py`, `openai_vision.py`)

Vision providers exist but are never registered in either `VoxAgentApp._register_providers()` or the API `lifespan()`. The Eyes module's `analyze_screen()` will always fail with "No vision provider configured."

### 6.3 Telemetry Endpoint Is Non-Functional

**Location:** `agent/core/telemetry.py:11`

The telemetry client points to `https://telemetry.voxagent.dev/v1/events` which is presumably not a real endpoint. The client is never instantiated anywhere in the application.

### 6.4 i18n System Is Not Wired Up

**Location:** `agent/core/i18n.py`, `agent/core/language.py`

Both `i18n.t()` and `LanguageManager` exist but are unused. All TTS responses throughout skills are hardcoded Vietnamese strings. The i18n system would need to be integrated into every skill's response generation.

---

## 7. Code Quality & Conventions

### 7.1 MEDIUM: Missing `__init__.py` Barrel Exports

Several `__init__.py` files are empty or minimal. Per the CLAUDE.md rules, barrel files should re-export public APIs. Currently, imports use deep paths like `from core.audio.recorder import AudioRecorder` instead of `from core.audio import AudioRecorder`.

### 7.2 MEDIUM: Global Mutable State in API Store

**Location:** `agent/api/state/store.py:219-221`

```python
_routing, _skills = _load_state()
routing_config_state: RoutingConfigState = _routing
skills_state: list[SkillEntry] = _skills
```

Module-level mutable globals loaded at import time. Any module importing `store` gets the same mutable references. No locking for concurrent access from FastAPI's async handlers.

### 7.3 LOW: Config Uses `yaml.safe_load` But No Schema Validation

**Location:** `agent/core/config.py:182`

While `safe_load` prevents arbitrary code execution, there is no validation that the YAML structure matches expected types. A malformed config file could produce silent runtime errors (e.g., string where int is expected).

### 7.4 LOW: Inconsistent Error Reporting Pattern

Skills return errors in three different ways:
1. `SkillResult(success=False, error="...", tts_response="...")` - full info
2. `SkillResult(success=False, error="...")` - no TTS response
3. `SkillResult(success=False, tts_response="...")` - no error detail

No standardized error handling pattern across skills.

---

## 8. Dependency & Deployment Risks

### 8.1 MEDIUM: Heavy Optional Dependencies Not Managed

The project has ~15 optional dependencies (PaddleOCR, Silero VAD, OpenWakeWord, faster-whisper, sounddevice, psutil, pydub, edge-tts, torch, etc.) handled via lazy `try/except ImportError`. There is no clear dependency group management (e.g., `pip install voxagent[audio]` vs `voxagent[vision]`).

### 8.2 MEDIUM: No Dependency Pinning

The `pyproject.toml` or `requirements.txt` was not found in the explored tree. Without pinned dependencies, builds are not reproducible and may break from upstream changes.

### 8.3 LOW: Windows-Centric Development

Many features are Windows-only or Windows-first:
- `media_control.py` uses `ctypes.windll` directly (non-Windows returns failure)
- `system_control.py` handles Windows/Unix but no macOS-specific paths
- `app_launcher.py`'s `_APP_MAP` is Windows-focused (`calc`, `mspaint`, `winword`)
- `windows.py` is the most complete SystemAutomation; Linux/macOS stubs are minimal

---

## 9. Summary Priority Matrix

| Priority | Count | Top Item |
|----------|-------|----------|
| CRITICAL | 2 | Marketplace RCE, Unsanitized screen context injection |
| HIGH | 8 | No API auth, path traversal, duplicate registration, httpx per-request |
| MEDIUM | 17 | Planner not integrated, no retry on LLM, coverage-driven tests |
| LOW | 9 | Duplicate dataclasses, hardcoded stubs, unbounded queue |

---

## 10. Recommended Immediate Actions

1. **Disable remote marketplace install** until code signing is implemented
2. **Integrate PromptGuard** into Brain.process() before any LLM call
3. **Add authentication** to the management API (at minimum, localhost-only binding + API key)
4. **Add path sandboxing** to FileManagerSkill (restrict to user home or configured safe dirs)
5. **Create shared httpx.AsyncClient** per provider with connection pooling
6. **Extract provider registration** into a single shared function
7. **Wire ProviderRegistry.get_llm_with_fallback()** into Brain tier routing
8. **Register vision providers** in the startup sequence
