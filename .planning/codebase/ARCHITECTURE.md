# VoxAgent Architecture

## Pattern

**Anthropomorphic Pipeline Architecture** with **Tiered Execution Strategy**.

The system models a voice-controlled desktop agent as a human body metaphor:
EARS (hear) -> BRAIN (think) -> HANDS (act) -> MOUTH (speak), with EYES (see)
and MEMORY (remember) as auxiliary modules. Each module is a single-responsibility
orchestrator that delegates to injected providers and sub-components.

The secondary architectural pattern is a **Provider-Abstracted Plugin System**:
all external integrations (LLMs, STT, TTS, Vision, OS automation) are behind
abstract base classes, registered in centralized registries, and resolved at
runtime via factory/registry patterns.

---

## Layers

### Layer 1: Core Pipeline (`agent/core/`)

The domain logic layer. Provider-agnostic orchestrators that implement the
voice agent loop. No direct imports of concrete providers are allowed here.

| Module        | Responsibility                                              |
|---------------|-------------------------------------------------------------|
| `app.py`      | Application lifecycle orchestrator. Entry point. Wires all modules, runs the EARS->BRAIN->HANDS->MOUTH loop, manages signal handlers and graceful shutdown. |
| `ears.py`     | Voice input pipeline: Mic -> Wake Word -> VAD -> STT -> raw text. Orchestrates `audio/` sub-components and delegates transcription to an injected `STTProvider`. |
| `brain.py`    | Smart tier routing and intent extraction. Routes text through Tier 0 (keyword matching) -> Tier 1-3 (LLM function calling) and returns structured `Intent` objects. |
| `hands.py`    | Tiered action execution. Receives `SkillIntent`, resolves the skill from the registry, enforces permissions, handles dangerous-action confirmation via voice, and tries execution tiers A->D. |
| `mouth.py`    | TTS output with Vietnamese response templates. Synthesizes text via injected `TTSProvider` and plays audio through sounddevice. |
| `eyes.py`     | Layered screen understanding: Layer 1 (native UI tree) -> Layer 2 (OCR with caching) -> Layer 3 (Vision LLM). Injects screen context into Brain prompts. |
| `memory.py`   | SQLite persistence via `aiosqlite`. Stores conversations, user preferences, and per-skill state. Schema-versioned for migrations. |
| `autopilot.py`| Background task scheduler. Supports time-based, event-based, condition-based, and idle-based triggers. Runs as a separate asyncio task alongside the main pipeline. |
| `planner.py`  | Multi-step command decomposition. Detects multi-action commands (e.g., "open Chrome then shutdown") and uses the Tier 3 LLM to break them into sequential `Intent` lists. |
| `safety.py`   | Prompt injection detection and sanitization. Regex-based pattern matching against known injection techniques with input length limits. |
| `config.py`   | YAML configuration loader with built-in profiles (`full_local`, `cloud_free`, `hybrid`, `budget_cloud`). Atomic writes via temp-file-then-rename. |
| `keyring_manager.py` | OS keyring wrapper for secure API key storage. Reads/writes to Windows Credential Locker, macOS Keychain, or Linux SecretService. |
| `i18n.py`     | Internationalization. Template-based translation system for Vietnamese and English responses. |
| `language.py` | Multi-language manager. Heuristic language detection and STT/TTS voice mapping for vi, en, ja, ko, zh. |
| `ocr.py`      | OCR engine with PaddleOCR primary and Tesseract fallback. Thread-pooled for async compatibility. |
| `sync.py`     | Multi-device config synchronization via shared directory (file-based, last-writer-wins). |
| `telemetry.py`| Opt-in anonymous telemetry client. No-op when disabled. |

#### Audio Sub-components (`agent/core/audio/`)

| Module         | Responsibility                                           |
|----------------|----------------------------------------------------------|
| `recorder.py`  | Microphone capture via sounddevice. Produces audio chunks. |
| `wake_word.py` | Wake word detection using openwakeword/ONNX models.       |
| `vad.py`       | Voice Activity Detection using Silero VAD.                 |
| `converter.py` | Converts numpy audio frames to WAV byte format.           |

### Layer 2: Providers (`agent/providers/`)

Abstract interfaces and their concrete implementations. Core modules
never import concrete providers directly -- they go through the
`ProviderRegistry`.

| Sub-layer          | Base Class       | Implementations                                                   |
|--------------------|------------------|-------------------------------------------------------------------|
| LLM Providers      | `LLMProvider`    | `openai`, `groq`, `anthropic`, `ollama`, `deepseek`, `mistral`, `openrouter` |
| STT Providers      | `STTProvider`    | `whisper_local` (faster-whisper), `openai_whisper`                |
| TTS Providers      | `TTSProvider`    | `edge_tts`, `piper`, `elevenlabs_clone`                          |
| Vision Providers   | `VisionProvider` | `openai_vision`, `anthropic_vision`, `gemini_vision`             |
| Registry           | --               | `ProviderRegistry` (factory + instance cache + fallback chain)   |

**Key abstractions in `providers/base.py`:**
- `LLMProvider.chat()` -- text completion
- `LLMProvider.chat_with_tools()` -- function calling (used by Brain for intent extraction)
- `LLMProvider.health_check()` -- availability probing (used by fallback chain)
- `STTProvider.transcribe()` -- audio bytes -> `TranscribeResult`
- `TTSProvider.synthesize()` -- text -> WAV bytes
- `VisionProvider.analyze_image()` -- image bytes + prompt -> text analysis

### Layer 3: Skills (`agent/skills/`)

Pluggable action handlers. Each skill extends `BaseSkill`, declares its
`execution_tiers` (A->D priority), `keywords` (for Tier 0 matching), and
`permissions` (for safety enforcement).

| Skill               | Execution Tiers      | Description                           |
|----------------------|----------------------|---------------------------------------|
| `app_launcher.py`    | NATIVE_API, SHELL    | Open/close desktop applications       |
| `media_control.py`   | NATIVE_API, KEYBOARD | Play/pause/skip/volume via media keys |
| `system_control.py`  | NATIVE_API, SHELL    | Shutdown, restart, lock, sleep        |
| `file_manager.py`    | NATIVE_API, SHELL    | File operations (create, move, delete)|
| `browser_control.py` | APP_API              | Browser automation via Playwright CDP |
| `terminal.py`        | SHELL                | Execute terminal commands             |
| `screen_reader.py`   | NATIVE_API, UI       | Read screen content via Eyes          |
| `code_reviewer.py`   | APP_API              | Code review using LLM                 |
| `media_control.py`   | NATIVE_API, KEYBOARD | Media playback control                |
| `marketplace.py`     | APP_API              | Skill marketplace (install/browse)    |
| `system_skill.py`    | NATIVE_API           | System info queries                   |

**Registration:** Skills use the `@register_skill` decorator, which instantiates
the class and stores it in the singleton `SkillRegistry`. The registry also
supports dynamic discovery via `discover_skills()` (walks the `skills` package).

**Permission system:** `permissions.py` defines `PermissionLevel` (SAFE, ELEVATED,
DANGEROUS) and `PermissionManager` which checks skill-declared permissions at
runtime. DANGEROUS permissions block execution unless explicitly granted.

### Layer 4: System Abstraction (`agent/system/`)

OS-specific implementations behind the `SystemAutomation` ABC.

| Module        | Platform  | Implementation                             |
|---------------|-----------|--------------------------------------------|
| `base.py`     | --        | Abstract interface: get_active_window, find_element, get_running_processes, read_notifications, set/get_volume |
| `windows.py`  | Windows   | pywinauto + win32gui + ctypes              |
| `macos.py`    | macOS     | pyobjc + Accessibility API + osascript     |
| `linux.py`    | Linux     | AT-SPI (atspi2) + xdotool                 |
| `factory.py`  | --        | Platform detection factory with lazy init  |

### Layer 5: API Server (`agent/api/`)

FastAPI REST API consumed by the React dashboard. Follows a strict
Router -> Service -> State/Registry layered pattern.

| Component          | Responsibility                                       |
|--------------------|------------------------------------------------------|
| `server.py`        | FastAPI app creation, lifespan, CORS, router mounting. Entry point for `voxagent-api` command. |
| `server_mode.py`   | Headless server mode. Adds `/api/command` endpoint for programmatic integration (n8n, Home Assistant). Includes rate limiting and API key auth. |
| `routers/`         | HTTP route handlers: `providers`, `routing`, `skills`, `settings` |
| `services/`        | Business logic layer between routers and state/registries |
| `schemas/`         | Pydantic request/response models                     |
| `state/store.py`   | Persistent YAML-backed state for routing config and skill toggles |
| `deps.py`          | FastAPI dependency injection (extracts ProviderRegistry from app.state) |
| `exceptions.py`    | Domain exception hierarchy: `VoxAPIException`, `ProviderConfigError`, `ProviderNotFoundError` |

### Layer 6: Dashboard (`dashboard/`)

React 19 + TypeScript + Tailwind CSS SPA. Communicates with the Python API
server over REST.

**Structure pattern:** Feature-sliced architecture with Atomic Design for shared components.

| Route         | Feature Module             | Description                    |
|---------------|----------------------------|--------------------------------|
| `/dashboard`  | `features/dashboard/`      | Overview with bento grid, hero card, terminal log |
| `/providers`  | `features/providers/`      | Provider cards, Ollama config, quota stats |
| `/routing`    | `features/routing/`        | Tier configuration, preset selection |
| `/skills`     | `features/skills/`         | Skill cards, enable/disable, add skill |
| `/settings`   | `features/settings/`       | Audio settings, security card  |
| `/autopilot`  | `features/autopilot/`      | Background task management     |
| `/memory`     | `features/memory/`         | Conversation history viewer    |

Each feature follows: `containers/` (glue) + `components/organisms/` (UI) +
`hooks/` (data/state) + `types/` + `constants/`.

Shared layer: `shared/components/` (atoms, molecules, organisms, templates),
`shared/api/client.ts` (fetch wrapper).

---

## Data Flow

### Primary Voice Pipeline

```
Microphone
    |
    v
[EARS] AudioRecorder -> WakeWordDetector -> VAD -> AudioConverter -> STTProvider
    |                                                                    |
    | wake word detected                                    TranscribeResult
    |                                                                    |
    v                                                                    v
[BRAIN] Tier 0: keyword match against skill.keywords
    |       -> hit? return Intent immediately (<50ms)
    |
    |   Tier 1-3: LLM function calling via ProviderRegistry
    |       -> build OpenAI-compatible tools schema from skills
    |       -> inject screen context from EYES if command references screen
    |       -> parse tool call response into Intent(skill_name, action, params)
    |
    v
[HANDS] SkillRegistry.get_skill(intent.skill_name)
    |       -> permission check (PermissionManager)
    |       -> dangerous action? voice confirmation via MOUTH+EARS
    |       -> skill.can_handle(intent)
    |       -> iterate execution tiers A->D until success
    |
    v
[MOUTH] TTSProvider.synthesize(result.tts_response)
    |       -> sounddevice playback
    v
Speaker
```

### Multi-Step Command Flow (Planner)

```
"Open Chrome then shutdown"
    |
    v
[Planner] is_multi_step() -> detects sequence indicators ("then", "rồi")
    |       -> Tier 3 LLM with create_plan tool
    |       -> returns [Intent(app_launcher, open), Intent(system_control, shutdown)]
    |
    v
[HANDS] executes each Intent sequentially
```

### API/Dashboard Flow

```
React Dashboard
    |
    | HTTP REST (fetch via shared/api/client.ts)
    | Base URL: http://localhost:8642
    |
    v
[FastAPI Server] /api/*
    |   routers -> services -> state/store.py + ProviderRegistry
    |
    |   /api/status       -> system overview
    |   /api/providers/*  -> manage LLM/STT/TTS providers + API keys
    |   /api/routing/*    -> tier configuration + presets
    |   /api/skills/*     -> enable/disable/list skills
    |   /api/settings/*   -> audio, security, wake word config
    |   /api/command      -> headless command execution (server mode)
    |
    v
[ProviderRegistry] + [SkillRegistry] + [State Store]
```

### Screen Understanding Flow (Eyes)

```
Voice command references screen content
    |
    v
[EYES Layer 1] SystemAutomation.get_active_window() / find_element()
    |               -> OS-specific: pywinauto / pyobjc / AT-SPI
    |               -> instant, free
    |
    v (if deeper understanding needed)
[EYES Layer 2] OCREngine.extract_text(capture_screen())
    |               -> PaddleOCR primary, Tesseract fallback
    |               -> 5-second cache to avoid redundant calls
    |               -> <500ms
    |
    v (if complex visual analysis needed)
[EYES Layer 3] VisionProvider.analyze_image()
    |               -> GPT-4o / Claude / Gemini vision
    |               -> always crops to target region to minimize tokens
```

---

## Abstractions

### Provider Abstraction Boundary

```
core/ modules  -- only import -->  providers/base.py (ABCs)
                                   providers/registry.py (ProviderRegistry)

providers/*_provider.py  -- implements -->  LLMProvider / STTProvider / TTSProvider / VisionProvider
```

Core modules never know which LLM, STT, or TTS is in use. The `ProviderRegistry`
acts as a service locator with:
- **Lazy instantiation:** Providers are created on first `.get_*()` call
- **Instance caching:** Avoids repeated keyring lookups for API keys
- **Fallback chain:** `get_llm_with_fallback()` iterates configured providers, health-checking each

### Skill Abstraction Boundary

```
core/hands.py  -- uses -->  skills/base.py (BaseSkill ABC)
                            skills/registry.py (SkillRegistry singleton)

skills/*_skill.py  -- extends -->  BaseSkill
                  -- decorated with -->  @register_skill
```

Skills declare:
- `name`, `description`, `keywords` (for Tier 0)
- `execution_tiers` (ordered list: which tiers this skill supports)
- `permissions` (list of permission strings: "media:control", "terminal:write", etc.)

### System Abstraction Boundary

```
core/eyes.py  -- uses -->  system/factory.py -> system/base.py (SystemAutomation ABC)

system/windows.py  -- implements -->  SystemAutomation
system/macos.py    -- implements -->  SystemAutomation
system/linux.py    -- implements -->  SystemAutomation
```

The factory uses `platform.system()` detection with lazy singleton initialization.

### Configuration Abstraction

```
~/.voxagent/config.yaml  -- loaded by -->  core/config.py -> VoxAgentConfig dataclass tree
~/.voxagent/state.yaml   -- loaded by -->  api/state/store.py (dashboard state)
~/.voxagent/memory.db    -- managed by --> core/memory.py (SQLite via aiosqlite)
~/.voxagent/sync/        -- managed by --> core/sync.py (multi-device sync)
~/.voxagent/.device_id   -- managed by --> core/sync.py (persistent device ID)
```

Built-in profiles: `full_local` (Ollama), `cloud_free` (Groq), `hybrid` (Groq+Anthropic),
`budget_cloud` (Groq+Ollama fallback).

---

## Entry Points

| Entry Point         | Command                | Module            | Description                       |
|---------------------|------------------------|-------------------|-----------------------------------|
| Voice Agent CLI     | `voxagent start`       | `core/app.py:main`| Full pipeline: audio + brain + skills + TTS. Supports `--debug` and `--profile`. |
| Setup Wizard        | `voxagent setup`       | `core/app.py:_run_setup` | Interactive profile selection and config generation. |
| API Server          | `voxagent-api`         | `api/server.py:main` | FastAPI on `127.0.0.1:8642` with auto-reload. Dashboard management endpoints. |
| Server Mode         | (programmatic)         | `api/server_mode.py:run_server_mode` | Headless mode with `/api/command` for external integrations. Rate-limited + API key auth. |
| System Tray         | (embedded)             | `tray.py:TrayApp`  | pystray-based system tray icon with start/stop/dashboard menu. Runs in background thread. |
| Dashboard           | `pnpm dev`             | `dashboard/`       | Vite dev server on `localhost:5173`. React SPA communicating with the API server. |
| Benchmarks          | (manual)               | `agent/benchmarks/` | `bench_stt.py` (STT latency), `bench_tiers.py` (tier routing latency) |

### Script Entry Points (pyproject.toml)

```toml
[project.scripts]
voxagent = "core.app:main"
voxagent-api = "api.server:main"
```

### CI/CD

- `.github/workflows/ci.yml` -- GitHub Actions CI pipeline
- `.pre-commit-config.yaml` -- Pre-commit hooks (ruff, mypy, etc.)
- `.github/dependabot.yml` -- Dependency update automation

---

## Tiered Execution Strategy

The core differentiator of VoxAgent's architecture. Actions are always
attempted in order of cheapness/safety:

| Tier | Name        | Method                                  | Latency  | Cost |
|------|-------------|-----------------------------------------|----------|------|
| A    | NATIVE_API  | subprocess, ctypes, win32api, osascript | <100ms   | Free |
| A'   | SHELL       | Shell commands via subprocess            | <200ms   | Free |
| B    | APP_API     | Playwright CDP, REST APIs, native APIs  | <500ms   | Free |
| C    | UI          | pywinauto, pyobjc Accessibility, AT-SPI | <1s      | Free |
| D    | KEYBOARD    | PyAutoGUI mouse/keyboard simulation     | <2s      | Free |

HANDS iterates a skill's declared `execution_tiers` list and uses the first
tier that succeeds. If all tiers fail, an error response is spoken via MOUTH.

## LLM Tier Routing

Brain routes user commands through escalating LLM tiers:

| Tier | Size      | Use Case                        | Latency Target |
|------|-----------|---------------------------------|----------------|
| 0    | None      | Keyword pattern matching        | <50ms          |
| 1    | 1-3B      | Simple intent classification    | <200ms         |
| 2    | 7-8B      | Reasoning, multi-step planning  | <1s            |
| 3    | 32B+/Cloud| Complex tasks, code review      | <5s            |

Tier 0 always runs first. If no keyword match, escalation to Tier 1+ via
LLM function calling with OpenAI-compatible tools schema built dynamically
from registered skills.
