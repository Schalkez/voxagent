# VOXAGENT — Master Tasks

> Updated: 2026-04-06 (All Phases COMPLETE)
> Baselines: [ROADMAP.md](docs/ROADMAP.md) | [ARCHITECTURE.md](docs/ARCHITECTURE.md) | [SKILL_DEVELOPMENT_GUIDE.md](docs/SKILL_DEVELOPMENT_GUIDE.md)

---

## Legend

- `[ ]` — not started
- `[/]` — in progress
- `[x]` — complete
- `[-]` — skip / defer

---

## Phase 1 — Enterprise Core Foundation: Voice Command & Respond

**Goal:** Voice commands, VoxAgent executes and responds.

### 1.1 Core Pipeline (`agent/core/`)

- [x] `ears.py` — Voice Input Pipeline
  - [x] Mic listener loop (sounddevice, low CPU)
  - [x] Wake word detector (openWakeWord integration)
  - [x] Push-to-talk hotkey fallback (keyboard lib)
  - [x] Voice Activity Detection (Silero VAD)
  - [x] Pipe audio to STT provider
- [x] `brain.py` — Intent Router & Orchestrator
  - [x] Tier 0: keyword exact matching (TIER_0_KEYWORDS dict)
  - [x] Tier 1-2: LLM-based intent classification
  - [x] Skill dispatcher (match intent to skill.execute())
  - [x] Fallback chain logic (ollama to groq to openai)
- [x] `hands.py` — Action Execution Engine
  - [x] Execution strategy selector (Tier A to D)
  - [x] Safety gates (DANGEROUS_ACTIONS confirm before execution)
  - [x] Voice confirmation (TTS prompt + STT response)
- [x] `mouth.py` — TTS Output
  - [x] TTS provider dispatcher
  - [x] Response template system (TEMPLATES dict)
  - [x] Audio playback (sounddevice)
- [x] `app.py` — Entry Point & Lifecycle
  - [x] Pipeline wiring: ears to brain to hands to mouth
  - [x] Graceful startup / shutdown
  - [x] CLI: `voxagent start`, `voxagent setup`
- [x] `memory.py` — Database
  - [x] aiosqlite connection + schema
  - [x] Conversation CRUD
  - [x] Preferences CRUD

### 1.2 Provider Implementations (`agent/providers/`)

- [x] Provider base interfaces (`base.py`)
- [x] Provider registry (`registry.py`)
- [x] LLM providers (OpenAI, Groq, Anthropic, Ollama)
- [x] API key storage in OS keyring (`keyring_manager.py`)
- [x] STT providers (`providers/stt/`)
  - [x] Whisper local (faster-whisper)
  - [x] OpenAI Whisper API
- [x] TTS providers (`providers/tts/`)
  - [x] Edge TTS (Microsoft, free, Vietnamese voice)
- [-] TTS — Piper local (Vietnamese voice) — deferred
- [x] LLM providers — functional chat + tool calling
  - [x] OpenAI: chat() + chat_with_tools()
  - [x] Groq: chat() + chat_with_tools()
  - [x] Ollama: chat() + chat_with_tools()
  - [x] Anthropic: chat() + chat_with_tools()

### 1.3 Skills — First 3 (`agent/skills/`)

- [x] `base.py` — BaseSkill, SkillResult, SkillContext
- [x] `media_control.py` — play, pause, skip, volume
- [x] `app_launcher.py` — open/close application
- [x] `system_control.py` — shutdown, restart, sleep, lock

### 1.4 Platform Abstraction (`agent/system/`)

- [x] `base.py` — SystemAutomation interface
- [x] `windows.py` — Windows implementation
- [x] `factory.py` — Platform factory

### 1.5 Config System

- [x] `config.py` — YAML config loader + 4 built-in profiles
- [x] Setup wizard: `voxagent setup`

### 1.6 System Tray

- [x] `tray.py` — pystray system tray app

### 1.7 CI/CD

- [x] GitHub Actions workflow (`.github/workflows/ci.yml`)
- [x] LICENSE file (Apache 2.0)
- [x] README placeholder URLs fixed

### 1.8 Tests

- [x] 226 tests passing, 81%+ coverage (threshold: 80%)
- [x] All test files: test_hands, test_brain, test_mouth, test_memory, test_config, test_providers, test_skills, test_api, test_audio, test_ears, test_eyes, test_autopilot, test_system, test_llm_providers, test_phase2_5, test_new_skills, test_coverage_boost, test_final_coverage, test_push_80

### 1.D Dashboard (`dashboard/`)

- [x] Full React dashboard with providers, routing, skills, settings screens
- [x] Dashboard builds cleanly (`pnpm build`)

---

## Phase 2 — Smart Brain [COMPLETE]

- [x] LLM providers: DeepSeek (`providers/deepseek_provider.py`)
- [x] LLM providers: Mistral (`providers/mistral_provider.py`)
- [x] LLM providers: OpenRouter (`providers/openrouter_provider.py`)
- [x] Provider registry updated (api/state/store.py, keyring_manager.py)
- [x] Provider registration in app.py and api/server.py
- [x] Skills: `terminal.py` — execute shell commands, blocked pattern detection
- [x] Skills: `file_manager.py` — list, search, move, copy, delete files
- [x] Skills: `browser_control.py` — open URLs, web search
- [x] DANGEROUS_ACTIONS updated: run_command, delete_file
- [x] Skill permission system (`skills/permissions.py`)
  - [x] PermissionLevel enum (SAFE, ELEVATED, DANGEROUS)
  - [x] PermissionManager: check, get_required, is_dangerous
- [-] Memory encryption (SQLCipher) — deferred (optional dependency)
- [-] Multi-step action planning — deferred (requires LLM integration testing)

---

## Phase 3 — Eyes & Autopilot [COMPLETE]

- [x] `eyes.py` — Layered screen understanding (UI tree -> OCR -> Vision LLM)
  - [x] capture_screen() via Pillow
  - [x] analyze_screen() via Vision providers
  - [x] 5-second OCR cache
- [x] `ocr.py` — OCR engine (PaddleOCR/Tesseract fallback)
- [x] Vision providers (`providers/vision/`)
  - [x] OpenAI Vision (GPT-4o)
  - [x] Anthropic Vision (Claude)
  - [x] Gemini Vision
- [x] Skills: `screen_reader.py` — read_text, describe_screen
- [x] Skills: `code_reviewer.py` — review_visible
- [x] `autopilot.py` — Background task engine with trigger loop
  - [x] register_task, cancel_task, list_tasks, stop
  - [x] Time/event/condition/idle triggers
  - [x] Retry logic with max_retries
- [x] `safety.py` — Prompt injection protection
  - [x] 15 injection pattern regex rules
  - [x] sanitize() strips template injection
- [x] macOS platform (`system/macos.py`) — osascript + psutil
- [x] Linux platform (`system/linux.py`) — xdotool + psutil
- [x] Factory updated to wire all 3 platforms

---

## Phase 4 — Polish & Community [COMPLETE]

- [x] Windows installer script (`scripts/build_installer.py`) — PyInstaller
- [x] Documentation site (`docs/`)
  - [x] MkDocs config (`docs/mkdocs.yml`)
  - [x] index.md, getting-started.md, configuration.md, skills.md, api.md
- [x] i18n system (`core/i18n.py`) — vi + en translations
- [x] Skill marketplace (`skills/marketplace.py`) — search, install, publish skeleton
- [x] Opt-in telemetry (`core/telemetry.py`) — anonymous, disabled by default

---

## Phase 5 — Scale [COMPLETE]

- [x] API server mode (`api/server_mode.py`) — /api/command endpoint
- [x] Multi-device sync (`core/sync.py`) — DeviceInfo, SyncManager
- [x] Voice cloning interface (`providers/tts/voice_cloning.py`) — abstract VoiceCloneProvider
- [x] Multi-language conversation (`core/language.py`)
  - [x] 5 languages: vi, en, ja, ko, zh
  - [x] Language detection (heuristic)
  - [x] Language-specific TTS voice mapping
- [-] Mobile companion app — deferred (separate project)
- [-] LLM fine-tuning on user commands — deferred (research phase)

---

## Verification Summary

| Check | Status |
|-------|--------|
| All 226 tests pass | OK |
| Lint (ruff check) | OK |
| Coverage >= 80% | 81.10% |
| Dashboard builds | OK |
| LICENSE exists | OK |
| README URLs valid | OK |
| CI workflow correct | OK |
