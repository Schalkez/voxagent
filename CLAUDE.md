<!-- GSD:project-start source:PROJECT.md -->
## Project

**VoxAgent**

VoxAgent is a voice-controlled desktop AI agent. It listens for "Hey Vox", transcribes speech, routes intents through a tiered model system (keyword matching -> small LLM -> large LLM), executes actions via a skill system, and responds via TTS. It runs locally on Windows/macOS/Linux with a Python backend and React dashboard. The architecture uses a human body metaphor: Ears (listen) -> Brain (think) -> Hands (act) -> Mouth (speak), with Eyes (see) and Memory (remember) as auxiliary modules.

**Core Value:** Voice-first desktop automation that actually works in real-world conditions — reliable wake word detection, fast response, graceful error handling, and safe action execution.

### Constraints

- **Language**: Python 3.12+ backend, TypeScript frontend (no changes)
- **Voice-only**: All improvements must serve the voice pipeline — no text/chat channels
- **Backward compatible**: Existing skills, providers, and config must continue working
- **Local-first**: Core functionality must work without cloud APIs (Ollama + Piper + faster-whisper)
- **Security**: No regression on existing safety measures (permission system, prompt injection detection)
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages & Runtimes
| Layer | Language | Version | Notes |
|-------|----------|---------|-------|
| Backend (Agent) | Python | 3.12+ | Async/await for all I/O, strict mypy typing |
| Frontend (Dashboard) | TypeScript | ~5.9.3 | Strict mode, `exactOptionalPropertyTypes: true` |
| Markup/Templates | JSX (React) | react-jsx | Via `@vitejs/plugin-react` |
| Configuration | YAML | - | `~/.voxagent/config.yaml` via PyYAML |
| Build/CI | YAML | - | GitHub Actions workflows |
## Backend Frameworks & Libraries
### Core Framework
| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | >=0.115 | REST API server for dashboard management |
| `uvicorn[standard]` | >=0.34 | ASGI server (host: 127.0.0.1, port: 8642) |
| `pydantic` | >=2.9 | Data validation (mypy override, FastAPI integration) |
### Audio Pipeline
| Package | Version | Purpose |
|---------|---------|---------|
| `sounddevice` | >=0.5.1 | Microphone input stream (InputStream) and audio playback |
| `numpy` | >=1.26 | Audio buffer manipulation (int16 arrays, RMS energy) |
| `pydub` | >=0.25 | MP3-to-WAV conversion for Edge TTS output |
| `openwakeword` | >=0.6 | Wake word detection ("hey vox"), ONNX backend (optional) |
| `silero-vad` | >=5.1 | Voice Activity Detection, ONNX backend (optional) |
| `onnxruntime` | >=1.19 | ONNX inference runtime for wake word + VAD models (optional) |
| `faster-whisper` | >=1.0 | Local STT via CTranslate2 Whisper backend (optional) |
| `edge-tts` | >=6.1 | Microsoft Edge free TTS service (Vietnamese support) |
### System & Desktop
| Package | Version | Purpose |
|---------|---------|---------|
| `psutil` | >=5.9 | Process listing, memory usage monitoring |
| `pystray` | >=0.19 | System tray icon with menu (start/stop/dashboard) |
| `Pillow` | >=10.0 | Screenshot capture (ImageGrab), tray icon generation |
| `keyring` | >=25.0 | OS credential manager (Windows Credential Locker, macOS Keychain, Linux SecretService) |
### Data & Networking
| Package | Version | Purpose |
|---------|---------|---------|
| `httpx` | >=0.28 | Async HTTP client for all LLM/STT/TTS API calls |
| `aiosqlite` | >=0.20 | Async SQLite for conversation memory and preferences |
| `pyyaml` | >=6.0 | YAML config loading/saving |
### Optional OCR Backends
| Package | Version | Purpose |
|---------|---------|---------|
| `paddleocr` | - | Primary OCR engine (best Vietnamese support) |
| `pytesseract` | - | Fallback OCR engine |
| `torch` | - | Required by Silero VAD model inference |
### Optional TTS Backends
| Package | Version | Purpose |
|---------|---------|---------|
| `piper-tts` | - | Local neural TTS via CLI subprocess (ONNX models) |
## Frontend Frameworks & Libraries
### Core
| Package | Version | Purpose |
|---------|---------|---------|
| `react` | ^19.2.4 | UI framework (functional components only) |
| `react-dom` | ^19.2.4 | DOM rendering |
| `react-router-dom` | ^7.14.0 | Client-side routing (7 views: dashboard, providers, routing, skills, settings, autopilot, memory) |
### Build & Dev Tooling
| Package | Version | Purpose |
|---------|---------|---------|
| `vite` | ^8.0.1 | Build tool and dev server |
| `tailwindcss` | ^4.2.2 | Utility-first CSS framework (via `@tailwindcss/vite` plugin) |
| `typescript` | ~5.9.3 | Type checking (strict mode) |
| `@vitejs/plugin-react` | ^6.0.1 | React Fast Refresh and JSX transform |
| `babel-plugin-react-compiler` | ^1.0.0 | React Compiler (automatic memoization) |
| `@rolldown/plugin-babel` | ^0.2.1 | Babel integration via Rolldown bundler |
### Linting & Formatting
| Package | Version | Purpose |
|---------|---------|---------|
| `eslint` | ^9.39.4 | JavaScript/TypeScript linting |
| `eslint-plugin-react-hooks` | ^7.0.1 | React hooks linting rules |
| `eslint-plugin-react-refresh` | ^0.5.2 | Fast Refresh boundary validation |
| `eslint-config-prettier` | ^10.1.8 | Disable ESLint rules conflicting with Prettier |
| `eslint-plugin-prettier` | ^5.5.5 | Run Prettier as an ESLint rule |
| `prettier` | ^3.8.1 | Code formatter |
| `typescript-eslint` | ^8.57.0 | TypeScript ESLint parser and rules |
## Python Dev Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `ruff` | >=0.8 | Linter + formatter (replaces black, isort, flake8) |
| `mypy` | >=1.13 | Static type checker (strict mode, Python 3.12) |
| `pytest` | >=8.3 | Test framework |
| `pytest-asyncio` | >=0.24 | Async test support (auto mode) |
| `pytest-cov` | >=6.0 | Code coverage reporting (fail_under=50) |
| `pre-commit` | >=4.0 | Git hook management |
| `bandit` | >=1.8 | Security vulnerability scanning |
| `interrogate` | >=1.7 | Docstring coverage enforcement (fail_under=80) |
| `vulture` | >=2.13 | Dead code detection |
## Build System
| Component | Tool | Notes |
|-----------|------|-------|
| Python packaging | `setuptools` >=75.0 | Via `pyproject.toml`, `[build-system]` |
| Python package format | `voxagent.egg-info` | Editable install (`pip install -e ".[dev]"`) |
| Frontend package manager | `pnpm` | Lock file: `pnpm-lock.yaml` |
| Frontend bundler | Vite 8 | With Rolldown + Babel plugins |
## Configuration Files
| File | Purpose |
|------|---------|
| `agent/pyproject.toml` | Python project config, dependencies, tool settings (ruff, mypy, pytest, bandit, interrogate, vulture) |
| `dashboard/package.json` | Frontend dependencies and scripts |
| `dashboard/tsconfig.json` | TypeScript project references |
| `dashboard/tsconfig.app.json` | App-level TS config (ES2023 target, strict mode, path aliases) |
| `dashboard/vite.config.ts` | Vite build config (Tailwind, React, Babel plugins, path aliases) |
| `.pre-commit-config.yaml` | Pre-commit hooks (ruff, mypy, bandit, interrogate, conventional commits) |
| `.github/workflows/ci.yml` | CI pipeline (lint, security, dead code, docstrings, tests) |
| `.github/dependabot.yml` | Automated dependency updates (pip, npm, GitHub Actions) |
| `.editorconfig` | Editor formatting consistency |
| `agent/config.example.yaml` | Example runtime configuration template |
| `docs/mkdocs.yml` | Documentation site config (MkDocs Material theme) |
## Path Aliases
### TypeScript (via tsconfig + vite)
- `@/*` -> `./src/*`
- `@features/*` -> `./src/features/*`
- `@shared/*` -> `./src/shared/*`
### Python (via ruff isort)
- First-party: `core`, `providers`, `system`, `skills`
## Runtime Configuration
- **Config location**: `~/.voxagent/config.yaml`
- **Database location**: `~/.voxagent/memory.db` (SQLite)
- **API keys**: OS keyring (service name: `voxagent`)
- **Built-in profiles**: `full_local`, `cloud_free`, `hybrid`, `budget_cloud`
- **Entry points**: `voxagent` (CLI agent), `voxagent-api` (REST server)
## CI/CD Pipeline
| Step | Tool | Scope |
|------|------|-------|
| Lint | `ruff check` | All Python in `agent/` |
| Security | `bandit` | `core/`, `skills/`, `api/` |
| Dead code | `vulture` | `core/`, `skills/`, `api/`, `tray.py` |
| Docstrings | `interrogate` | All Python (fail_under=80) |
| Tests | `pytest --cov` | `agent/tests/` |
| Platform | GitHub Actions | `ubuntu-latest`, Python 3.12 |
| Triggers | Push/PR to `main`/`master` | Plus `workflow_dispatch` |
## Architecture Summary
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## 1. Language & Runtime
| Layer | Stack | Version |
|-------|-------|---------|
| Backend (Agent) | Python | 3.12+ (`target-version = "py312"`) |
| Frontend (Dashboard) | TypeScript + React | TS ~5.9, React 19+ |
| Formatter (Python) | ruff | `line-length = 100`, double quotes, spaces |
| Formatter (TS/CSS) | prettier | Default config via eslint-plugin-prettier |
| Linter (Python) | ruff (E, F, W, I, N, UP, B, A, SIM, ASYNC, PTH, RUF) | Strict rule set |
| Linter (TS) | typescript-eslint | strict + stylistic configs |
| Type Checker | mypy (`strict = true`) | `disallow_untyped_defs = true` |
| Package Manager (FE) | pnpm | Lockfile: `pnpm-lock.yaml` |
## 2. Project Structure & Module Boundaries
### Python Backend (`agent/`)
- `core/` NEVER imports concrete providers; it accesses them through `ProviderRegistry`.
- `providers/` implementations MUST inherit ABCs from `providers/base.py`.
- `skills/` implementations MUST inherit `BaseSkill` from `skills/base.py`.
- `system/` implementations MUST inherit `SystemAutomation` from `system/base.py`.
- Cross-layer imports flow downward: `api/ -> core/ -> providers/ (via registry)`.
### React Dashboard (`dashboard/src/`)
## 3. Naming Conventions
### Python
| Element | Convention | Example |
|---------|-----------|---------|
| Module files | `snake_case.py` | `groq_provider.py`, `media_control.py` |
| Classes | `PascalCase` | `Brain`, `ProviderRegistry`, `MediaControlSkill` |
| Functions / Methods | `snake_case` | `load_config()`, `chat_with_tools()` |
| Constants | `SCREAMING_SNAKE_CASE` | `MAX_INPUT_LENGTH`, `COMMAND_TIMEOUT_S`, `VK_MEDIA_PLAY_PAUSE` |
| Private members | Leading underscore | `self._running`, `self._db`, `_parse_tier()` |
| Type aliases | `PascalCase` | `VoxAgentConfig`, `SkillResult` |
| Logger instances | `logging.getLogger("voxagent.<module>")` | `logger = logging.getLogger("voxagent.brain")` |
| Boolean variables | `is_` / `has_` prefix (properties) | `is_active`, `is_loaded`, `_connected` |
### TypeScript / React
| Element | Convention | Example |
|---------|-----------|---------|
| Component files | `PascalCase/PascalCase.tsx` | `HeroCard/HeroCard.tsx` |
| Hook files | `camelCase.ts` | `useDashboardStatus.ts` |
| Type files | `kebab.types.ts` | `dashboard.types.ts`, `routing.types.ts` |
| Interfaces | `PascalCase` | `DashboardStatus`, `ProviderInfo` |
| Constants | `SCREAMING_SNAKE_CASE` | `POLL_INTERVAL_MS`, `API_BASE` |
| Components | Named exports, `React.FC` | `export const DashboardView: React.FC` |
| Hooks | `use` prefix, named export | `export function useDashboardStatus()` |
## 4. Import Conventions
### Python
- `from __future__ import annotations` at the top of every module (deferred evaluation).
- `TYPE_CHECKING` guard for circular/heavy imports: only used for type hints.
- Import order enforced by ruff isort: stdlib -> third-party -> first-party (`core`, `providers`, `system`, `skills`).
- Concrete providers are imported dynamically inside `try/except ImportError` blocks (graceful degradation).
### TypeScript
- **BANNED**: Relative parent imports (`../`). ESLint rule enforces this.
- **REQUIRED**: Path aliases `@shared/*`, `@features/*` (configured in `vite.config.ts`).
- Barrel `index.ts` files MUST ONLY contain re-exports. No inline definitions.
## 5. Data Modeling
### Frozen Dataclasses (Python)
### Pydantic Models (API Layer Only)
### TypeScript Interfaces
## 6. Error Handling Patterns
### Exception Hierarchy
### Catch Strategies
### Error Propagation
- `core/` and `skills/` return result objects (`SkillResult`, `Intent`) with error fields instead of raising.
- `api/` raises `VoxAPIException` subclasses which are caught by the global exception handler.
- Provider failures propagate `ProviderNotFoundError` (KeyError subclass).
## 7. Async Patterns
- All I/O-bound operations are `async/await`.
- CPU-bound or blocking stdlib calls use `asyncio.to_thread()`:
- Lazy imports of heavy libraries inside functions (e.g., `from PIL import ImageGrab` inside method body).
- `httpx.AsyncClient` for all HTTP calls with explicit timeout.
## 8. Security Conventions
- API keys stored in OS keyring (`keyring` library), NEVER in config files or env vars.
- `core/keyring_manager.py` wraps all keyring access behind `save_key()`, `get_key()`, `delete_key()`.
- `PromptGuard` in `core/safety.py` detects prompt injection via compiled regex patterns.
- Terminal command execution uses an allowlist (`ALLOWED_COMMAND_PREFIXES`), blocks dangerous shell chars, and applies Unicode normalization (`NFKC`) to prevent bypass.
- `DANGEROUS_ACTIONS` frozenset in Hands requires voice confirmation before execution.
- Permission system (`PermissionLevel.DANGEROUS`) blocks skills without explicit grants.
- `shell=False` enforced for subprocess execution.
## 9. Design Patterns
### Registry / Factory
- `ProviderRegistry`: Central factory for LLM/STT/TTS/Vision providers with instance caching and fallback chain.
- `SkillRegistry`: Singleton with `@register_skill` decorator for auto-registration. Plugin discovery via `pkgutil.walk_packages`.
- `system/factory.py`: Singleton factory for platform-specific `SystemAutomation` implementations.
### Strategy / Tiered Execution
- **Brain Tier System**: Tier 0 (keyword) -> Tier 1 (small LLM) -> Tier 2 (medium) -> Tier 3 (large/cloud). Cheapest first, escalate on failure.
- **Hands Execution Tiers**: A (Native API) -> B (App API) -> C (UI Automation) -> D (Keyboard). Skills declare supported tiers.
- **Eyes Layered Vision**: Layer 1 (UI tree) -> Layer 2 (OCR with 5s cache) -> Layer 3 (Vision LLM).
### Pipeline / Orchestrator
- Main pipeline: `EARS -> BRAIN -> HANDS -> MOUTH` (orchestrated by `VoxAgentApp._run_loop`).
- Each module is a single-responsibility orchestrator delegating to sub-components.
- `Ears` delegates to `AudioRecorder`, `WakeWordDetector`, `VoiceActivityDetector`, `AudioConverter`.
### Observer / Callback
- `Ears._event_callbacks`: list of callables notified on state changes via `_emit()`.
### Dependency Injection
- Providers injected via constructor: `Ears(stt_provider=...)`, `Mouth(tts_provider=...)`.
- `Hands` accepts optional `Mouth` and `Ears` for voice confirmation flow.
- `Brain` receives `ProviderRegistry` and skill list.
## 10. Docstring & Documentation
- **Every module** starts with a docstring explaining purpose and context.
- **Every public class** has a docstring with description.
- **Every public method** has a docstring with `Args:`, `Returns:`, and optionally `Raises:`.
- **Dataclass attributes** documented in the class docstring `Attributes:` section.
- Format: Google-style docstrings.
- Tool: `interrogate` enforces >= 80% docstring coverage.
- Section dividers use `# -- Section Name --` comments.
- Tier 0: Keyword pattern matching (no LLM, < 50ms)
- Tier 1: Small LLM for simple intents (1-3B params)
## 11. Constants Organization
## 12. Logging
- Hierarchical logger names: `voxagent.brain`, `voxagent.ears`, `voxagent.skills.media_control`.
- `%s` formatting (lazy evaluation): `logger.info("Transcription: '%s'", result.text)`.
- Levels: `DEBUG` for trace, `INFO` for operations, `WARNING` for recoverable errors, `ERROR` for failures.
- `logger.exception()` auto-includes stack trace.
## 13. Frontend Patterns
### Component Architecture (Atomic Design)
- **Atoms**: `Text`, `Badge`, `Dot`, `Icon`, `Input`, `Switch`, `Slider`, `Avatar`, `ProgressBar`
- **Molecules**: `Card`, `NavItem`, `Breadcrumb`, `StatusBadge`, `Select`
- **Organisms**: Feature-specific composites (`HeroCard`, `BentoGrid`, `TerminalLog`, `ProviderCard`)
- **Templates**: Layout wrappers (`MainLayout`)
- **Containers**: Thin glue components connecting hooks to organisms
### State Management
- No global state library; each feature uses local hooks (`useState`, `useCallback`, `useEffect`).
- Polling pattern with `setInterval` + cleanup in `useEffect`.
- Default state constants defined at module scope.
### API Communication
- Single generic `fetchApi<T>()` function in `@shared/api/client.ts`.
- API base URL from `VITE_API_URL` env var with `http://localhost:8642` fallback.
- Error handling: check `resp.ok`, throw `Error` with status + body text.
## 14. Configuration
- YAML-based config at `~/.voxagent/config.yaml`.
- 4 built-in profiles: `full_local`, `cloud_free`, `hybrid`, `budget_cloud`.
- Atomic writes via `NamedTemporaryFile` + `Path.replace()`.
- CORS origins from `CORS_ORIGINS` env var (comma-separated).
- FastAPI lifespan pattern for startup/teardown.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern
## Layers
### Layer 1: Core Pipeline (`agent/core/`)
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
| Sub-layer          | Base Class       | Implementations                                                   |
|--------------------|------------------|-------------------------------------------------------------------|
| LLM Providers      | `LLMProvider`    | `openai`, `groq`, `anthropic`, `ollama`, `deepseek`, `mistral`, `openrouter` |
| STT Providers      | `STTProvider`    | `whisper_local` (faster-whisper), `openai_whisper`                |
| TTS Providers      | `TTSProvider`    | `edge_tts`, `piper`, `elevenlabs_clone`                          |
| Vision Providers   | `VisionProvider` | `openai_vision`, `anthropic_vision`, `gemini_vision`             |
| Registry           | --               | `ProviderRegistry` (factory + instance cache + fallback chain)   |
- `LLMProvider.chat()` -- text completion
- `LLMProvider.chat_with_tools()` -- function calling (used by Brain for intent extraction)
- `LLMProvider.health_check()` -- availability probing (used by fallback chain)
- `STTProvider.transcribe()` -- audio bytes -> `TranscribeResult`
- `TTSProvider.synthesize()` -- text -> WAV bytes
- `VisionProvider.analyze_image()` -- image bytes + prompt -> text analysis
### Layer 3: Skills (`agent/skills/`)
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
### Layer 4: System Abstraction (`agent/system/`)
| Module        | Platform  | Implementation                             |
|---------------|-----------|--------------------------------------------|
| `base.py`     | --        | Abstract interface: get_active_window, find_element, get_running_processes, read_notifications, set/get_volume |
| `windows.py`  | Windows   | pywinauto + win32gui + ctypes              |
| `macos.py`    | macOS     | pyobjc + Accessibility API + osascript     |
| `linux.py`    | Linux     | AT-SPI (atspi2) + xdotool                 |
| `factory.py`  | --        | Platform detection factory with lazy init  |
### Layer 5: API Server (`agent/api/`)
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
| Route         | Feature Module             | Description                    |
|---------------|----------------------------|--------------------------------|
| `/dashboard`  | `features/dashboard/`      | Overview with bento grid, hero card, terminal log |
| `/providers`  | `features/providers/`      | Provider cards, Ollama config, quota stats |
| `/routing`    | `features/routing/`        | Tier configuration, preset selection |
| `/skills`     | `features/skills/`         | Skill cards, enable/disable, add skill |
| `/settings`   | `features/settings/`       | Audio settings, security card  |
| `/autopilot`  | `features/autopilot/`      | Background task management     |
| `/memory`     | `features/memory/`         | Conversation history viewer    |
## Data Flow
### Primary Voice Pipeline
```
```
### Multi-Step Command Flow (Planner)
```
```
### API/Dashboard Flow
```
```
### Screen Understanding Flow (Eyes)
```
```
## Abstractions
### Provider Abstraction Boundary
```
```
- **Lazy instantiation:** Providers are created on first `.get_*()` call
- **Instance caching:** Avoids repeated keyring lookups for API keys
- **Fallback chain:** `get_llm_with_fallback()` iterates configured providers, health-checking each
### Skill Abstraction Boundary
```
```
- `name`, `description`, `keywords` (for Tier 0)
- `execution_tiers` (ordered list: which tiers this skill supports)
- `permissions` (list of permission strings: "media:control", "terminal:write", etc.)
### System Abstraction Boundary
```
```
### Configuration Abstraction
```
```
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
```
### CI/CD
- `.github/workflows/ci.yml` -- GitHub Actions CI pipeline
- `.pre-commit-config.yaml` -- Pre-commit hooks (ruff, mypy, etc.)
- `.github/dependabot.yml` -- Dependency update automation
## Tiered Execution Strategy
| Tier | Name        | Method                                  | Latency  | Cost |
|------|-------------|-----------------------------------------|----------|------|
| A    | NATIVE_API  | subprocess, ctypes, win32api, osascript | <100ms   | Free |
| A'   | SHELL       | Shell commands via subprocess            | <200ms   | Free |
| B    | APP_API     | Playwright CDP, REST APIs, native APIs  | <500ms   | Free |
| C    | UI          | pywinauto, pyobjc Accessibility, AT-SPI | <1s      | Free |
| D    | KEYBOARD    | PyAutoGUI mouse/keyboard simulation     | <2s      | Free |
## LLM Tier Routing
| Tier | Size      | Use Case                        | Latency Target |
|------|-----------|---------------------------------|----------------|
| 0    | None      | Keyword pattern matching        | <50ms          |
| 1    | 1-3B      | Simple intent classification    | <200ms         |
| 2    | 7-8B      | Reasoning, multi-step planning  | <1s            |
| 3    | 32B+/Cloud| Complex tasks, code review      | <5s            |
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
