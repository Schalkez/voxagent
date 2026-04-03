# 🏗️ VOXAGENT — Architecture Document

> Chi tiết kỹ thuật đầy đủ về thiết kế hệ thống, quyết định kiến trúc, và implementation guide.

---

## 1. Tổng quan

VoxAgent được thiết kế theo nguyên tắc **modular pipeline**:

```
Voice Input → STT → Intent Router → Skill Execution → TTS Output
                         ↑                  ↑
                    Memory System      Eyes (Vision)
                         ↑                  ↑
                    Autopilot          Screen/OCR
```

Mỗi module được abstract thành interface riêng, có thể swap provider mà không ảnh hưởng đến phần còn lại.

---

## 2. Module Chi Tiết

### 2.1 🎤 EARS — Voice Input Pipeline

```
Mic (luôn bật, ~2% CPU)
    ↓
Wake Word Detector (openWakeWord — Apache 2.0)
    ↓ "Hey Vox" detected
🔔 Beep xác nhận
    ↓
Voice Activity Detection (Silero VAD)
    ↓ user nói xong
STT Transcription (Whisper local / cloud API)
    ↓
Raw text → BRAIN
```

**Wake word options:**

| Option              | License       | Accuracy | CPU usage |
| ------------------- | ------------- | -------- | --------- |
| openWakeWord        | Apache 2.0 ✅ | Good     | < 2%      |
| Whisper streaming   | Apache 2.0 ✅ | Best     | 5–15%     |
| Hotkey push-to-talk | N/A ✅        | Perfect  | 0%        |

> ⚠️ Picovoice Porcupine yêu cầu commercial license cho production. Dùng openWakeWord hoặc hotkey thay thế.

**STT Provider Interface:**

```python
class STTProvider(ABC):
    @abstractmethod
    async def transcribe(
        self,
        audio: bytes,
        language: str = "vi",
        task: Literal["transcribe", "translate"] = "transcribe"
    ) -> TranscribeResult:
        """
        Returns:
            TranscribeResult(text, confidence, language_detected, duration_ms)
        """
```

---

### 2.2 🧠 BRAIN — Intent Router & Orchestrator

#### Smart Tier Routing

```
Text từ EARS
    ↓
┌─────────────────────────────────────────────────────────┐
│  TIER 0: Pattern Matching (< 50ms, NO model)            │
│  Keywords: skip, pause, next, stop, tắt, mở...          │
│  → Gọi thẳng skill                                      │
├─────────────────────────────────────────────────────────┤
│  TIER 1: Small LLM (< 1s, ~1–3B params)                │
│  Model: Qwen2.5-1.5B / Phi-4-mini                      │
│  Dùng khi: intent đơn giản, extract params              │
├─────────────────────────────────────────────────────────┤
│  TIER 2: Medium LLM (2–5s, ~7–8B params)               │
│  Model: Llama 3.1 8B / Mistral 7B                      │
│  Dùng khi: reasoning, multi-step planning               │
├─────────────────────────────────────────────────────────┤
│  TIER 3: Large LLM (5–15s, load on-demand)             │
│  Model: Qwen2.5-32B / Claude / GPT-4o                  │
│  Dùng khi: complex reasoning, vision, code review       │
│  ⚠️ Unload sau khi xong để giải phóng VRAM             │
└─────────────────────────────────────────────────────────┘
```

**Routing Logic:**

```python
def route(text: str) -> Tier:
    # Tier 0: Keyword exact match
    if match_keywords(text, TIER_0_KEYWORDS):
        return Tier.ZERO

    # Tier 1: Simple intent
    intent = small_model.classify(text)
    if intent.confidence > 0.9 and intent.complexity == "simple":
        return Tier.ONE

    # Tier 2: Needs reasoning
    if intent.needs_planning or intent.multi_step:
        return Tier.TWO

    # Tier 3: Vision hoặc complex analysis
    if intent.needs_vision or intent.complexity == "complex":
        return Tier.THREE
```

**Fallback Chain:**

```yaml
fallback_chain:
  - ollama # Local trước (free, private)
  - groq # Cloud nhanh & rẻ
  - openai # Reliable nhất
```

---

### 2.3 Memory System

```
┌──────────────────────────────────────────┐
│             MEMORY LAYERS                │
│                                          │
│  Short-term:  Session context buffer     │
│  Long-term:   SQLite (encrypted)         │
│  Skill state: Per-skill key-value store  │
│  Preferences: User habits & defaults     │
└──────────────────────────────────────────┘
```

**Schema SQLite:**

```sql
-- Conversation history
CREATE TABLE conversations (
    id         INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    role       TEXT NOT NULL,  -- user | assistant
    content    TEXT NOT NULL,
    timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- User preferences (learned)
CREATE TABLE preferences (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Skill state
CREATE TABLE skill_state (
    skill_name TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    PRIMARY KEY (skill_name, key)
);
```

> ⚠️ Database được encrypt bằng SQLCipher. Key được lưu trong OS keyring (Keychain trên macOS, Credential Manager trên Windows, libsecret trên Linux).

---

### 2.4 👁️ EYES — Layered Screen Understanding

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Native UI Automation (FREE, instant)          │
│  Windows: pywinauto + win32gui                          │
│  macOS:   pyobjc + Accessibility API                    │
│  Linux:   AT-SPI (atspi2)                              │
│  → Đọc window title, button labels, text fields        │
├─────────────────────────────────────────────────────────┤
│  Layer 2: OCR (FREE, < 500ms)                           │
│  PaddleOCR (tiếng Việt tốt) / Tesseract                │
│  Targeted crop: chỉ chụp vùng cần thiết                 │
│  Cache kết quả 5s để tránh re-OCR                       │
├─────────────────────────────────────────────────────────┤
│  Layer 3: Vision LLM (complex cases only)               │
│  Crop nhỏ vùng cần thiết, KHÔNG gửi full screen         │
│  Cache aggressive: same region + same hash → reuse      │
│  Providers: GPT-4o / Claude / Gemini / Qwen-VL (local) │
└─────────────────────────────────────────────────────────┘
```

**Platform Abstraction:**

```python
class SystemAutomation(ABC):
    """Interface chung cho mọi OS"""

    @abstractmethod
    def get_active_window(self) -> WindowInfo: ...

    @abstractmethod
    def find_element(self, role: str, name: str) -> Optional[UIElement]: ...

    @abstractmethod
    def get_running_processes(self) -> list[ProcessInfo]: ...

    @abstractmethod
    def read_notifications(self) -> list[Notification]: ...


# Implementations
class WindowsAutomation(SystemAutomation): ...   # pywinauto + win32gui
class MacOSAutomation(SystemAutomation): ...     # pyobjc + Accessibility
class LinuxAutomation(SystemAutomation): ...     # AT-SPI (atspi2)
```

---

### 2.5 🖐️ HANDS — Action Execution

#### Execution Strategy — Nguyên tắc cốt lõi

> **UI automation là last resort, không phải default.**
> Cùng một kết quả, luôn ưu tiên cách rẻ hơn, nhanh hơn, ít phụ thuộc vào layout hơn.

```
Intent
  ↓
┌──────────────────────────────────────────────────────┐
│              Execution Strategy Selector             │
│                                                      │
│  Tier A: Native API / Shell        ← ưu tiên nhất   │
│  │  subprocess, os, ctypes, win32api, AppKit         │
│  │  Nhanh nhất, không tốn token, không vỡ theo UI    │
│  ↓                                                   │
│  Tier B: App / Service API         ← nếu có          │
│  │  Playwright CDP, Gmail API, Spotify API...         │
│  │  Đáng tin, idempotent, có error handling tốt      │
│  ↓                                                   │
│  Tier C: UI Automation             ← khi không có API│
│  │  pywinauto, pyobjc Accessibility, AT-SPI           │
│  │  Đọc widget tree — không cần nhìn màn hình        │
│  ↓                                                   │
│  Tier D: Mouse / Keyboard          ← last resort     │
│     PyAutoGUI click/type                             │
│     Chỉ dùng khi app không có accessibility support  │
└──────────────────────────────────────────────────────┘
```

**Ví dụ cùng một lệnh, khác execution tier:**

| Lệnh               | ❌ Tier D (tránh)        | ✅ Tier tốt hơn                      |
| ------------------ | ------------------------ | ------------------------------------ |
| "commit code"      | Screenshot → OCR → type  | `subprocess git commit` (Tier A)     |
| "tìm file hôm qua" | Simulate Explorer search | `os.scandir` + filter mtime (Tier A) |
| "volume 50%"       | Click thanh volume       | `ctypes` / `osascript` (Tier A)      |
| "gửi email"        | Click Gmail từng bước    | Gmail API (Tier B)                   |
| "mở tab mới"       | PyAutoGUI Ctrl+T         | Playwright `new_page()` (Tier B)     |
| "click nút Submit" | Toạ độ pixel             | `pywinauto find_element` (Tier C)    |

**Mỗi Skill khai báo strategy ưu tiên của mình:**

```python
class GitSkill(BaseSkill):
    execution_tiers = [
        ExecutionTier.SHELL,   # git CLI — luôn có
    ]

class BrowserSkill(BaseSkill):
    execution_tiers = [
        ExecutionTier.APP_API,  # Playwright CDP trước
        ExecutionTier.UI,       # fallback nếu CDP bị block
    ]

class MediaControlSkill(BaseSkill):
    execution_tiers = [
        ExecutionTier.NATIVE_API,  # win32api / osascript
        ExecutionTier.KEYBOARD,    # fallback media keys
    ]
```

**Khi nào được phép dùng Tier D (mouse/keyboard):**

- App không có Accessibility support (game, một số app Electron cũ)
- Không có API, không có CLI, widget tree không readable
- Skill phải ghi rõ lý do trong `skill.json`: `"ui_fallback_reason": "..."`

---

**Safety gates — bắt buộc confirm trước khi thực hiện:**

```python
DANGEROUS_ACTIONS = {
    "shutdown", "restart", "delete_file",
    "format_disk", "run_as_admin", "send_email"
}

async def execute_with_gate(action: Action) -> SkillResult:
    if action.type in DANGEROUS_ACTIONS:
        confirmed = await confirm_voice(
            f"Bạn có chắc muốn {action.description}?"
        )
        if not confirmed:
            return SkillResult(cancelled=True)
    return await action.execute()
```

---

### 2.6 🔊 MOUTH — TTS Output

**TTS Provider Interface:**

```python
class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: str = "vi-female",
        speed: float = 1.0
    ) -> bytes:
        """Returns raw WAV/MP3 audio bytes"""
```

**Response templates:**

```python
TEMPLATES = {
    "success":   "Đã {action} rồi nha",
    "report":    "Hiện tại {state}. {detail}",
    "error":     "Không {action} được vì {reason}",
    "confirm":   "Ý anh là {option_a} hay {option_b}?",
    "thinking":  "Để tôi xem...",   # earcon trong khi xử lý
}
```

---

### 2.7 ⏰ AUTOPILOT — Background Task Engine

```python
@dataclass
class AutopilotTask:
    id:          str
    trigger:     Trigger          # time | event | condition | idle
    condition:   Callable[[], bool]
    actions:     list[Action]
    repeat:      bool = False
    max_retries: int = 3
    timeout_s:   int = 300

class TriggerType(Enum):
    TIME_BASED      = "time"       # "5 phút nữa nhắc tao"
    EVENT_BASED     = "event"      # "khi download xong"
    CONDITION_BASED = "condition"  # "khi CPU < 30%"
    IDLE_BASED      = "idle"       # "khi Cursor idle 30s"
```

---

## 3. Provider System

### Unified Interface

```python
class LLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[Message], **kwargs) -> str: ...

    @abstractmethod
    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[Tool],
        **kwargs
    ) -> ToolCallResult: ...

    @abstractmethod
    def get_model_info(self) -> ModelInfo: ...

    @abstractmethod
    async def health_check(self) -> bool: ...
```

### Provider Registry

```python
# config.yaml → tự động load đúng provider
registry = ProviderRegistry()
registry.register("openai",    OpenAIProvider)
registry.register("anthropic", AnthropicProvider)
registry.register("ollama",    OllamaProvider)
registry.register("groq",      GroqProvider)
# ...

llm = registry.get_llm(tier=2)  # trả về provider cho tier 2
```

---

## 4. Cross-Platform Support

| Component     | Windows           | macOS        | Linux        |
| ------------- | ----------------- | ------------ | ------------ |
| Wake word     | openWakeWord      | openWakeWord | openWakeWord |
| UI Automation | pywinauto + win32 | pyobjc       | AT-SPI       |
| Screenshot    | mss               | mss          | mss          |
| System tray   | pystray           | pystray      | pystray      |
| Hotkeys       | keyboard          | keyboard     | keyboard     |
| Audio         | sounddevice       | sounddevice  | sounddevice  |
| Keyring       | win32cred         | Keychain     | libsecret    |

---

## 5. Security Model

### Skill Permission System

Mỗi skill khai báo permissions cần thiết trong `skill.json`:

```json
{
  "name": "file_manager",
  "version": "1.0.0",
  "permissions": ["filesystem:read", "filesystem:write", "process:list"],
  "os_support": ["windows", "macos", "linux"]
}
```

**Permission tiers:**

| Permission         | Mô tả               | Confirm required |
| ------------------ | ------------------- | ---------------- |
| `filesystem:read`  | Đọc file            | No               |
| `filesystem:write` | Ghi/xóa file        | Yes (delete)     |
| `process:list`     | List processes      | No               |
| `process:kill`     | Tắt process         | Yes              |
| `network:request`  | HTTP requests       | No               |
| `system:admin`     | Admin commands      | Yes + PIN        |
| `browser:history`  | Đọc browser history | Yes              |

### API Key Security

```python
import keyring

def save_api_key(provider: str, key: str):
    keyring.set_password("voxagent", provider, key)

def load_api_key(provider: str) -> str:
    return keyring.get_password("voxagent", provider)
```

API keys **không bao giờ** được lưu plaintext trong `config.yaml`.

---

## 6. Performance Targets

| Metric                  | Target  | Tier 0 | Tier 1 | Tier 2 | Tier 3 |
| ----------------------- | ------- | ------ | ------ | ------ | ------ |
| Wake word latency       | < 100ms | —      | —      | —      | —      |
| End-to-end (simple cmd) | < 2s    | ✅     | ✅     | —      | —      |
| End-to-end (reasoning)  | < 5s    | —      | —      | ✅     | —      |
| End-to-end (complex)    | < 15s   | —      | —      | —      | ✅     |
| Memory (idle)           | < 200MB | —      | —      | —      | —      |
| CPU (listening)         | < 5%    | —      | —      | —      | —      |

---

## 7. Cấu trúc Project

```
voxagent/
├── README.md
├── ARCHITECTURE.md
├── CONTRIBUTING.md
├── SECURITY.md
├── CODE_OF_CONDUCT.md
├── LICENSE
├── pyproject.toml
├── config.yaml
│
├── core/
│   ├── app.py           # Entry point, lifecycle management
│   ├── ears.py          # Wake word + STT
│   ├── brain.py         # Router + LLM orchestration
│   ├── hands.py         # Action execution
│   ├── eyes.py          # Screen reading (platform-agnostic)
│   ├── mouth.py         # TTS output
│   ├── autopilot.py     # Background task engine
│   └── memory.py        # Encrypted SQLite + session context
│
├── providers/
│   ├── base.py          # Abstract interfaces
│   ├── registry.py      # Factory + fallback chain
│   ├── llm/             # OpenAI, Claude, Groq, Ollama...
│   ├── stt/             # Whisper, Deepgram, Google...
│   ├── tts/             # Piper, Edge, OpenAI...
│   └── vision/          # GPT-4o, Claude, Qwen-VL...
│
├── platform/
│   ├── base.py          # SystemAutomation interface
│   ├── windows.py       # pywinauto + win32
│   ├── macos.py         # pyobjc + Accessibility
│   └── linux.py         # AT-SPI
│
├── skills/
│   ├── base.py          # BaseSkill, SkillResult, Permission
│   ├── media_control.py
│   ├── browser_control.py
│   ├── app_launcher.py
│   ├── system_control.py
│   ├── terminal.py
│   ├── file_manager.py
│   ├── screen_reader.py
│   ├── code_reviewer.py
│   └── summarizer.py
│
├── tests/
│   ├── conftest.py       # Mock providers, fixtures
│   ├── test_ears.py
│   ├── test_brain.py
│   ├── test_providers.py
│   ├── test_skills.py
│   ├── test_platform.py
│   └── benchmarks/       # Latency & accuracy benchmarks
│
└── scripts/
    ├── setup_wizard.py   # Interactive first-run setup
    ├── download_models.py
    └── train_wake_word.py
```

---

## 8. ADRs — Architecture Decision Records

### ADR-001: openWakeWord thay vì Porcupine

**Quyết định:** Dùng openWakeWord (Apache 2.0) thay Picovoice Porcupine.

**Lý do:** Porcupine yêu cầu commercial license, không compatible với Apache 2.0 OSS license của VoxAgent. openWakeWord cho accuracy tương đương với custom wake words.

### ADR-002: SQLCipher cho memory encryption

**Quyết định:** Encrypt SQLite database bằng SQLCipher, key trong OS keyring.

**Lý do:** VoxAgent lưu nội dung màn hình và lịch sử lệnh — dữ liệu nhạy cảm. Transparent encryption không ảnh hưởng API.

### ADR-003: Platform abstraction layer sớm

**Quyết định:** Abstract `SystemAutomation` interface ngay từ MVP, dù ban đầu chỉ implement Windows.

**Lý do:** Refactor về sau tốn gấp 5x chi phí. Interface chuẩn từ đầu giúp community dễ contribute macOS/Linux support.

### ADR-004: Skill permissions manifest

**Quyết định:** Mỗi skill phải khai báo permissions trong `skill.json`. Runtime enforces.

**Lý do:** Community skill marketplace cần trust model. User cần biết skill yêu cầu gì trước khi cài.
