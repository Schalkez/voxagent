# 📋 VOXAGENT — Master Tasks

> Cập nhật lần cuối: 2026-04-04
> Baselines: [ROADMAP.md](docs/ROADMAP.md) | [ARCHITECTURE.md](docs/ARCHITECTURE.md) | [SKILL_DEVELOPMENT_GUIDE.md](docs/SKILL_DEVELOPMENT_GUIDE.md)

---

## Legend

- `[ ]` — chưa bắt đầu
- `[/]` — đang làm
- `[x]` — hoàn thành
- `[-]` — skip / defer

---

## Phase 1 — Enterprise Core Foundation: Voice Command & Respond

**Goal:** Nói lệnh đơn giản, VoxAgent thực hiện và trả lời bằng giọng.

### 1.1 Core Pipeline (`agent/core/`)

> Backbone ears → brain → hands → mouth. Các file đã có skeleton, cần implement logic thật.

- [ ] `ears.py` — Voice Input Pipeline
  - [ ] Mic listener loop (sounddevice, low CPU)
  - [ ] Wake word detector (openWakeWord integration)
  - [ ] Push-to-talk hotkey fallback (keyboard lib)
  - [ ] Voice Activity Detection (Silero VAD)
  - [ ] Pipe audio → STT provider
- [ ] `brain.py` — Intent Router & Orchestrator
  - [ ] Tier 0: keyword exact matching (TIER_0_KEYWORDS dict)
  - [ ] Tier 1–2: LLM-based intent classification
  - [ ] Skill dispatcher (match intent → skill.execute())
  - [ ] Fallback chain logic (ollama → groq → openai)
- [ ] `hands.py` — Action Execution Engine
  - [ ] Execution strategy selector (Tier A → D)
  - [ ] Safety gates (DANGEROUS_ACTIONS confirm trước khi thực hiện)
  - [ ] Keyboard/mouse abstraction (PyAutoGUI wrapper)
- [ ] `mouth.py` — TTS Output
  - [ ] TTS provider dispatcher
  - [ ] Response template system (`TEMPLATES` dict)
  - [ ] Audio playback (sounddevice)
- [ ] `app.py` — Entry Point & Lifecycle
  - [ ] Pipeline wiring: ears → brain → hands → mouth
  - [ ] Graceful startup / shutdown
  - [ ] CLI: `voxagent start`, `voxagent setup`

### 1.2 Provider Implementations (`agent/providers/`)

> Base interfaces ✅ done. Cần implement concrete providers.

- [x] Provider base interfaces (`base.py`)
- [x] Provider registry (`registry.py`)
- [x] LLM providers skeleton (OpenAI, Groq, Anthropic, Ollama)
- [x] API key storage in OS keyring (`keyring_manager.py`)
- [ ] STT providers (`providers/stt/`)
  - [ ] Whisper local (faster-whisper)
  - [ ] OpenAI Whisper API
- [ ] TTS providers (`providers/tts/`)
  - [ ] Piper local (Vietnamese voice)
  - [ ] Edge TTS (Microsoft, free)
- [ ] LLM providers — functional chat + tool calling
  - [ ] OpenAI: chat() + chat_with_tools()
  - [ ] Groq: chat() + chat_with_tools()
  - [ ] Ollama: chat() + chat_with_tools()
  - [ ] Anthropic: chat() + chat_with_tools()

### 1.3 Skills — First 3 (`agent/skills/`)

> `base.py` ✅ done. Cần implement 3 skills + manifests.

- [x] `base.py` — BaseSkill, SkillResult, SkillContext
- [ ] `media_control.py` — play, pause, skip, volume
  - [ ] Tier A: `ctypes` / `osascript` (native volume control)
  - [ ] Tier D fallback: media keys via keyboard lib
  - [ ] `media_control.json` manifest
- [ ] `app_launcher.py` — mở/tắt application
  - [ ] Tier A: `subprocess.Popen` / `os.startfile`
  - [ ] App name → executable mapping
  - [ ] `app_launcher.json` manifest
- [ ] `system_control.py` — shutdown, restart, sleep, lock
  - [ ] Tier A: `subprocess` os commands
  - [ ] Safety gate integration (DANGEROUS_ACTIONS)
  - [ ] `system_control.json` manifest

### 1.4 Platform Abstraction (`agent/platform/`)

> `base.py` ✅ done. Cần implement Windows.

- [x] `base.py` — SystemAutomation interface
- [ ] `windows.py` — Windows implementation
  - [ ] `get_active_window()` — pywinauto/win32gui
  - [ ] `find_element()` — UI automation element search
  - [ ] `get_running_processes()` — psutil
  - [ ] `read_notifications()` — Win32 notification center

### 1.5 Config System (`agent/core/`)

- [x] `config.py` — YAML config loader (skeleton exists)
- [ ] Config validation (Pydantic models)
- [ ] 4 built-in profiles: `full_local`, `cloud_free`, `hybrid`, `budget_cloud`
- [ ] Profile switching: `voxagent start --profile <name>`
- [ ] `~/.voxagent/config.yaml` auto-generation on first run

### 1.6 System Tray (`agent/`)

- [ ] `tray.py` — pystray system tray app
  - [ ] Tray icon with status indicator
  - [ ] Menu: Start/Stop listening, Settings, Quit
  - [ ] Launch dashboard in browser

### 1.7 CI/CD

- [ ] GitHub Actions workflow (`.github/workflows/ci.yml`)
  - [ ] Run `pytest` on push/PR
  - [ ] Run `ruff check` + `mypy`
  - [ ] Run `pnpm lint` + `pnpm build` for dashboard
  - [ ] Coverage report upload

---

## Phase 1 — Dashboard (`dashboard/`)

> React dashboard cho monitoring, config, skill management.

### 1.D.1 Shared Components (`shared/`)

- [x] Design system (Tailwind CSS v4 + custom tokens)
- [x] Atoms: Input, Select, Switch, Slider, Icon, Badge
- [x] Molecules: Breadcrumb, StatusIndicator
- [x] Organisms: Sidebar, Topbar
- [x] Templates: MainLayout
- [x] API client (`shared/api/client.ts`)
- [x] ESLint strict imports (path aliases enforced)

### 1.D.2 Feature Screens

- [x] Providers (`/providers`) — fullstack
  - [x] ProviderCard, OllamaCard, QuotaStats organisms
  - [x] useProviders hooks + API integration
  - [x] Backend: `/api/providers`, `/api/keys`, `/api/health`
- [x] Routing (`/routing`) — fullstack
  - [x] RoutingPresetCard, TierCard, RoutingStatusChip organisms
  - [x] useRouting hooks + API integration
  - [x] Backend: `/api/routing` GET/PUT
- [x] Skills (`/skills`) — fullstack
  - [x] SkillCard, AddSkillCard, SkillsFooter organisms
  - [x] useSkills + useToggleSkill hooks
  - [x] Backend: `/api/skills`, `/api/skills/{id}/toggle`
- [ ] Settings (`/settings`) — fullstack
  - [ ] Device settings UI (audio input/output, display, wake word)
  - [ ] Profile selector
  - [ ] Backend: `/api/settings` GET/PUT
- [ ] Autopilot (`/autopilot`) — fullstack
  - [ ] Task list, trigger config, execution log
  - [ ] Backend: `/api/autopilot/tasks` CRUD
- [ ] Memory (`/memory`) — fullstack
  - [ ] Conversation history viewer
  - [ ] Preference editor
  - [ ] Backend: `/api/memory/conversations`, `/api/memory/preferences`
- [ ] Dashboard Home (`/`) — overview
  - [ ] System status overview
  - [ ] Active skills count, last command, uptime

### 1.D.3 Code Quality

- [x] Separation of concerns: types/, constants/, utils/ per feature
- [x] Barrel re-export only in index.ts
- [x] Convention enforcement (voxagent-conventions SKILL.md)
- [ ] Refactor providers feature — apply same types/constants separation

---

## Phase 2 — Smart Brain

- [ ] LLM providers: DeepSeek, Mistral, OpenRouter
- [ ] Tier 1–2 smart routing (LLM-based complexity classification)
- [ ] Skills: `terminal.py`, `file_manager.py`, `browser_control.py`
- [ ] `memory.py` — Conversation memory (SQLite + SQLCipher encryption)
- [ ] Multi-step action planning (brain)
- [ ] Fallback chain (auto-switch provider khi fail)
- [ ] Skill permission system — runtime enforcement
- [ ] macOS platform implementation (pyobjc + Accessibility API)
- [ ] Unit test coverage ≥ 70% cho core modules

---

## Phase 3 — Eyes & Autopilot

- [ ] `eyes.py` — Screen capture + Win32 / macOS Accessibility
- [ ] OCR: PaddleOCR (tiếng Việt) + Tesseract fallback
- [ ] Vision providers: GPT-4o, Claude, Gemini, Qwen-VL local
- [ ] Skills: `screen_reader.py`, `code_reviewer.py`
- [ ] `autopilot.py` — Background task engine (time/event/condition/idle triggers)
- [ ] Prompt injection protection
- [ ] Linux platform (AT-SPI) — experimental
- [ ] Benchmark suite: latency per tier, STT accuracy

---

## Phase 4 — Polish & Community

- [ ] Windows installer (.exe) + auto-update
- [ ] macOS .dmg + Homebrew formula
- [ ] `pip install voxagent-agent` packaging
- [ ] Skill marketplace (skill.json registry + review process)
- [ ] Documentation site (MkDocs)
- [ ] Custom wake word training UI
- [ ] Multi-language support (i18n)
- [ ] Opt-in telemetry

---

## Phase 5 — Scale (Q3+)

- [ ] Mobile companion app
- [ ] Multi-device sync
- [ ] VoxAgent API server mode (home automation, n8n)
- [ ] Custom voice cloning TTS
- [ ] Multi-language conversation
- [ ] LLM fine-tuning trên lệnh user
