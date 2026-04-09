# Technology Stack

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

```
agent/                      # Python backend
  core/                     # Provider-agnostic domain logic
    audio/                  # Recorder, VAD, wake word, converter
    app.py                  # Main orchestrator (EARS->BRAIN->HANDS->MOUTH)
    brain.py                # Tiered LLM routing (Tier 0-3)
    ears.py                 # Voice input pipeline
    mouth.py                # TTS output with Vietnamese templates
    hands.py                # Tiered action execution (Tier A-D)
    eyes.py                 # Layered screen understanding (UI tree->OCR->Vision)
    memory.py               # SQLite conversation/preference storage
    config.py               # YAML config loader with profiles
    autopilot.py            # Background task scheduling
    keyring_manager.py      # OS credential management
    ocr.py                  # PaddleOCR + Tesseract engine
    i18n.py                 # Vietnamese/English translations
    telemetry.py            # Opt-in anonymous usage analytics
  providers/                # LLM/STT/TTS/Vision provider implementations
    base.py                 # Abstract base classes (LLMProvider, STTProvider, etc.)
    registry.py             # Provider factory with fallback chain
    stt/                    # Speech-to-text providers
    tts/                    # Text-to-speech providers
  skills/                   # Extensible skill system
  system/                   # OS-specific automation (Windows, macOS, Linux)
  api/                      # FastAPI REST endpoints
    routers/                # Providers, routing, skills, settings endpoints
  tests/                    # pytest test suite

dashboard/                  # React/TypeScript frontend
  src/
    features/               # Feature-based module structure
      dashboard/            # Home dashboard view
      providers/            # Provider management
      routing/              # Tier routing configuration
      skills/               # Skill management
      settings/             # System settings
      autopilot/            # Background task management
      memory/               # Conversation history

scripts/                    # Build and utility scripts
docs/                       # MkDocs documentation site
tests/                      # Root-level integration tests
```
