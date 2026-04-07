# VOXAGENT — Future Roadmap

> Items deferred from current development cycle. Revisit when prerequisites are met.

---

## 🔮 Deferred Features

### 1. Mobile Companion App
- **Status:** Deferred — Separate project
- **Reason:** Requires dedicated mobile codebase (React Native / Flutter), separate CI/CD
- **Prerequisites:** Stable API server mode (Phase 5), WebSocket protocol for real-time sync
- **Estimated Effort:** 2-4 weeks
- **Notes:** Consider using the existing `api/server_mode.py` as the backend, `core/sync.py` for device pairing

### 2. LLM Fine-tuning on User Commands
- **Status:** Deferred — Research phase
- **Reason:** Requires significant training data collection, GPU infrastructure, and evaluation pipeline
- **Prerequisites:**
  - Minimum 10k labeled conversation entries in `memory.db`
  - Training infrastructure (cloud GPU or local A100/H100)
  - Evaluation framework for intent accuracy
- **Estimated Effort:** 4-8 weeks (research + implementation)
- **Notes:** Consider LoRA/QLoRA fine-tuning on Mistral-7B or Llama-3-8B as starter approach

---

## 📋 How to Promote a Feature

When ready to implement a deferred feature:
1. Move the item from `FUTURE.md` to `TASKS.md` under a new Phase
2. Create a feature branch: `feat/<feature-name>`
3. Update `pyproject.toml` dependencies if needed
4. Add tests before implementation (TDD)
5. Update CI workflow if new dependencies are required
