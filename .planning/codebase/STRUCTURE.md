# VoxAgent Directory Structure

## Root Layout

```
voxagent/
|-- agent/                    # Python backend (voice agent + API server)
|-- dashboard/                # React/TypeScript frontend (management SPA)
|-- docs/                     # Documentation (MkDocs)
|-- scripts/                  # Build and deployment scripts
|-- tests/                    # Root-level integration tests
|-- .github/                  # CI/CD workflows and config
|-- ARCHITECTURE.md           # High-level architecture overview
|-- CONTRIBUTING.md           # Contribution guidelines
|-- FUTURE.md                 # Roadmap and future plans
|-- REVIEW.md                 # Code review notes
|-- LICENSE                   # Apache-2.0
```

---

## Agent (Python Backend)

```
agent/
|-- core/                     # Domain logic (provider-agnostic)
|   |-- __init__.py
|   |-- app.py                # Main orchestrator, CLI entry point
|   |-- brain.py              # Tiered LLM routing, intent extraction
|   |-- ears.py               # Voice input pipeline orchestrator
|   |-- mouth.py              # TTS output with Vietnamese templates
|   |-- hands.py              # Tiered action execution
|   |-- eyes.py               # Layered screen understanding
|   |-- memory.py             # SQLite storage (aiosqlite)
|   |-- autopilot.py          # Background task scheduler
|   |-- planner.py            # Multi-step command decomposition
|   |-- config.py             # YAML config loader + built-in profiles
|   |-- safety.py             # Prompt injection detection
|   |-- keyring_manager.py    # OS keyring API key storage
|   |-- i18n.py               # vi/en translations
|   |-- language.py           # Multi-language detection + manager
|   |-- ocr.py                # PaddleOCR + Tesseract engine
|   |-- sync.py               # Multi-device config sync
|   |-- telemetry.py          # Opt-in anonymous telemetry
|   |-- audio/                # Audio sub-components (SRP)
|       |-- __init__.py
|       |-- recorder.py       # Microphone capture (sounddevice)
|       |-- wake_word.py      # Wake word detection (openwakeword)
|       |-- vad.py            # Voice activity detection (Silero)
|       |-- converter.py      # Numpy frames -> WAV bytes
|
|-- providers/                # External service integrations
|   |-- __init__.py
|   |-- base.py               # ABCs: LLMProvider, STTProvider, TTSProvider, VisionProvider
|   |-- registry.py           # ProviderRegistry (factory + cache + fallback)
|   |-- openai_provider.py    # OpenAI LLM implementation
|   |-- groq_provider.py      # Groq LLM implementation
|   |-- anthropic_provider.py # Anthropic LLM implementation
|   |-- ollama_provider.py    # Ollama (local) LLM implementation
|   |-- deepseek_provider.py  # DeepSeek LLM implementation
|   |-- mistral_provider.py   # Mistral LLM implementation
|   |-- openrouter_provider.py# OpenRouter LLM implementation
|   |-- stt/                  # Speech-to-Text providers
|   |   |-- __init__.py
|   |   |-- whisper_local.py  # Local Whisper (faster-whisper)
|   |   |-- openai_whisper.py # OpenAI Whisper API
|   |-- tts/                  # Text-to-Speech providers
|   |   |-- __init__.py
|   |   |-- edge_tts_provider.py  # Microsoft Edge TTS (free)
|   |   |-- piper_provider.py     # Piper TTS (local)
|   |   |-- elevenlabs_clone.py   # ElevenLabs voice cloning
|   |   |-- voice_cloning.py      # Voice cloning utilities
|   |-- vision/               # Vision/Image providers
|       |-- __init__.py
|       |-- openai_vision.py     # GPT-4o vision
|       |-- anthropic_vision.py  # Claude vision
|       |-- gemini_vision.py     # Gemini vision
|
|-- skills/                   # Pluggable action handlers
|   |-- __init__.py
|   |-- base.py               # BaseSkill ABC, ExecutionTier, SkillIntent, SkillResult
|   |-- registry.py           # SkillRegistry singleton + @register_skill decorator
|   |-- permissions.py        # PermissionLevel, PermissionManager
|   |-- app_launcher.py       # Open/close applications
|   |-- media_control.py      # Play/pause/skip/volume
|   |-- system_control.py     # Shutdown, restart, lock, sleep
|   |-- file_manager.py       # File operations
|   |-- browser_control.py    # Browser automation (Playwright)
|   |-- terminal.py           # Terminal command execution
|   |-- screen_reader.py      # Screen content reading via Eyes
|   |-- code_reviewer.py      # LLM-powered code review
|   |-- marketplace.py        # Skill marketplace (install/browse)
|   |-- system_skill.py       # System info queries
|   |-- dependency_resolver.py# Skill dependency management
|
|-- system/                   # OS-specific automation
|   |-- __init__.py
|   |-- base.py               # SystemAutomation ABC
|   |-- factory.py            # Platform detection factory
|   |-- windows.py            # Windows: pywinauto + win32gui
|   |-- macos.py              # macOS: pyobjc + Accessibility
|   |-- linux.py              # Linux: AT-SPI + xdotool
|
|-- api/                      # FastAPI REST server (for dashboard)
|   |-- __init__.py
|   |-- server.py             # App creation, lifespan, CORS, router mount
|   |-- server_mode.py        # Headless server mode + /api/command endpoint
|   |-- deps.py               # FastAPI dependency injection helpers
|   |-- exceptions.py         # Domain exception hierarchy
|   |-- routers/              # HTTP route handlers
|   |   |-- __init__.py       # Re-exports only (barrel)
|   |   |-- providers.py      # /api/providers/* endpoints
|   |   |-- routing.py        # /api/routing/* endpoints
|   |   |-- skills.py         # /api/skills/* endpoints
|   |   |-- settings.py       # /api/settings/* endpoints
|   |-- services/             # Business logic for routers
|   |   |-- __init__.py
|   |   |-- providers.py
|   |   |-- routing.py
|   |   |-- skills.py
|   |   |-- settings.py
|   |-- schemas/              # Pydantic request/response models
|   |   |-- __init__.py
|   |   |-- providers.py
|   |   |-- routing.py
|   |   |-- skills.py
|   |   |-- settings.py
|   |-- state/                # Persistent YAML-backed state
|       |-- __init__.py
|       |-- store.py          # routing_config_state, skills_state
|
|-- benchmarks/               # Performance benchmarks
|   |-- __init__.py
|   |-- bench_stt.py          # STT latency benchmarks
|   |-- bench_tiers.py        # Tier routing latency benchmarks
|
|-- tests/                    # Agent-level unit tests
|   |-- conftest.py           # Shared fixtures (mock providers, skills)
|   |-- test_api.py           # API endpoint tests
|   |-- test_app_compliance.py# Architecture compliance tests
|   |-- test_audio.py         # Audio module tests
|   |-- test_autopilot.py     # Autopilot tests
|   |-- test_brain.py         # Brain routing tests
|   |-- test_config.py        # Config loading tests
|   |-- test_ears.py          # Ears pipeline tests
|   |-- test_eyes.py          # Eyes module tests
|   |-- test_hands.py         # Hands execution tests
|   |-- test_llm_providers.py # LLM provider tests
|   |-- test_memory.py        # Memory/SQLite tests
|   |-- test_mouth.py         # Mouth/TTS tests
|   |-- test_new_skills.py    # Skill tests
|   |-- test_providers.py     # Provider registry tests
|   |-- test_skills.py        # Skill execution tests
|   |-- test_system.py        # System automation tests
|   |-- test_security_phase1.py # Security/safety tests
|   |-- test_*.py             # Additional coverage tests
|
|-- scripts/
|   |-- train_wake_word.py    # Custom wake word model training
|
|-- tray.py                   # System tray icon (pystray)
|-- pyproject.toml            # Project metadata, dependencies, tool config
|-- config.example.yaml       # Example configuration file
|-- skill-manifest-schema.json# JSON Schema for skill manifests
```

---

## Dashboard (React Frontend)

```
dashboard/
|-- src/
|   |-- main.tsx              # React DOM entry point
|   |-- App.tsx               # Router configuration (react-router-dom v7)
|   |
|   |-- features/             # Feature-sliced modules
|   |   |-- dashboard/        # Home/overview page
|   |   |   |-- containers/DashboardView.tsx
|   |   |   |-- components/organisms/
|   |   |   |   |-- BentoGrid/BentoGrid.tsx
|   |   |   |   |-- HeroCard/HeroCard.tsx
|   |   |   |   |-- TerminalLog/TerminalLog.tsx
|   |   |   |   |-- index.ts
|   |   |   |-- hooks/useDashboardStatus.ts
|   |   |   |-- types/dashboard.types.ts
|   |   |   |-- index.ts
|   |   |
|   |   |-- providers/        # Provider management page
|   |   |   |-- containers/ProvidersView.tsx
|   |   |   |-- components/organisms/
|   |   |   |   |-- ProviderCard/ProviderCard.tsx
|   |   |   |   |-- OllamaCard/OllamaCard.tsx
|   |   |   |   |-- QuotaStats/QuotaStats.tsx
|   |   |   |   |-- index.ts
|   |   |   |-- hooks/useProviders.ts
|   |   |   |-- types/providers.types.ts
|   |   |   |-- constants/mocks.ts
|   |   |
|   |   |-- routing/          # Tier routing configuration page
|   |   |   |-- containers/RoutingView.tsx
|   |   |   |-- components/organisms/
|   |   |   |   |-- TierCard/TierCard.tsx
|   |   |   |   |-- RoutingPresetCard/RoutingPresetCard.tsx
|   |   |   |   |-- RoutingStatusChip/RoutingStatusChip.tsx
|   |   |   |   |-- index.ts
|   |   |   |-- hooks/useRouting.ts
|   |   |   |-- types/routing.types.ts, components.types.ts
|   |   |   |-- constants/mocks.ts, presets.ts
|   |   |
|   |   |-- skills/           # Skills management page
|   |   |   |-- containers/SkillsView.tsx
|   |   |   |-- components/organisms/
|   |   |   |   |-- SkillCard/SkillCard.tsx
|   |   |   |   |-- AddSkillCard/AddSkillCard.tsx
|   |   |   |   |-- SkillsFooter/SkillsFooter.tsx
|   |   |   |   |-- index.ts
|   |   |   |-- hooks/useSkills.ts
|   |   |   |-- types/skills.types.ts, components.types.ts
|   |   |   |-- constants/mocks.ts, ui.ts
|   |   |
|   |   |-- settings/         # Settings page
|   |   |   |-- containers/SettingsView.tsx
|   |   |   |-- components/organisms/
|   |   |   |   |-- AudioSettingsCard/AudioSettingsCard.tsx
|   |   |   |   |-- SecurityCard/SecurityCard.tsx
|   |   |   |-- hooks/useSettings.ts
|   |   |   |-- types/settings.types.ts
|   |   |   |-- constants/ui.ts
|   |   |   |-- index.ts
|   |   |
|   |   |-- autopilot/        # Autopilot page
|   |   |   |-- containers/AutopilotView.tsx
|   |   |
|   |   |-- memory/           # Memory/history page
|   |       |-- containers/MemoryView.tsx
|   |
|   |-- shared/               # Cross-feature shared code
|   |   |-- api/
|   |   |   |-- client.ts     # fetchApi() wrapper (base URL from env)
|   |   |-- components/
|   |   |   |-- atoms/        # Smallest UI primitives
|   |   |   |   |-- Avatar/, Badge/, Dot/, Icon/, Input/
|   |   |   |   |-- ProgressBar/, Slider/, Switch/, Text/
|   |   |   |   |-- index.ts
|   |   |   |-- molecules/    # Composed UI elements
|   |   |   |   |-- Breadcrumb/, Card/, NavItem/, Select/, StatusBadge/
|   |   |   |   |-- index.ts
|   |   |   |-- organisms/    # Complex UI blocks
|   |   |   |   |-- Sidebar/, Topbar/
|   |   |   |   |-- index.ts
|   |   |   |-- templates/    # Page-level layout wrappers
|   |   |   |   |-- MainLayout/MainLayout.tsx
|   |   |   |-- Button/Button.tsx
|   |   |   |-- index.ts
|   |   |-- styles/
|   |   |   |-- global.css    # Tailwind CSS v4 imports + global styles
|   |   |-- index.ts          # Barrel re-export for @shared/*
|   |
|   |-- assets/               # Static assets (images, SVGs)
|       |-- hero.png, react.svg, vite.svg
|
|-- public/
|   |-- favicon.svg
|   |-- icons.svg             # Shared icon sprite
|
|-- mocks/                    # HTML mockups for design reference
|   |-- JARVIS_Dashboard_Overview.html
|   |-- Providers___API_Keys.html
|   |-- Smart_Tier_Routing.html
|   |-- JARVIS_Skills___Plugins.html
|   |-- Memory___History.html
|   |-- Device_Settings.html
|   |-- Autopilot___Tasks.html
|   |-- Initial_Setup_Wizard.html
|
|-- package.json              # pnpm dependencies
|-- pnpm-lock.yaml
|-- vite.config.ts            # Vite + React + Tailwind + path aliases
|-- tsconfig.json             # TypeScript base config
|-- tsconfig.app.json         # App-specific TS config
|-- tsconfig.node.json        # Node-specific TS config (Vite)
|-- eslint.config.js          # ESLint + Prettier config
|-- .prettierrc               # Prettier settings
|-- .prettierignore
|-- index.html                # Vite HTML entry point
```

---

## Key Locations

| What you need                        | Where to find it                              |
|--------------------------------------|-----------------------------------------------|
| Application entry point              | `agent/core/app.py` (`main()` function)       |
| API server entry point               | `agent/api/server.py` (`main()` function)     |
| All provider ABCs                    | `agent/providers/base.py`                     |
| Provider registration                | `agent/providers/registry.py`                 |
| Skill base class                     | `agent/skills/base.py`                        |
| Skill registration                   | `agent/skills/registry.py`                    |
| System automation interface          | `agent/system/base.py`                        |
| Configuration model                  | `agent/core/config.py`                        |
| API key management                   | `agent/core/keyring_manager.py`               |
| Dashboard API client                 | `dashboard/src/shared/api/client.ts`          |
| Dashboard routing                    | `dashboard/src/App.tsx`                        |
| Shared UI components                 | `dashboard/src/shared/components/`            |
| Python dependencies                  | `agent/pyproject.toml`                        |
| Frontend dependencies                | `dashboard/package.json`                      |
| CI pipeline                          | `.github/workflows/ci.yml`                    |
| Test configuration                   | `agent/pyproject.toml` `[tool.pytest]`        |
| Linter configuration                 | `agent/pyproject.toml` `[tool.ruff]`          |
| User configuration (runtime)         | `~/.voxagent/config.yaml`                     |
| User database (runtime)              | `~/.voxagent/memory.db`                       |
| Dashboard state (runtime)            | `~/.voxagent/state.yaml`                      |

---

## Naming Conventions

### Python Backend

| Element                | Convention                          | Example                        |
|------------------------|-------------------------------------|--------------------------------|
| Modules                | `snake_case.py`                     | `openai_provider.py`           |
| Classes                | `PascalCase`                        | `ProviderRegistry`             |
| Functions/methods      | `snake_case`                        | `chat_with_tools()`            |
| Private methods        | `_snake_case`                       | `_try_tier_zero()`             |
| Constants              | `SCREAMING_SNAKE_CASE`              | `MAX_RECORDING_S`              |
| Frozen dataclasses     | `PascalCase`                        | `TranscribeResult`             |
| Type aliases           | `PascalCase`                        | `VoxAgentConfig`               |
| Abstract base classes  | `PascalCase` (suffix: `Provider`)   | `LLMProvider`, `STTProvider`   |
| Concrete providers     | `PascalCase` (suffix: `Provider`)   | `GroqProvider`, `EdgeTTSProvider` |
| Skills                 | `PascalCase` (suffix: `Skill`)      | `AppLauncherSkill`             |
| System implementations | `PascalCase` (suffix: `Automation`) | `WindowsAutomation`            |
| Test files             | `test_*.py`                         | `test_brain.py`                |
| Logger names           | `voxagent.<module>`                 | `voxagent.brain`               |

### TypeScript Frontend

| Element                | Convention                          | Example                        |
|------------------------|-------------------------------------|--------------------------------|
| Components             | `PascalCase.tsx` in `PascalCase/`   | `ProviderCard/ProviderCard.tsx`|
| Hooks                  | `use<Name>.ts`                      | `useProviders.ts`              |
| Types                  | `<domain>.types.ts`                 | `routing.types.ts`             |
| Constants              | `camelCase.ts` or `SCREAMING_SNAKE` | `mocks.ts`, `API_BASE`        |
| Containers             | `<Name>View.tsx`                    | `DashboardView.tsx`            |
| Barrel exports         | `index.ts` (re-exports only)        | Every folder has one           |
| CSS                    | Tailwind utility classes             | No CSS modules                 |
| Path aliases           | `@features/*`, `@shared/*`, `@/*`   | `import { Card } from '@shared/components'` |

### File Organization Rules

| Rule                                 | Applies To             |
|--------------------------------------|------------------------|
| One class per file                   | Providers, Skills, System implementations |
| Barrel `index.ts` = re-exports only  | All dashboard folders  |
| No `../` relative imports            | Dashboard (use `@shared/*`, `@features/*`) |
| `TYPE_CHECKING` guard for type-only imports | All Python modules |
| Feature-sliced structure             | Dashboard (`features/<name>/containers,components,hooks,types,constants`) |
| Atomic Design hierarchy              | Shared components (`atoms` -> `molecules` -> `organisms` -> `templates`) |
