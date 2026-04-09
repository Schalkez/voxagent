# VoxAgent

## What This Is

VoxAgent is a voice-controlled desktop AI agent. It listens for "Hey Vox", transcribes speech, routes intents through a tiered model system (keyword matching -> small LLM -> large LLM), executes actions via a skill system, and responds via TTS. It runs locally on Windows/macOS/Linux with a Python backend and React dashboard. The architecture uses a human body metaphor: Ears (listen) -> Brain (think) -> Hands (act) -> Mouth (speak), with Eyes (see) and Memory (remember) as auxiliary modules.

## Core Value

Voice-first desktop automation that actually works in real-world conditions — reliable wake word detection, fast response, graceful error handling, and safe action execution.

## Requirements

### Validated

- ✓ Wake word detection ("Hey Vox") via OpenWakeWord — existing
- ✓ VAD with Silero VAD + energy fallback — existing
- ✓ STT via OpenAI Whisper (cloud) and faster-whisper (local) — existing
- ✓ TTS via Edge TTS, ElevenLabs, Piper — existing
- ✓ Tiered intent routing (keyword -> small LLM -> large LLM) — existing
- ✓ 12+ skills (terminal, browser, media, files, apps, etc.) — existing
- ✓ Permission system with dangerous action voice confirmation — existing
- ✓ Multi-provider LLM support (OpenAI, Anthropic, Groq, Ollama, DeepSeek, Mistral, OpenRouter) — existing
- ✓ SQLite memory (conversations, preferences, skill state) — existing
- ✓ Layered vision (UI tree -> OCR -> Vision LLM) — existing
- ✓ React dashboard with system monitoring — existing
- ✓ Config profiles (full_local, cloud_free, hybrid, budget_cloud) — existing
- ✓ OS keyring API key storage — existing
- ✓ Prompt injection detection — existing

### Active

- [ ] TTS interruption support (user can cut in mid-response)
- [ ] Streaming TTS (chunked playback, first-word latency <500ms)
- [ ] Provider fallback chains (TTS/STT/LLM auto-failover)
- [ ] Robust error handling (no silent failures, user-facing error messages)
- [ ] Audio pipeline resilience (no dropped chunks, backpressure management)
- [ ] Retry logic with exponential backoff for transient failures
- [ ] Type-safe parameter validation from LLM tool calls
- [ ] Noise suppression and adaptive VAD thresholds
- [ ] Acoustic echo cancellation (prevent Whisper transcribing own TTS)
- [ ] Progress feedback for long-running skills
- [ ] Terminal skill semantic safety (AST-based validation, not regex)
- [ ] Memory DB bounded growth with cleanup policies

### Out of Scope

- Messaging channels (Telegram, WhatsApp, etc.) — VoxAgent is voice-only by design
- Mobile companion apps — desktop-first focus
- Multi-user / multi-tenant — personal single-user assistant
- Plugin marketplace — skill system sufficient for v1
- MCP protocol support — not needed for voice-first architecture
- Web chat / text-only mode — voice is the primary interface

## Context

VoxAgent is a brownfield project with ~14,229 lines of core Python code. The architecture is clean (SRP modules, provider abstractions, tiered execution) but error handling, resilience, and production edge cases are weak.

A deep analysis against OpenClaw (a production-grade personal AI assistant) revealed 12 critical and high-severity gaps that would break real-world usage:

**Critical (5):** No TTS interruption, no streaming TTS, silent failures everywhere, audio chunks dropped silently, no provider fallback.

**High (7):** Terminal safety filter bypassable, no retry/backoff, no parameter validation, no noise suppression, no echo cancellation, no progress feedback, memory DB unbounded.

**Reference codebase:** OpenClaw patterns to adopt include WebSocket backpressure management, pre-start timeout with `unref()`, type-safe parameter extraction helpers, custom error hierarchy with status codes, idempotent cleanup patterns, and queue-based TTS with AbortController for barge-in.

**Tech stack:** Python 3.12+ (FastAPI, aiosqlite, httpx, sounddevice, faster-whisper, edge-tts), TypeScript ~5.9 (React 19, Vite 8, Tailwind 4).

## Constraints

- **Language**: Python 3.12+ backend, TypeScript frontend (no changes)
- **Voice-only**: All improvements must serve the voice pipeline — no text/chat channels
- **Backward compatible**: Existing skills, providers, and config must continue working
- **Local-first**: Core functionality must work without cloud APIs (Ollama + Piper + faster-whisper)
- **Security**: No regression on existing safety measures (permission system, prompt injection detection)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Reference OpenClaw patterns for hardening | Production-proven patterns for voice/audio/execution resilience | — Pending |
| Hardening all 12 Critical+High issues | User wants production-ready voice assistant, not just a prototype | — Pending |
| Keep voice-only focus | VoxAgent's identity is voice-first desktop automation, not a messaging platform | — Pending |
| Adopt error hierarchy pattern | Custom error classes with severity levels, not generic exceptions | — Pending |
| Implement provider fallback chains | Single-provider failure should not kill entire pipeline | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-09 after initialization*
