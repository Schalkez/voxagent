# 🤖 VOXAGENT — Voice Desktop Agent

<p align="center">
  <em>"Siri cao cấp điều khiển PC bằng giọng nói — hỗ trợ model local lẫn cloud, hiểu context, nhìn màn hình, tự hành động"</em>
</p>

<p align="center">
  <a href="https://github.com/your-org/voxagent/actions"><img src="https://img.shields.io/github/actions/workflow/status/your-org/voxagent/ci.yml?label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/voxagent-agent"><img src="https://img.shields.io/pypi/v/voxagent-agent" alt="PyPI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License"></a>
  <a href="https://discord.gg/voxagent"><img src="https://img.shields.io/discord/000000?label=Discord&logo=discord" alt="Discord"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
</p>

---

## ✨ Demo

> *Nói "VoxAgent, khi Cursor xong thì check 100% chưa, chưa thì prompt tiếp" — rồi đi pha cà phê.*

<!-- TODO: thay bằng GIF demo thực tế -->
![Demo GIF](docs/assets/demo.gif)

**VoxAgent** là AI agent chạy trên máy tính, luôn lắng nghe, nhận lệnh bằng **giọng nói**, thao tác máy tính ở tầng giao diện (chuột, bàn phím, đọc màn hình), và báo cáo kết quả bằng giọng nói. Hỗ trợ **cả model local lẫn cloud** — người dùng tự chọn provider cho từng tác vụ.

---

## 🚀 Quick Start

### Cài đặt (1 lệnh)

```bash
pip install voxagent-agent
```

Hoặc cài từ source:

```bash
git clone https://github.com/your-org/voxagent
cd voxagent
pip install -e ".[dev]"
```

### Chạy lần đầu

```bash
voxagent setup   # Wizard hướng dẫn chọn providers & cấu hình
voxagent start   # Khởi động — nói "VoxAgent" để bắt đầu
```

### Chạy với profile có sẵn

```bash
# Không có GPU, dùng cloud miễn phí
voxagent start --profile cloud_free

# Có GPU, chạy hoàn toàn offline
voxagent start --profile full_local

# Máy yếu, tối ưu chi phí
voxagent start --profile budget_cloud
```

---

## 🎯 Use Cases

| Kịch bản | Lệnh | Thời gian |
|---------|------|-----------|
| Đang nấu ăn, bỏ qua quảng cáo | *"VoxAgent, skip"* | < 1.5s |
| Kiểm tra Cursor đang code đến đâu | *"VoxAgent, Cursor xong chưa?"* | 3–5s |
| Tự động prompt Cursor khi idle | *"VoxAgent, khi xong thì check rồi prompt tiếp"* | continuous |
| Commit code | *"VoxAgent, commit, message là fix login bug"* | 5–10s |
| Tìm file | *"VoxAgent, mở file report hôm qua"* | 2–5s |
| Đọc notification | *"VoxAgent, ai nhắn gì?"* | < 2s |

---

## 🏗️ Kiến trúc

```
┌──────────────────────────────────────────────────────┐
│              🤖 VOXAGENT SYSTEM ARCHITECTURE           │
├──────────────────────────────────────────────────────┤
│  🎤 EARS          🧠 BRAIN          🔊 MOUTH         │
│  Wake Word    ──▶  Smart Router ──▶  TTS Output      │
│  Whisper STT       LLM Tiers        Tiếng Việt       │
│                    Memory                            │
│                       │                              │
│  👁️ EYES          🖐️ HANDS         ⏰ AUTOPILOT     │
│  Screenshot        PyAutoGUI        File Watcher     │
│  Win32/macOS API   Browser          Task Monitor     │
│  OCR/Vision        Terminal         Cron Tasks       │
│                                                      │
│  📦 SKILL PLUGIN SYSTEM                              │
│  media │ browser │ terminal │ files │ code │ ...     │
└──────────────────────────────────────────────────────┘
```

Chi tiết: [ARCHITECTURE.md](ARCHITECTURE.md)

---

## 🔌 Provider Support

VoxAgent hỗ trợ **provider-agnostic** — swap bất kỳ lúc nào mà không cần sửa code:

| Loại | Providers hỗ trợ |
|------|-----------------|
| **LLM** | Ollama, llama.cpp, OpenAI, Claude, Gemini, Groq, DeepSeek, Mistral, OpenRouter |
| **STT** | Whisper (local), OpenAI Whisper API, Deepgram, Google STT |
| **TTS** | Piper (local), Edge TTS, OpenAI TTS, ElevenLabs, Google TTS |
| **Vision** | Qwen-VL (local), GPT-4o, Claude, Gemini |

---

## 💸 Chi phí ước tính (cloud)

| Cách dùng | Provider gợi ý | Chi phí/ngày |
|-----------|---------------|-------------|
| Lệnh đơn giản | Groq (free tier) | **$0** |
| Dùng cả ngày nhẹ | Groq + DeepSeek | < $0.10 |
| Dev nặng + vision | Claude + GPT-4o | $1–3 |
| Full local | Ollama | **$0** |

---

## 📦 Cài đặt chi tiết

### Yêu cầu hệ thống

| Mode | CPU | RAM | GPU | Ghi chú |
|------|-----|-----|-----|---------|
| Cloud mode | Dual-core | 4GB | Không cần | Cần internet |
| Hybrid mode | Quad-core | 8–16GB | Tùy chọn | Recommended |
| Full local | 6+ cores | 16–32GB | 8–24GB VRAM | Offline hoàn toàn |

### Hệ điều hành

- **Windows 10/11** ✅ (fully supported)
- **macOS 12+** ✅ (cần cấp Accessibility permission)
- **Linux (Ubuntu 22.04+)** 🔶 (experimental, AT-SPI required)

### Cài model local (optional)

```bash
# Cài Ollama trước
curl -fsSL https://ollama.ai/install.sh | sh

# Download models cho từng tier
voxagent download-models --profile hybrid
# hoặc thủ công:
ollama pull qwen2.5:1.5b    # Tier 1
ollama pull llama3.1:8b     # Tier 2
```

---

## ⚙️ Cấu hình

File cấu hình chính: `~/.voxagent/config.yaml`

```yaml
providers:
  groq:
    api_key: "gsk_..."      # Free tier rất nhanh
  ollama:
    base_url: "http://localhost:11434"

routing:
  tier_1: { provider: "groq",   model: "llama-3.1-8b-instant" }
  tier_2: { provider: "ollama", model: "llama3.1:8b" }
  tier_3: { provider: "anthropic", model: "claude-sonnet-4-20250514" }

stt:
  provider: "local"    # local | openai | deepgram | google

tts:
  provider: "piper"    # piper | edge | openai | elevenlabs
```

Xem thêm: [docs/configuration.md](docs/configuration.md)

---

## 🔌 Skill / Plugin System

VoxAgent có thể mở rộng dễ dàng bằng skills. Xem hướng dẫn: [SKILL_DEVELOPMENT_GUIDE.md](SKILL_DEVELOPMENT_GUIDE.md)

```python
from voxagent.skills import BaseSkill, SkillResult

class MyCustomSkill(BaseSkill):
    name = "my_skill"
    description = "Mô tả để LLM biết khi nào dùng skill này"
    keywords = ["từ khoá", "trigger words"]

    def execute(self, intent, context) -> SkillResult:
        # logic của bạn ở đây
        return SkillResult(success=True, tts_response="Xong rồi!")
```

---

## 🤝 Đóng góp

Mọi đóng góp đều được chào đón! Xem [CONTRIBUTING.md](CONTRIBUTING.md) để bắt đầu.

- 🐛 [Báo lỗi](https://github.com/your-org/voxagent/issues/new?template=bug_report.md)
- 💡 [Đề xuất tính năng](https://github.com/your-org/voxagent/issues/new?template=feature_request.md)
- 🔌 [Chia sẻ skill của bạn](https://github.com/your-org/voxagent/discussions/categories/skills)
- 💬 [Discord community](https://discord.gg/voxagent)

---

## 📄 License

Apache 2.0 — xem [LICENSE](LICENSE)

---

## 🙏 Acknowledgements

- [Whisper](https://github.com/openai/whisper) — Speech recognition
- [openWakeWord](https://github.com/dscripka/openWakeWord) — Wake word detection
- [Piper TTS](https://github.com/rhasspy/piper) — Local Vietnamese TTS
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) — OCR tiếng Việt
- [Ollama](https://ollama.ai) — Local LLM runtime
