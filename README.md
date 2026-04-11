# VoxAgent -- Voice-Controlled Desktop AI Agent

![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
[![CI](https://img.shields.io/github/actions/workflow/status/voxagent/voxagent/ci.yml?label=CI)](https://github.com/voxagent/voxagent/actions)

A voice-first desktop automation agent. Say "Hey Vox" to control your computer.

VoxAgent listens for a wake word, transcribes speech, routes intents through a
tiered model system, executes actions via a skill plugin system, and responds
via text-to-speech. It runs locally on Windows, macOS, and Linux with a Python
backend and a React dashboard for configuration and monitoring.

---

## Key Features

- **Wake word detection** ("Hey Vox") via openwakeword with ONNX runtime
- **Tiered LLM routing** (keyword matching -> small LLM -> large LLM) for cost efficiency -- cheapest tier first, escalate only on failure
- **10+ built-in skills**: app launch, media control, file management, terminal, browser automation, screen reading, code review, system control, and more
- **Streaming TTS** with sentence-level chunking and gapless playback
- **Barge-in support** -- interrupt VoxAgent mid-speech with "Hey Vox"
- **Provider fallback chains** with circuit breakers and health caching
- **Adaptive Voice Activity Detection** with ambient noise estimation via Silero VAD
- **Safety hardening**: AST command validation, prompt injection detection, path sandboxing, shell allowlists, and dangerous-action voice confirmation
- **Multi-language support**: Vietnamese, English, Japanese, Korean, Chinese
- **React dashboard** for real-time configuration and monitoring at `http://localhost:8642`
- **Provider-agnostic**: swap LLM, STT, TTS, and Vision providers without code changes
- **Local-first**: core functionality works offline with Ollama + Piper + faster-whisper

---

## Architecture

```
Mic --> [Ears] --> [Brain] --> [Hands] --> [Mouth] --> Speaker
             |          |          |
         [Memory]    [Eyes]   [Autopilot]
```

| Module    | Role                                                        |
|-----------|-------------------------------------------------------------|
| Ears      | Microphone capture, wake word detection, VAD, STT           |
| Brain     | Tiered intent routing (Tier 0-3), function calling          |
| Hands     | Skill resolution, permission enforcement, tiered execution  |
| Mouth     | TTS synthesis and audio playback                            |
| Eyes      | Screen understanding: UI tree, OCR, Vision LLM              |
| Memory    | SQLite persistence for conversations, preferences, state    |
| Autopilot | Background task scheduler (time, event, condition triggers) |

For the full architecture reference, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Quick Start

### Prerequisites

- Python 3.12 or later
- A microphone and speakers
- (Optional) Ollama for local LLM inference
- (Optional) GPU with 8 GB+ VRAM for full local mode

### Install

```bash
git clone https://github.com/voxagent/voxagent
cd voxagent/agent
pip install -e ".[dev,audio,stt]"
```

### Run

```bash
voxagent setup          # Interactive wizard -- choose providers and profile
voxagent start          # Start listening -- say "Hey Vox" to activate
```

### Start the Dashboard

```bash
voxagent-api            # API server on http://localhost:8642
cd ../dashboard
pnpm install && pnpm dev   # Dashboard on http://localhost:5173
```

---

## Built-in Profiles

VoxAgent ships with four configuration profiles that pre-select providers for
common hardware setups:

| Profile        | Best For       | GPU Required         | Internet Required |
|----------------|----------------|----------------------|-------------------|
| `full_local`   | Privacy, offline use | Yes (8 GB+ VRAM) | No                |
| `cloud_free`   | Quick start    | No                   | Yes               |
| `hybrid`       | Best quality   | Optional             | Yes               |
| `budget_cloud` | Low cost       | No                   | Yes               |

```bash
voxagent start --profile cloud_free
```

---

## Skills

| Skill            | Execution Tiers      | Description                              |
|------------------|----------------------|------------------------------------------|
| App Launcher     | NATIVE_API, SHELL    | Open and close desktop applications      |
| Media Control    | NATIVE_API, KEYBOARD | Play, pause, skip, volume via media keys |
| System Control   | NATIVE_API, SHELL    | Shutdown, restart, lock, sleep           |
| File Manager     | NATIVE_API, SHELL    | Create, move, copy, delete files         |
| Browser Control  | APP_API              | Browser automation via Playwright CDP    |
| Terminal         | SHELL                | Execute terminal commands (allowlisted)  |
| Screen Reader    | NATIVE_API, UI       | Read screen content via Eyes module      |
| Code Reviewer    | APP_API              | Code review powered by LLM              |
| Marketplace      | APP_API              | Browse and install community skills      |
| System Info      | NATIVE_API           | Query system information and processes   |

Skills declare their supported execution tiers. The Hands module tries the
cheapest tier first (A: Native API) and falls back through B (App API),
C (UI Automation), and D (Keyboard) as needed.

---

## Provider Support

VoxAgent is provider-agnostic. Swap any provider at runtime via configuration:

| Type   | Supported Providers                                                          |
|--------|------------------------------------------------------------------------------|
| LLM    | Ollama, OpenAI, Anthropic, Groq, DeepSeek, Mistral, OpenRouter              |
| STT    | faster-whisper (local), OpenAI Whisper API                                   |
| TTS    | Edge TTS, Piper (local), ElevenLabs                                          |
| Vision | OpenAI Vision, Anthropic Vision, Gemini Vision                               |

---

## LLM Tier Routing

| Tier | Model Size  | Use Case                     | Latency Target |
|------|-------------|------------------------------|----------------|
| 0    | None        | Keyword pattern matching     | < 50 ms        |
| 1    | 1-3B        | Simple intent classification | < 200 ms       |
| 2    | 7-8B        | Reasoning, multi-step plans  | < 1 s          |
| 3    | 32B+ / Cloud| Complex tasks, code review   | < 5 s          |

---

## Tech Stack

| Layer     | Technology                                    |
|-----------|-----------------------------------------------|
| Backend   | Python 3.12+, FastAPI, uvicorn, asyncio       |
| Frontend  | React 19, TypeScript 5.9, Tailwind CSS, Vite  |
| Database  | SQLite via aiosqlite                           |
| Audio     | sounddevice, openwakeword, Silero VAD, pydub   |
| HTTP      | httpx (async)                                  |
| Security  | OS keyring, bandit, prompt injection detection |
| CI        | GitHub Actions, ruff, mypy, pytest, interrogate|

---

## Development

### Clone and Install

```bash
git clone https://github.com/voxagent/voxagent
cd voxagent/agent
pip install -e ".[dev,audio,stt]"
```

### Run Tests

```bash
cd agent
pytest tests/ --cov
```

### Lint and Format

```bash
ruff check .                # Lint
ruff format .               # Format
mypy core/ providers/       # Type check
bandit -c pyproject.toml -r core/   # Security scan
interrogate -c pyproject.toml       # Docstring coverage
```

### Dashboard Development

```bash
cd dashboard
pnpm install
pnpm dev         # Vite dev server on http://localhost:5173
pnpm build       # Production build
```

### Pre-commit Hooks

```bash
pre-commit install
pre-commit run --all-files
```

---

## Configuration

Runtime configuration lives at `~/.voxagent/config.yaml`. API keys are stored
in the OS keyring (Windows Credential Locker, macOS Keychain, or Linux
SecretService) and are never written to config files.

See [docs/configuration.md](docs/configuration.md) for the full reference.

---

## Server Mode

VoxAgent includes a headless API server for programmatic integration with
external platforms such as Home Assistant, n8n, or Zapier:

```bash
voxagent-api    # Starts on http://127.0.0.1:8642
```

```bash
curl -X POST http://127.0.0.1:8642/api/command \
     -H "Content-Type: application/json" \
     -H "X-VoxAgent-Key: <your_secret_key>" \
     -d '{"text": "shut down the computer in one hour"}'
```

---

## Documentation

- [Getting Started](docs/getting-started.md)
- [Architecture](ARCHITECTURE.md)
- [Configuration](docs/configuration.md)
- [Skill Development Guide](docs/SKILL_DEVELOPMENT_GUIDE.md)
- [API Reference](docs/api.md)
- [Security Policy](docs/SECURITY.md)
- [Roadmap](docs/ROADMAP.md)

---

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for
development setup, code quality standards, and the pull request process.

---

## License

Apache 2.0 -- see [LICENSE](LICENSE) for the full text.
