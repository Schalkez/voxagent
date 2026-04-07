# VOXAGENT — Master Tasks

> Updated: 2026-04-07 (All Phases COMPLETE — Verified)
> Baselines: [ROADMAP.md](docs/ROADMAP.md) | [ARCHITECTURE.md](docs/ARCHITECTURE.md) | [SKILL_DEVELOPMENT_GUIDE.md](docs/SKILL_DEVELOPMENT_GUIDE.md)

---

## Legend

- `[x]` — complete (real implementation)
- `[~]` — implemented but limited scope (documented below)
- `[-]` — deferred / out of scope

---

## Phase 1 — Enterprise Core Foundation

### 1.1 Core Pipeline (`agent/core/`)

- [x] `ears.py` — Voice Input Pipeline (mic, wake word, VAD, STT)
- [x] `brain.py` — Intent Router (Tier 0 keyword + Tier 1-2 LLM)
- [x] `hands.py` — Action Execution (Tier A-D, safety gates, permission enforcement)
- [x] `mouth.py` — TTS Output (provider dispatch, templates, audio playback)
- [x] `app.py` — Entry Point (pipeline wiring, CLI)
- [x] `memory.py` — Database (aiosqlite, conversation + preferences CRUD)

### 1.2 Providers (`agent/providers/`)

- [x] Base interfaces + registry
- [x] LLM: OpenAI, Groq, Anthropic, Ollama (chat + tool calling)
- [x] STT: Whisper local + OpenAI API
- [x] TTS: Edge TTS (Vietnamese voice)
- [x] API key storage in OS keyring

### 1.3 Skills (`agent/skills/`)

- [x] `base.py` — BaseSkill, SkillResult, SkillIntent
- [x] `media_control.py` — play, pause, skip, volume
- [x] `app_launcher.py` — open/close application
- [x] `system_control.py` — shutdown, restart, sleep, lock

### 1.4 Platform (`agent/system/`)

- [x] `base.py` — SystemAutomation interface
- [x] `windows.py` — Win32 API (ctypes)
- [x] `factory.py` — Platform factory

### 1.5 Config + Tray + CI

- [x] YAML config + 4 profiles + setup wizard
- [x] System tray (pystray)
- [x] GitHub Actions CI (pytest, ruff, pnpm build)
- [x] LICENSE (Apache 2.0)

### 1.6 Dashboard (`dashboard/`)

- [x] Full React dashboard (providers, routing, skills, settings, autopilot, memory)
- [x] Builds clean (`pnpm build`)

### 1.7 Tests

- [x] 253 tests passing, 80.65% coverage

---

## Phase 2 — Smart Brain

- [x] LLM providers: DeepSeek, Mistral, OpenRouter
- [x] Skills: `terminal.py` (shell commands + blocked patterns)
- [x] Skills: `file_manager.py` (list, search, move, copy, delete)
- [x] Skills: `browser_control.py` (open URLs, web search)
- [x] Skill permission system (`permissions.py`) — **enforced at runtime in hands.py**
- [x] `planner.py` — Multi-step action planning (LLM-based sequence detection)
- [-] Memory encryption (SQLCipher) — deferred (optional dependency)

---

## Phase 3 — Eyes & Autopilot

- [x] `eyes.py` — Layered screen understanding (UI tree -> OCR -> Vision LLM)
- [x] `ocr.py` — PaddleOCR + Tesseract fallback
- [x] Vision providers: OpenAI (GPT-4o), Anthropic (Claude), Gemini
- [x] Skills: `screen_reader.py`, `code_reviewer.py`
- [x] `autopilot.py` — Background task engine (time/event/condition/idle triggers, retry)
- [x] `safety.py` — Prompt injection protection (15 regex patterns + sanitize)
- [x] `system/macos.py` — osascript + System Events `find_element()` via Accessibility
- [x] `system/linux.py` — xdotool + wmctrl `find_element()` via window search
- [~] macOS `find_element` — uses AppleScript/System Events (not native pyobjc)
- [~] Linux `find_element` — uses xdotool window search (not AT-SPI)
- [-] Benchmark suite — created (`benchmarks/`) but requires runtime environment

---

## Phase 4 — Polish & Community

- [x] Windows installer (`scripts/build_installer.py`) — PyInstaller config
- [x] Documentation site (`docs/mkdocs.yml` + 5 pages)
- [x] i18n system (`core/i18n.py`) — vi + en, 22 translation strings
- [x] Skill marketplace (`skills/marketplace.py`) — **real install/publish/uninstall**
  - [x] Local file-based install (copy .py into skills/)
  - [x] Remote registry install (download from registry API)
  - [x] Publish to registry (upload source + metadata)
  - [x] Uninstall (remove file + manifest entry)
- [x] Plugin dependency resolver (`skills/dependency_resolver.py`)
  - [x] Parse string and dict dependency formats
  - [x] Check installed via importlib
  - [x] Auto-install missing via pip subprocess
- [x] Opt-in telemetry (`core/telemetry.py`) — anonymous, disabled by default
- [-] macOS .dmg installer — deferred (requires macOS build environment)
- [-] Linux Flatpak/Snap — deferred (requires Linux build environment)

---

## Phase 5 — Scale

- [x] API server mode (`api/server_mode.py`)
  - [x] `POST /api/command` endpoint
  - [x] API key auth via `X-VoxAgent-Key` header
  - [x] In-memory rate limiting (60 req/min per IP)
  - [x] `GET /api/server/health` endpoint
- [x] Multi-device sync (`core/sync.py`) — **real file-based sync**
  - [x] Shared directory sync (Dropbox/OneDrive/LAN compatible)
  - [x] Device registration with persistent ID
  - [x] Preference merge (last-writer-wins)
  - [x] Device listing and removal
- [x] Voice cloning (`providers/tts/elevenlabs_clone.py`) — **ElevenLabs API**
  - [x] `synthesize()` via /text-to-speech endpoint
  - [x] `clone_voice()` via /voices/add (multipart upload)
  - [x] `list_cloned_voices()` and `delete_voice()`
- [x] Multi-language (`core/language.py`) — 5 languages (vi/en/ja/ko/zh)
- [x] Custom wake word training (`scripts/train_wake_word.py`)
  - [x] Sample validation, negative sample generation
  - [x] Training config YAML generation for openWakeWord
- [-] Mobile companion app — deferred (separate project)
- [-] LLM fine-tuning — deferred (research phase)

---

## Verification Summary (2026-04-07)

| Check | Result |
|-------|--------|
| Tests | **253 passed** |
| Coverage | **80.65%** (threshold: 80%) |
| Lint (ruff) | **All checks passed** |
| Dashboard build | **Clean** |
| LICENSE | Apache 2.0 |
| CI workflow | Correct |

## Files Created/Modified This Session

### New Production Files (by GSD + Claude Code)
- `agent/core/planner.py` — Multi-step action planner (GSD)
- `agent/skills/dependency_resolver.py` — Plugin dependency resolver
- `agent/providers/tts/elevenlabs_clone.py` — ElevenLabs voice cloning (GSD)
- `agent/scripts/train_wake_word.py` — Wake word training helper (GSD)
- `agent/benchmarks/bench_tiers.py` — Tier latency benchmarks (GSD)
- `agent/benchmarks/bench_stt.py` — STT accuracy benchmarks (GSD)

### Modified Production Files
- `agent/core/hands.py` — Added PermissionManager enforcement
- `agent/core/sync.py` — Replaced stub with file-based sync
- `agent/skills/marketplace.py` — Replaced stubs with real install/publish/uninstall
- `agent/system/macos.py` — Real find_element via osascript (GSD)
- `agent/system/linux.py` — Real find_element via xdotool (GSD)
- `agent/api/server_mode.py` — Added auth + rate limiting (GSD)

### New Test Files
- `agent/tests/test_remaining_features.py` — 27 tests for new features
- `agent/tests/test_push_80.py` — Coverage push tests
