# Requirements: VoxAgent Production Hardening

**Defined:** 2026-04-09
**Core Value:** Voice-first desktop automation that actually works in real-world conditions

## v1 Requirements

Requirements for production hardening milestone. Each maps to roadmap phases.

### Barge-In

- [ ] **BGIN-01**: Wake word detector runs continuously during TTS playback and triggers interrupt within 100ms
- [ ] **BGIN-02**: Audio fades out over 15-25ms on interrupt instead of hard stop (no click/pop artifacts)
- [ ] **BGIN-03**: In-flight TTS synthesis HTTP requests are cancelled on interrupt (save API cost)
- [ ] **BGIN-04**: Pipeline state machine enforces LISTENING->PROCESSING->SPEAKING->INTERRUPTED->LISTENING transitions without race conditions

### Streaming TTS

- [ ] **STTS-01**: LLM response text is split at sentence boundaries before sending to TTS provider
- [ ] **STTS-02**: Audio playback consumes from asyncio.Queue of chunks — play chunk N while N+1 synthesizes (gapless)
- [ ] **STTS-03**: Edge TTS streaming output consumed incrementally via miniaudio decoder (not collected then converted)
- [ ] **STTS-04**: Playback starts after buffering 1-2 chunks, not after all chunks arrive (first-word latency <1.5s)

### Provider Resilience

- [ ] **PROV-01**: LLM fallback chain wired into Brain — if primary provider fails, auto-failover to next
- [ ] **PROV-02**: TTS fallback chain — Edge TTS down -> ElevenLabs -> Piper local
- [ ] **PROV-03**: STT fallback chain — OpenAI Whisper down -> faster-whisper local
- [ ] **PROV-04**: Circuit breaker per provider — after N consecutive failures, skip provider for cooldown period
- [ ] **PROV-05**: Retry with exponential backoff on transient failures (tenacity)
- [ ] **PROV-06**: Shared httpx client per provider with connection pooling (not new client per request)
- [ ] **PROV-07**: Provider health cached with TTL — no health checks in hot path

### Error Handling

- [ ] **ERRH-01**: Custom VoxError hierarchy with severity (critical/warning/info), user_message, and retryable flag
- [ ] **ERRH-02**: User hears spoken error messages instead of silent failures (e.g., "Không kết nối được OpenAI, đang chuyển sang Groq")
- [ ] **ERRH-03**: Error earcon plays before spoken error (distinct beep for errors vs success)
- [ ] **ERRH-04**: Structured error logging via structlog with context vars (provider, skill, latency)
- [ ] **ERRH-05**: Standardized SkillResult error format returned from all skills

### Audio Resilience

- [ ] **AUDR-01**: Mic muted (input discarded) while TTS is playing — prevents echo feedback loop
- [ ] **AUDR-02**: VAD thresholds adapt to ambient noise level (not hardcoded RMS 500.0)
- [ ] **AUDR-03**: VAD hysteresis — require N consecutive speech frames to start, M silence frames to stop
- [ ] **AUDR-04**: Audio queue uses bounded ring buffer with drop-oldest policy and metrics (not unbounded asyncio.Queue)
- [ ] **AUDR-05**: Audio format normalized to int16/16kHz/mono at capture — validate before processing

### Progress Feedback

- [ ] **PROG-01**: Immediate acknowledgment earcon plays when wake word detected (user knows system heard them)
- [ ] **PROG-02**: Timeout-based progress update — if skill runs >3s, speak "Đang xử lý..." with periodic updates

### Safety & Security

- [ ] **SAFE-01**: Terminal skill validates commands via AST parsing, not regex pattern matching
- [ ] **SAFE-02**: Remove python/pip/node/git from terminal allowlist (arbitrary code execution vectors)
- [ ] **SAFE-03**: Type-safe parameter extraction from LLM tool calls with validation and fallback
- [ ] **SAFE-04**: PromptGuard integrated into Brain.process() pipeline (exists but unwired)
- [ ] **SAFE-05**: Per-skill execution timeout enforced (configurable, default 30s)
- [ ] **SAFE-06**: File operations restricted to user-configurable allowed directories
- [ ] **SAFE-07**: Memory DB bounded growth — auto-prune conversations older than configurable TTL
- [ ] **SAFE-08**: API server requires authentication token (not open localhost)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Streaming Enhancements

- **STTS-05**: ElevenLabs WebSocket streaming API for lowest latency
- **STTS-06**: LLM token streaming piped directly to TTS (sentence boundary detection in token stream)

### Advanced Audio

- **AUDR-06**: speexdsp adaptive echo cancellation for true full-duplex barge-in
- **AUDR-07**: deepfilternet neural noise suppression
- **AUDR-08**: Multi-language VAD tuning (per-language thresholds)

### Advanced Safety

- **SAFE-09**: Container-based skill sandboxing for untrusted commands
- **SAFE-10**: Marketplace skill code signing verification
- **SAFE-11**: Comprehensive audit log persisted to disk with rotation

### Intelligence

- **INTL-01**: Conversation context carryover (Brain maintains recent N intents)
- **INTL-02**: Multi-step intent planning (decompose complex commands into subtasks)
- **INTL-03**: Intent disambiguation (ask user when confidence < threshold)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full-duplex barge-in (voice-activity triggered) | Requires hardware AEC; software AEC unreliable on commodity PC hardware |
| Multi-mic beamforming | Specialized hardware; desktop typically has single mic |
| AI-based command risk scoring | Circular LLM dependency; static rules safer |
| Process sandboxing via containers | Contradicts desktop automation purpose (skills need system access) |
| Adaptive TTS chunk sizing | Over-engineering; fixed sentence-level sufficient for desktop |
| Emotional prosody control | TTS providers don't support reliable emotion control |
| Real-time voice biometrics | Complexity/accuracy tradeoff not worth it for single-user |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| BGIN-01 | TBD | Pending |
| BGIN-02 | TBD | Pending |
| BGIN-03 | TBD | Pending |
| BGIN-04 | TBD | Pending |
| STTS-01 | TBD | Pending |
| STTS-02 | TBD | Pending |
| STTS-03 | TBD | Pending |
| STTS-04 | TBD | Pending |
| PROV-01 | TBD | Pending |
| PROV-02 | TBD | Pending |
| PROV-03 | TBD | Pending |
| PROV-04 | TBD | Pending |
| PROV-05 | TBD | Pending |
| PROV-06 | TBD | Pending |
| PROV-07 | TBD | Pending |
| ERRH-01 | TBD | Pending |
| ERRH-02 | TBD | Pending |
| ERRH-03 | TBD | Pending |
| ERRH-04 | TBD | Pending |
| ERRH-05 | TBD | Pending |
| AUDR-01 | TBD | Pending |
| AUDR-02 | TBD | Pending |
| AUDR-03 | TBD | Pending |
| AUDR-04 | TBD | Pending |
| AUDR-05 | TBD | Pending |
| PROG-01 | TBD | Pending |
| PROG-02 | TBD | Pending |
| SAFE-01 | TBD | Pending |
| SAFE-02 | TBD | Pending |
| SAFE-03 | TBD | Pending |
| SAFE-04 | TBD | Pending |
| SAFE-05 | TBD | Pending |
| SAFE-06 | TBD | Pending |
| SAFE-07 | TBD | Pending |
| SAFE-08 | TBD | Pending |

**Coverage:**
- v1 requirements: 35 total
- Mapped to phases: 0
- Unmapped: 35

---
*Requirements defined: 2026-04-09*
*Last updated: 2026-04-09 after initial definition*
