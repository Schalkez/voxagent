# 🗺️ VOXAGENT Roadmap

> Trạng thái: **Production Hardening Complete** — Phase 1-9 done, Phase 10 (Integration Testing) in progress

Roadmap này được cập nhật sau mỗi milestone. Community có thể vote và comment trên [GitHub Discussions](https://github.com/your-org/voxagent/discussions/categories/roadmap).

---

## Phase 1 — Enterprise Core Foundation: Voice Command & Respond (Tuần 1–2)

**Goal:** Nói được lệnh đơn giản, VoxAgent thực hiện và trả lời bằng giọng.

- [ ] Core pipeline: ears → brain → hands → mouth
- [ ] Provider system: base interfaces + registry
- [ ] Wake word (openWakeWord) + push-to-talk hotkey fallback
- [ ] STT: Whisper local + OpenAI API option
- [ ] Tier 0 routing (keyword matching — không cần LLM)
- [ ] Skills: `media_control`, `app_launcher`, `system_control`
- [ ] TTS: Piper (local Vietnamese) + Edge TTS
- [ ] Config system (YAML) + 4 built-in profiles
- [ ] System tray app (pystray) — Windows
- [ ] **[NEW]** Platform abstraction layer (`SystemAutomation` interface)
- [ ] **[NEW]** CI/CD: GitHub Actions chạy tests tự động
- [ ] **[NEW]** API key lưu trong OS keyring (không plaintext)

**Acceptance test:** *"VoxAgent, skip"* → YouTube skip ad trong < 2 giây.

---

## Phase 2 — Smart Brain (Tuần 3–4)

**Goal:** Hiểu câu phức tạp, multi-step planning, conversation memory.

- [ ] LLM providers: OpenAI, Claude, Groq, Ollama, DeepSeek
- [ ] Tier 1–2 routing (smart model selection)
- [ ] Skills: `terminal`, `file_manager`, `browser_control`
- [ ] Conversation memory (SQLite + SQLCipher encryption)
- [ ] Multi-step action planning
- [ ] Fallback chain (auto-switch provider khi fail)
- [ ] **[NEW]** Skill permission system (manifest + runtime enforcement)
- [ ] **[NEW]** macOS platform implementation (pyobjc + Accessibility API)
- [ ] **[NEW]** Unit test coverage ≥ 70% cho core modules

**Acceptance test:** *"VoxAgent, mở Chrome, vào gmail, đọc email mới nhất"* — 3 actions liên tiếp.

---

## Phase 3 — Eyes & Autopilot (Tuần 5–6)

**Goal:** Nhìn và hiểu màn hình, chạy task tự động không cần can thiệp.

- [ ] Screen capture + Win32 / macOS Accessibility
- [ ] OCR: PaddleOCR (tiếng Việt) + Tesseract fallback
- [ ] Vision providers: GPT-4o, Claude, Gemini, Qwen-VL local
- [ ] Skills: `screen_reader`, `code_reviewer`
- [ ] Autopilot engine: time/event/condition/idle triggers
- [ ] **[NEW]** Prompt injection protection (untrusted screen content isolation)
- [ ] **[NEW]** Linux platform (AT-SPI) — experimental
- [ ] **[NEW]** Benchmark suite: latency per tier, STT accuracy

**Acceptance test (killer demo):** *"VoxAgent, khi Cursor xong thì check 100% chưa, chưa thì prompt tiếp, xong thì báo tôi"* — hands-free, continuous monitoring.

---

## Phase 4 — Polish & Community (Tuần 7+)

**Goal:** Production-ready, dễ cài, có community.

- [ ] Windows installer (.exe) với auto-update
- [ ] macOS .dmg + Homebrew formula
- [ ] Linux Flatpak/Snap package
- [ ] **[NEW]** One-liner install: `pip install voxagent-agent`
- [ ] **[NEW]** Skill marketplace (skill.json registry + review process)
- [ ] **[NEW]** Documentation site (MkDocs)
- [ ] **[NEW]** Custom wake word training UI
- [ ] Web dashboard: monitoring, config, skill management
- [ ] Multi-language support (i18n architecture)
- [ ] **[NEW]** Opt-in telemetry (anonymous usage stats)
- [ ] **[NEW]** Plugin dependency resolver

---

## Phase 5 — Scale (Q3 2025+)

Những tính năng community vote cao — chưa committed:

- [ ] Mobile companion app (xem status, gửi lệnh text)
- [ ] Multi-device sync (VoxAgent trên nhiều máy tính)
- [ ] VoxAgent API server mode (cho home automation, n8n integration)
- [ ] Custom voice cloning (TTS bằng giọng của bạn)
- [ ] Multi-language conversation trong cùng session
- [ ] LLM fine-tuning trên lệnh của người dùng cụ thể

---

## Không nằm trong scope

Để tránh feature creep, các thứ sau VoxAgent **không** build:

- **GUI chat interface** — dùng Claude.ai, ChatGPT cho việc đó
- **Web scraping framework** — dùng Playwright trực tiếp
- **Smart home control** — có Home Assistant rồi
- **Mobile STT** — VoxAgent là desktop agent

---

## Cách contribute vào roadmap

1. Vote và comment trên [Discussions > Roadmap](https://github.com/your-org/voxagent/discussions/categories/roadmap)
2. Tính năng được vote nhiều sẽ được prioritize
3. Maintainers review và update roadmap sau mỗi release

---

## Versioning

VoxAgent theo [Semantic Versioning](https://semver.org/):
- `0.x.y` — Pre-stable. Breaking changes có thể xảy ra.
- `1.0.0` — Stable API. Breaking changes chỉ ở major versions.

Target `1.0.0`: Khi Phase 3 hoàn thành + cross-platform (Windows + macOS) + skill marketplace live.
