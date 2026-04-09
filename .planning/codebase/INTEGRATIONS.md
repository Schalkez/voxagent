# External Integrations

## LLM Provider APIs

### OpenAI
- **Endpoint**: `https://api.openai.com/v1/chat/completions`
- **Default model**: `gpt-4o-mini`
- **Auth**: Bearer token via `Authorization` header
- **Key storage**: OS keyring (`voxagent` / `openai`)
- **HTTP client**: `httpx.AsyncClient` (timeout: 30s)
- **Features used**: Chat Completions, Function Calling / Tools
- **File**: `agent/providers/openai_provider.py`

### Anthropic
- **Endpoint**: `https://api.anthropic.com/v1/messages`
- **Default model**: `claude-sonnet-4-20250514`
- **Auth**: `x-api-key` header + `anthropic-version: 2023-06-01`
- **Key storage**: OS keyring (`voxagent` / `anthropic`)
- **HTTP client**: `httpx.AsyncClient` (timeout: 60s)
- **Features used**: Messages API, Tool Use
- **Message format**: Separate system prompt from messages (Anthropic-specific conversion)
- **File**: `agent/providers/anthropic_provider.py`

### Groq
- **Endpoint**: `https://api.groq.com/openai/v1/chat/completions`
- **Default model**: `llama-3.1-8b-instant`
- **Auth**: Bearer token via `Authorization` header
- **Key storage**: OS keyring (`voxagent` / `groq`)
- **HTTP client**: `httpx.AsyncClient` (timeout: 30s)
- **Features used**: OpenAI-compatible Chat Completions, Function Calling
- **File**: `agent/providers/groq_provider.py`

### DeepSeek
- **Endpoint**: `https://api.deepseek.com/v1/chat/completions`
- **Default model**: `deepseek-chat`
- **Auth**: Bearer token via `Authorization` header
- **Key storage**: OS keyring (`voxagent` / `deepseek`)
- **HTTP client**: `httpx.AsyncClient` (timeout: 30s)
- **Features used**: OpenAI-compatible Chat Completions, Function Calling
- **File**: `agent/providers/deepseek_provider.py`

### Mistral
- **Endpoint**: `https://api.mistral.ai/v1/chat/completions`
- **Default model**: `mistral-small-latest`
- **Auth**: Bearer token via `Authorization` header
- **Key storage**: OS keyring (`voxagent` / `mistral`)
- **HTTP client**: `httpx.AsyncClient` (timeout: 30s)
- **Features used**: OpenAI-compatible Chat Completions, Function Calling
- **File**: `agent/providers/mistral_provider.py`

### OpenRouter
- **Endpoint**: `https://openrouter.ai/api/v1/chat/completions`
- **Default model**: `meta-llama/llama-3.1-8b-instruct:free`
- **Auth**: Bearer token via `Authorization` header + `HTTP-Referer: https://voxagent.dev`
- **Key storage**: OS keyring (`voxagent` / `openrouter`)
- **HTTP client**: `httpx.AsyncClient` (timeout: 30s)
- **Features used**: OpenAI-compatible Chat Completions, Function Calling
- **File**: `agent/providers/openrouter_provider.py`

### Ollama (Local)
- **Endpoint**: `http://localhost:11434/api/chat` (configurable base URL)
- **Default model**: `llama3.1:8b`
- **Auth**: None required (local service)
- **HTTP client**: `httpx.AsyncClient` (timeout: 120s)
- **Features used**: Chat API, Tool Calling, Model listing (`/api/tags`)
- **Health check**: Lists available models via `/api/tags`
- **File**: `agent/providers/ollama_provider.py`

## Speech-to-Text (STT) APIs

### OpenAI Whisper API (Cloud)
- **Endpoint**: `https://api.openai.com/v1/audio/transcriptions`
- **Default model**: `whisper-1`
- **Auth**: Bearer token via `Authorization` header (reuses OpenAI key)
- **Key storage**: OS keyring (`voxagent` / `openai`)
- **HTTP client**: `httpx.AsyncClient` (timeout: 30s)
- **Upload**: Multipart form with WAV file + `response_format: verbose_json`
- **Health check**: Validates key via `GET /v1/models`
- **File**: `agent/providers/stt/openai_whisper.py`

### Whisper Local (On-Device)
- **Engine**: `faster-whisper` (CTranslate2 backend)
- **Model sizes**: `tiny`, `base`, `small`, `medium`, `large-v3`
- **Default**: `base`
- **Device support**: CPU, CUDA, auto-detect
- **Compute types**: `default`, `int8`, `float16`
- **Network**: None (fully offline)
- **Features**: VAD filtering, beam search, 90+ language support
- **File**: `agent/providers/stt/whisper_local.py`

## Text-to-Speech (TTS) Services

### Microsoft Edge TTS (Free Cloud)
- **Service**: Microsoft Edge's free TTS via `edge-tts` Python library
- **Auth**: None required (free service)
- **Network**: Requires internet (streaming synthesis)
- **Voice map**:
  - `vi-female` -> `vi-VN-HoaiMyNeural`
  - `vi-male` -> `vi-VN-NamMinhNeural`
  - `en-female` -> `en-US-JennyNeural`
  - `en-male` -> `en-US-GuyNeural`
- **Output**: MP3 stream, converted to WAV via `pydub`
- **File**: `agent/providers/tts/edge_tts_provider.py`

### ElevenLabs (Paid Cloud + Voice Cloning)
- **Endpoint**: `https://api.elevenlabs.io/v1`
- **Default model**: `eleven_multilingual_v2`
- **Auth**: `xi-api-key` header
- **Key storage**: `ELEVENLABS_API_KEY` env var OR OS keyring (`voxagent` / `elevenlabs_api_key`)
- **HTTP client**: `httpx.AsyncClient` (timeout: 30s synthesis, 120s cloning)
- **Features**:
  - Text-to-speech synthesis (`POST /text-to-speech/{voice_id}`)
  - Voice cloning (`POST /voices/add` with multipart WAV samples)
  - List cloned voices (`GET /voices`)
  - Delete cloned voice (`DELETE /voices/{voice_id}`)
- **Voice settings**: stability, similarity_boost, speed
- **File**: `agent/providers/tts/elevenlabs_clone.py`

### Piper TTS (Local)
- **Engine**: Piper neural TTS via CLI subprocess
- **Auth**: None (fully offline)
- **Binary**: Auto-detected from PATH or configurable path
- **Models dir**: `~/.local/share/piper/models` (ONNX format)
- **Voice models**:
  - `vi-female` / `vi-male` -> `vi_VN-vais1000-medium`
  - `en-female` -> `en_US-amy-medium`
  - `en-male` -> `en_US-ryan-medium`
  - `ja-female` -> `ja_JP-tsukuyomi-medium`
- **Output**: Raw PCM (22050Hz, 16-bit, mono) wrapped in WAV header
- **File**: `agent/providers/tts/piper_provider.py`

## Databases

### SQLite (via aiosqlite)
- **Location**: `~/.voxagent/memory.db`
- **Access pattern**: Async via `aiosqlite.connect()`
- **Schema version**: 1 (tracked in `schema_version` table)
- **Tables**:
  - `conversations` (id, role, content, timestamp, session_id)
  - `preferences` (key, value)
  - `skill_state` (skill_name, key, value)
  - `schema_version` (version)
- **Usage**: Conversation history, user preferences, per-skill persistent state
- **File**: `agent/core/memory.py`

## OS Credential Store (Keyring)

- **Library**: `keyring` (Python)
- **Service name**: `voxagent`
- **Backends**:
  - Windows: Windows Credential Locker
  - macOS: Keychain
  - Linux: SecretService (GNOME Keyring / KDE Wallet)
- **Managed keys** (provider identifiers):
  - `openai`
  - `groq`
  - `anthropic`
  - `gemini`
  - `deepseek`
  - `mistral`
  - `openrouter`
  - `elevenlabs_api_key`
- **Operations**: `save_key()`, `get_key()`, `delete_key()`, `list_provider_keys()`
- **File**: `agent/core/keyring_manager.py`

## OS-Level System Integrations

### Windows
- **Win32 API** (via `ctypes.windll.user32`):
  - `GetForegroundWindow()` - Active window detection
  - `GetWindowTextW()` - Window title extraction
  - `GetWindowThreadProcessId()` - PID resolution
  - `GetWindowRect()` - Window bounds
  - `keybd_event()` - Volume control key simulation (VK_VOLUME_UP/DOWN)
- **Process info**: `psutil.process_iter()` for process listing and memory usage
- **File**: `agent/system/windows.py`

### macOS
- **Intended**: `pyobjc` + Accessibility API
- **File**: `agent/system/macos.py`

### Linux
- **Intended**: AT-SPI (atspi2) accessibility framework
- **File**: `agent/system/linux.py`

### Cross-Platform
- **Screen capture**: `PIL.ImageGrab.grab()` (Pillow)
- **Browser launch**: `webbrowser.open()` (stdlib)
- **System tray**: `pystray.Icon` with dynamic menu

## Internal REST API (Dashboard <-> Agent)

### Server
- **Framework**: FastAPI
- **Host**: `127.0.0.1:8642`
- **Docs**: `/api/docs` (Swagger UI)
- **CORS origins**: `CORS_ORIGINS` env var (default: `http://localhost:5173,http://localhost:3000`)

### Endpoints
- `GET /api/status` - System status for dashboard home
- Router: `/api/providers/*` - Provider management (list, health check, API key management)
- Router: `/api/routing/*` - Tier routing configuration
- Router: `/api/skills/*` - Skill listing and management
- Router: `/api/settings/*` - System settings CRUD

### Communication Pattern
- Dashboard (Vite dev server `:5173`) -> FastAPI backend (`:8642`)
- JSON request/response
- CORS middleware with configurable origins

## Telemetry (Opt-in)

- **Endpoint**: `https://telemetry.voxagent.dev/v1/events`
- **Method**: `POST`
- **Auth**: None
- **Default state**: Disabled (opt-in only)
- **Payload**: `{ event_type, timestamp, metadata }`
- **HTTP client**: `httpx.AsyncClient` (timeout: 5s)
- **Failure handling**: Silent (non-critical, debug log only)
- **File**: `agent/core/telemetry.py`

## Skill Marketplace

- **Registry endpoint**: `https://registry.voxagent.dev/api/skills`
- **Operations**:
  - `GET /search?q=` - Search for skills
  - `GET /{skill_name}/download` - Download skill source code
  - `POST /publish` - Publish a skill (code + manifest JSON)
- **HTTP client**: `httpx.AsyncClient` (timeout: 10s search, 30s install/publish)
- **Local fallback**: File-based install (copy `.py` into `skills/` directory)
- **Manifest storage**: `skills/.installed.json`
- **File**: `agent/skills/marketplace.py`

## OCR Engines

### PaddleOCR (Primary)
- **Library**: `paddleocr` (optional dependency)
- **Config**: `use_angle_cls=True`, `lang="vi"`, `show_log=False`
- **Input**: numpy array from PIL Image
- **Output**: Line-by-line extracted text

### Tesseract (Fallback)
- **Library**: `pytesseract` (optional dependency)
- **Language mapping**: `vi->vie`, `en->eng`, `ja->jpn`, `ko->kor`, `zh->chi_sim`
- **Input**: PIL Image from bytes

### Selection Logic
- Try PaddleOCR first (best Vietnamese support)
- Fall back to Tesseract if PaddleOCR unavailable
- Return empty string if neither available
- **File**: `agent/core/ocr.py`

## Wake Word Detection

- **Engine**: OpenWakeWord (`openwakeword.model.Model`)
- **Backend**: ONNX Runtime
- **Default phrase**: "hey vox"
- **Sensitivity**: 0.7 (configurable)
- **File**: `agent/core/audio/wake_word.py`

## Voice Activity Detection (VAD)

- **Primary**: Silero VAD (`silero_vad.load_silero_vad`, ONNX mode)
- **Fallback**: Energy-based RMS threshold detection (500.0 threshold)
- **Speech threshold**: 0.5 confidence
- **File**: `agent/core/audio/vad.py`

## External Service URLs Summary

| Service | URL | Auth Type |
|---------|-----|-----------|
| OpenAI Chat | `https://api.openai.com/v1/chat/completions` | Bearer token |
| OpenAI Whisper | `https://api.openai.com/v1/audio/transcriptions` | Bearer token |
| Anthropic Messages | `https://api.anthropic.com/v1/messages` | x-api-key header |
| Groq | `https://api.groq.com/openai/v1/chat/completions` | Bearer token |
| DeepSeek | `https://api.deepseek.com/v1/chat/completions` | Bearer token |
| Mistral | `https://api.mistral.ai/v1/chat/completions` | Bearer token |
| OpenRouter | `https://openrouter.ai/api/v1/chat/completions` | Bearer token + Referer |
| ElevenLabs | `https://api.elevenlabs.io/v1` | xi-api-key header |
| Ollama | `http://localhost:11434` | None (local) |
| Edge TTS | Microsoft Edge service (via `edge-tts` lib) | None (free) |
| Telemetry | `https://telemetry.voxagent.dev/v1/events` | None |
| Skill Registry | `https://registry.voxagent.dev/api/skills` | None |
| Google Search | `https://www.google.com/search` | None (browser redirect) |

## Tiered Routing Architecture

```
Voice Command
    |
    v
Tier 0: Keyword Match (no LLM, <50ms)
    |  fail
    v
Tier 1: Small LLM (1-3B, e.g., Groq llama-3.1-8b-instant)
    |  fail/escalate
    v
Tier 2: Medium LLM (7-8B, e.g., Ollama llama3.1:8b)
    |  fail/escalate
    v
Tier 3: Large LLM (32B+/cloud, e.g., Anthropic Claude Sonnet)
```

Fallback chain is configurable (e.g., `["ollama", "groq", "openai"]`).

## Execution Tier Architecture

```
Skill Intent
    |
    v
Tier A: Native API / Shell (subprocess, ctypes, win32api)
    |  fail
    v
Tier B: App / Service API (Playwright, Gmail API, Spotify API)
    |  fail
    v
Tier C: UI Automation (pywinauto, pyobjc, AT-SPI)
    |  fail
    v
Tier D: Mouse / Keyboard (PyAutoGUI -- last resort)
```

## GitHub Integration

### Dependabot
- **Python (pip)**: Weekly updates on Monday, max 5 open PRs
- **npm (dashboard)**: Weekly updates on Monday, max 5 open PRs
- **GitHub Actions**: Weekly version updates
- Labels: `dependencies`, `python`, `dashboard`, `ci`

### CI Workflow
- **Triggers**: Push/PR to `main`/`master`, manual dispatch
- **Runner**: `ubuntu-latest`
- **Python**: 3.12 with pip cache
- **Steps**: Ruff lint -> Bandit security -> Vulture dead code -> Interrogate docstrings -> Pytest with coverage
