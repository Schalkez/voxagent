# 📋 VOXAGENT — Master Tasks

> Cập nhật lần cuối: 2026-04-04 (Phase 1 COMPLETE)
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

> Backbone ears → brain → hands → mouth. Pipeline fully wired.

- [x] `ears.py` — Voice Input Pipeline
  - [x] Mic listener loop (sounddevice, low CPU)
  - [x] Wake word detector (openWakeWord integration)
  - [x] Push-to-talk hotkey fallback (keyboard lib)
  - [x] Voice Activity Detection (Silero VAD)
  - [x] Pipe audio → STT provider
- [x] `brain.py` — Intent Router & Orchestrator
  - [x] Tier 0: keyword exact matching (TIER_0_KEYWORDS dict)
  - [x] Tier 1–2: LLM-based intent classification
  - [x] Skill dispatcher (match intent → skill.execute())
  - [x] Fallback chain logic (ollama → groq → openai)
- [x] `hands.py` — Action Execution Engine
  - [x] Execution strategy selector (Tier A → D)
  - [x] Safety gates (DANGEROUS_ACTIONS confirm trước khi thực hiện)
  - [x] Voice confirmation (TTS prompt + STT response)
- [x] `mouth.py` — TTS Output
  - [x] TTS provider dispatcher
  - [x] Response template system (`TEMPLATES` dict)
  - [x] Audio playback (sounddevice)
- [x] `app.py` — Entry Point & Lifecycle
  - [x] Pipeline wiring: ears → brain → hands → mouth
  - [x] Graceful startup / shutdown
  - [x] CLI: `voxagent start`, `voxagent setup`
- [x] `memory.py` — Database
  - [x] aiosqlite connection + schema
  - [x] Conversation CRUD
  - [x] Preferences CRUD

### 1.2 Provider Implementations (`agent/providers/`)

> All provider types implemented.

- [x] Provider base interfaces (`base.py`)
- [x] Provider registry (`registry.py`)
- [x] LLM providers (OpenAI, Groq, Anthropic, Ollama)
- [x] API key storage in OS keyring (`keyring_manager.py`)
- [x] STT providers (`providers/stt/`)
  - [x] Whisper local (faster-whisper)
  - [x] OpenAI Whisper API
- [x] TTS providers (`providers/tts/`)
  - [x] Edge TTS (Microsoft, free, Vietnamese voice)
- [ ] TTS — Piper local (Vietnamese voice) — deferred to Phase 2
- [x] LLM providers — functional chat + tool calling
  - [x] OpenAI: chat() + chat_with_tools()
  - [x] Groq: chat() + chat_with_tools()
  - [x] Ollama: chat() + chat_with_tools()
  - [x] Anthropic: chat() + chat_with_tools()

### 1.3 Skills — First 3 (`agent/skills/`)

> All 3 skills implemented.

- [x] `base.py` — BaseSkill, SkillResult, SkillContext
- [x] `media_control.py` — play, pause, skip, volume
  - [x] Tier A: ctypes media key simulation (Windows)
  - [x] Tier D fallback: keyboard lib
- [x] `app_launcher.py` — mở/tắt application
  - [x] Tier A: `os.startfile` / `subprocess`
  - [x] App name → executable mapping
- [x] `system_control.py` — shutdown, restart, sleep, lock
  - [x] Tier A: subprocess os commands (asyncio.to_thread)
  - [x] Safety gate integration (DANGEROUS_ACTIONS)

### 1.4 Platform Abstraction (`agent/system/`)

- [x] `base.py` — SystemAutomation interface
- [x] `windows.py` — Windows implementation
  - [x] `get_active_window()` — ctypes Win32 API
  - [x] `get_running_processes()` — psutil
  - [x] `set_volume()` / `get_volume()` — media key approximation
  - [/] `find_element()` — basic stub (full pywinauto in Phase 2)
  - [-] `read_notifications()` — deferred (UWP API complexity)

### 1.5 Config System (`agent/core/`)

- [x] `config.py` — YAML config loader
- [x] Config validation (dataclass types)
- [x] 4 built-in profiles: `full_local`, `cloud_free`, `hybrid`, `budget_cloud`
- [x] Profile switching: `voxagent start --profile <name>`
- [x] `~/.voxagent/config.yaml` auto-generation on first run
- [x] Setup wizard: `voxagent setup`

### 1.6 System Tray (`agent/`)

- [x] `tray.py` — pystray system tray app
  - [x] Tray icon with status indicator (green/gray)
  - [x] Menu: Start/Stop listening, Settings, Quit
  - [x] Launch dashboard in browser

### 1.7 CI/CD

- [x] GitHub Actions workflow (`.github/workflows/ci.yml`)
  - [x] Run `pytest` on push/PR
  - [x] Run `ruff check` + `mypy`
  - [x] Run `pnpm lint` + `pnpm build` for dashboard
  - [x] Coverage report upload

### 1.8 Tests

- [x] `test_hands.py` — Hands orchestration
- [x] `test_brain.py` — Brain tier routing
- [x] `test_mouth.py` — TTS templates + speak
- [x] `test_memory.py` — Database CRUD
- [x] `test_config.py` — Config load/save/profiles
- [x] `test_providers.py` — Registry + fallback chain
- [x] `test_skills.py` — All 3 skills + system volume
- [x] `test_api.py` — FastAPI endpoints

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
- [x] Settings (`/settings`) — fullstack
  - [x] Device settings UI (audio input/output, display, wake word)
  - [-] Profile selector
  - [x] Backend: `/api/settings` GET/PUT
- [x] Autopilot (`/autopilot`) — preview stub
  - [x] Coming Soon UI with mock task list
- [x] Memory (`/memory`) — preview stub
  - [x] Coming Soon UI with mock conversation history
- [x] Dashboard Home (`/`) — overview with real API integration
  - [x] HeroCard with live online/listening/offline status
  - [x] BentoGrid with live stats (commands, latency, skills)
  - [x] TerminalLog with command history
  - [x] useDashboardStatus hook polling /api/status

### 1.D.3 Code Quality

- [x] Separation of concerns: types/, constants/, utils/ per feature
- [x] Barrel re-export only in index.ts
- [x] Convention enforcement (voxagent-conventions SKILL.md)
- [x] Refactor providers feature — types/ and constants/ separation

---

## Phase 2 — Smart Brain

- [ ] LLM providers: DeepSeek, Mistral, OpenRouter
- [ ] Tier 1–2 smart routing (LLM-based complexity classification)
- [ ] Skills: `terminal.py`, `file_manager.py`, `browser_control.py`
- [ ] `memory.py` — Conversation memory encryption (SQLCipher)
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
