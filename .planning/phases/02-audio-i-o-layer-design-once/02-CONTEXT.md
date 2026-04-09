# Phase 2: Audio I/O Layer (Design Once) - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Replace the unbounded audio queue with a ring buffer, normalize audio format at capture, and establish the InterruptController skeleton. This phase exists because research pitfall P1 warns: design the shared audio output layer once upfront, or rewrite it three times.

Requirements: AUDR-04 (bounded ring buffer), AUDR-05 (format normalization).

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Key guidance from research:

- AudioRingBuffer: ~60 lines, lock-free circular buffer with drop-oldest policy + metrics (drop count, high watermark)
- Format normalization: validate int16/16kHz/mono at capture point, convert if needed
- InterruptController skeleton: asyncio.Event-based cancellation for future barge-in (Phase 6)
- Use structlog (added in Phase 1) for drop/overflow logging
- Use VoxError/AudioError (from Phase 1) for audio pipeline errors

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/errors.py` — AudioError class (Phase 1)
- `core/logging.py` — get_logger() with structlog (Phase 1)
- `core/audio/recorder.py` — current mic capture with asyncio.Queue
- `core/audio/converter.py` — WAV byte encoding
- `core/audio/vad.py` — Silero VAD consuming audio chunks

### Integration Points
- `core/audio/recorder.py` — replace asyncio.Queue with AudioRingBuffer
- `core/ears.py` — consumes audio from recorder, feeds to VAD/STT
- All audio consumers must receive normalized format

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase.

</specifics>

<deferred>
## Deferred Ideas

None — infrastructure phase.

</deferred>
