# Phase 05: Streaming TTS Pipeline -- Summary

**Status:** Complete
**Date:** 2026-04-10
**Commits:** eb90010, 93eeec5, 0ce79c2, dcef351

---

## Requirements Delivered

| ID | Requirement | Implementation |
|----|-------------|----------------|
| STTS-01 | Text split at sentence boundaries | `core/audio/text_chunker.py` -- regex split at `.!?...`, merge short fragments, split long chunks at clause boundaries (`,;:--`) |
| STTS-02 | Queue-based gapless playback | `core/audio/streaming_player.py` -- `sd.OutputStream` callback pulls from `queue.Queue`, producer/consumer run concurrently |
| STTS-03 | Edge TTS streaming via miniaudio | `providers/tts/edge_tts_provider.py` -- `synthesize_stream()` yields MP3 chunks; `mouth.py` decodes via `miniaudio.decode()` |
| STTS-04 | Pre-buffer 1-2 chunks before playback | `StreamingPlayer._pre_buffer()` waits for N chunks (configurable, default 2) before opening OutputStream |

## Architecture

```
Mouth.speak_streaming(text)
  |
  +--> split_sentences(text)       # text_chunker.py
  |     -> ["Sentence 1.", "Sentence 2.", ...]
  |
  +--> asyncio.gather(producer, player)
        |
        |-- producer: for each sentence:
        |     TTSProvider.synthesize_stream(sentence)
        |       -> async yield MP3 chunks
        |     _decode_mp3_to_pcm(chunk)  # miniaudio
        |     player.enqueue(pcm_array)
        |     ...
        |     player.enqueue_sentinel()
        |
        |-- player: StreamingPlayer.play()
              _pre_buffer()    # wait for 2 chunks
              sd.OutputStream(callback=_audio_callback)
              callback pulls from queue.Queue
              _wait_for_completion() or interrupt
```

## Key Design Decisions

1. **`queue.Queue` not `asyncio.Queue`**: The sounddevice callback runs on PortAudio's C-thread and cannot `await`. Thread-safe `queue.Queue` with `get_nowait()` bridges async producer and C-thread consumer (Pitfall P1.4).

2. **miniaudio for MP3 decode**: Replaces pydub batch decode. `miniaudio.decode()` handles chunk-by-chunk MP3-to-PCM without requiring the full stream in memory (Pitfall P1.3). Falls back to pydub if miniaudio is unavailable.

3. **Sentence-level chunking**: Text is split at sentence boundaries (`.!?`), not at fixed byte offsets. Short fragments (<10 chars) are merged with neighbors. Long sentences (>300 chars) are split at clause boundaries (`,;:`).

4. **Pre-buffer before playback**: Player waits for 2 chunks before opening the OutputStream. This absorbs network jitter from the first TTS call. If only 1 chunk arrives quickly, it starts after a short additional wait.

5. **InterruptController integration**: Both the producer loop and the audio callback check `is_interrupted`. The callback outputs silence and raises `_StopCallback` on interrupt. The async `_wait_for_completion()` races the finished event against the interrupt event.

6. **Backward compatible**: `Mouth.speak()` (batch path) is preserved unchanged. `speak_streaming()` is additive. Existing callers continue to work.

## Files Changed

| File | Change |
|------|--------|
| `agent/pyproject.toml` | Added `miniaudio>=1.61` dependency |
| `agent/core/audio/text_chunker.py` | **New** -- sentence-level text splitting |
| `agent/core/audio/streaming_player.py` | **New** -- sd.OutputStream queue-based player |
| `agent/core/audio/__init__.py` | Added `StreamingPlayer` and `split_sentences` exports |
| `agent/providers/base.py` | Added `synthesize_stream()` async generator to `TTSProvider` |
| `agent/providers/tts/edge_tts_provider.py` | Added `synthesize_stream()` yielding MP3 chunks |
| `agent/core/mouth.py` | Added `speak_streaming()`, `_produce_audio()`, `_decode_mp3_to_pcm()` |
| `tests/test_text_chunker.py` | **New** -- 15 test cases |
| `tests/test_streaming_player.py` | **New** -- 11 test cases |

## Test Results

```
26 passed in 0.21s (phase 5 tests)
111 passed in 2.29s (full suite, excluding pre-existing test_ears failure)
```

## Success Criteria Verification

| Criterion | Status | Evidence |
|-----------|--------|----------|
| First audio <1.5s after LLM response | Design meets target | Pre-buffer 2 chunks (~200ms each), first sentence starts TTS immediately, playback begins after ~400ms of buffering |
| No audible gap between chunks | Design ensures gapless | Single OutputStream pulls continuously from queue; remainder buffer carries across callback invocations |
| Memory constant regardless of length | Achieved | MP3 decoded chunk-by-chunk via miniaudio; queue bounded (maxsize=10); no `b"".join(chunks)` |
| Playback after 1-2 chunks, not full response | Achieved | `_pre_buffer()` starts after 2 chunks arrive; producer continues feeding while playing |

## Phase 6 Readiness

Phase 5 outputs feed directly into Phase 6 (Barge-In & Echo Prevention):
- `InterruptController` is wired into `StreamingPlayer` (skeleton ready for wake-word triggers)
- `_StopCallback` in the audio callback enables instant stream termination
- `_drain_queue()` clears stale audio after interrupt (Pitfall P2.3)
- `_on_stream_finished` callback provides clean shutdown signal
