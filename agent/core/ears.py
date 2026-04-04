"""EARS module: Voice input pipeline orchestrator.

Pipeline: Mic → Wake Word → VAD → STT → Raw text

This module orchestrates the audio sub-components (AudioRecorder,
WakeWordDetector, VoiceActivityDetector, AudioConverter) and delegates
STT to an injected provider. It contains no audio logic itself.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

import numpy as np

from core.audio.converter import AudioConverter
from core.audio.recorder import CHUNK_DURATION_MS, AudioRecorder
from core.audio.vad import VoiceActivityDetector
from core.audio.wake_word import WakeWordDetector

if TYPE_CHECKING:
    from core.config import VoxAgentConfig
    from providers.base import STTProvider, TranscribeResult

logger = logging.getLogger("voxagent.ears")

# ── Named Constants ───────────────────────────────

VAD_SILENCE_TIMEOUT_S: float = 1.5
MAX_RECORDING_S: int = 30


# ── Data Classes ──────────────────────────────────


class EarsState(Enum):
    """Current state of the Ears pipeline."""

    IDLE = auto()
    LISTENING_FOR_WAKE_WORD = auto()
    RECORDING_SPEECH = auto()
    TRANSCRIBING = auto()
    STOPPED = auto()


@dataclass
class EarsEvent:
    """Event emitted by the Ears pipeline for UI/logging.

    Attributes:
        state: Current pipeline state.
        message: Human-readable description of the event.
    """

    state: EarsState
    message: str = ""


@dataclass(frozen=True)
class EmptyTranscribeResult:
    """Lightweight result for when no audio was captured.

    Mirrors the TranscribeResult interface without importing
    it at runtime (solid-dip compliance).
    """

    text: str = ""
    confidence: float = 0.0
    language: str = "vi"
    duration_ms: int = 0


# ── Orchestrator ──────────────────────────────────


class Ears:
    """Orchestrates the voice input pipeline.

    Coordinates AudioRecorder, WakeWordDetector, VoiceActivityDetector,
    and AudioConverter to implement the full voice-to-text flow.
    Contains no audio processing logic — delegates to sub-components.

    Args:
        stt_provider: Injected STT provider for transcription.
        config: VoxAgent configuration.
    """

    def __init__(
        self,
        stt_provider: STTProvider,
        config: VoxAgentConfig,
    ) -> None:
        self._stt_provider = stt_provider
        self._config = config
        self._state = EarsState.IDLE

        # Sub-components (SRP: each has one job)
        self._recorder = AudioRecorder()
        self._wake_word_detector = WakeWordDetector(
            sensitivity=config.wake_word.sensitivity,
        )
        self._vad = VoiceActivityDetector()

        # Event callbacks
        self._event_callbacks: list[Callable[[EarsEvent], None]] = []

    @property
    def state(self) -> EarsState:
        """Current state of the Ears pipeline."""
        return self._state

    # ── Event System ──────────────────────────────

    def on_event(self, callback: Callable[[EarsEvent], None]) -> None:
        """Register a callback for pipeline state changes."""
        self._event_callbacks.append(callback)

    def _emit(self, state: EarsState, message: str = "") -> None:
        """Update state and notify all registered callbacks."""
        self._state = state
        event = EarsEvent(state=state, message=message)
        for registered_callback in self._event_callbacks:
            try:
                registered_callback(event)
            except (TypeError, ValueError, AttributeError):
                logger.exception("Event callback error")

    # ── Lifecycle ─────────────────────────────────

    async def start_listening(self) -> None:
        """Start microphone and load detection models.

        Raises:
            RuntimeError: If microphone is unavailable.
        """
        self._emit(EarsState.LISTENING_FOR_WAKE_WORD, "Initializing...")

        self._wake_word_detector.load()
        self._vad.load()
        await self._recorder.start()

        self._emit(
            EarsState.LISTENING_FOR_WAKE_WORD,
            f"Listening for '{self._config.wake_word.phrase}'...",
        )

    async def stop_listening(self) -> None:
        """Stop listening and release all resources."""
        await self._recorder.stop()
        self._wake_word_detector.unload()
        self._vad.unload()
        self._emit(EarsState.STOPPED, "Ears stopped")

    # ── Main Pipeline ─────────────────────────────

    async def wait_for_command(self) -> TranscribeResult | EmptyTranscribeResult:
        """Wait for wake word, record speech, transcribe.

        Returns:
            TranscribeResult or EmptyTranscribeResult if no audio.

        Raises:
            RuntimeError: If ears are not started.
        """
        self._ensure_started()

        # Step 1: Wait for wake word
        self._emit(
            EarsState.LISTENING_FOR_WAKE_WORD,
            f"Waiting for '{self._config.wake_word.phrase}'...",
        )
        await self._wait_for_wake_word()

        # Step 2: Record until silence
        self._emit(EarsState.RECORDING_SPEECH, "Recording...")
        logger.info("Wake word detected — recording speech")
        frames = await self._record_until_silence()

        if not frames:
            return EmptyTranscribeResult()

        # Step 3: Transcribe
        return await self._transcribe_frames(frames)

    async def push_to_talk(
        self, duration_s: float = 5.0
    ) -> TranscribeResult | EmptyTranscribeResult:
        """Record for a fixed duration and transcribe.

        Args:
            duration_s: Duration to record in seconds.

        Returns:
            TranscribeResult or EmptyTranscribeResult if no audio.
        """
        self._ensure_started()

        self._emit(EarsState.RECORDING_SPEECH, f"PTT: recording {duration_s}s...")
        frames = await self._capture_fixed_duration(duration_s)

        if not frames:
            return EmptyTranscribeResult()

        return await self._transcribe_frames(frames)

    # ── Internal: Orchestration ───────────────────

    def _ensure_started(self) -> None:
        """Guard clause: raise if not started."""
        if not self._recorder.is_active:
            raise RuntimeError("Ears not started. Call start_listening() first.")

    async def _wait_for_wake_word(self) -> None:
        """Feed audio chunks to wake word detector until triggered."""
        while self._state == EarsState.LISTENING_FOR_WAKE_WORD:
            chunk = await self._recorder.read_chunk()
            if chunk is None:
                continue
            if self._wake_word_detector.detect(chunk):
                return

    async def _record_until_silence(self) -> list[np.ndarray]:
        """Record audio frames until VAD detects end-of-speech."""
        frames: list[np.ndarray] = []
        silence_chunks = 0
        max_silence_chunks = int(VAD_SILENCE_TIMEOUT_S * 1000 / CHUNK_DURATION_MS)
        max_total_chunks = int(MAX_RECORDING_S * 1000 / CHUNK_DURATION_MS)

        for _ in range(max_total_chunks):
            chunk = await self._recorder.read_chunk()
            if chunk is None:
                continue

            frames.append(chunk)

            if self._vad.detect_speech(chunk):
                silence_chunks = 0
            else:
                silence_chunks += 1
                if silence_chunks >= max_silence_chunks and len(frames) > max_silence_chunks:
                    frames = frames[: len(frames) - silence_chunks + 2]
                    logger.debug("End of speech after %d frames", len(frames))
                    break

        return frames

    async def _capture_fixed_duration(self, duration_s: float) -> list[np.ndarray]:
        """Capture audio for a fixed duration (push-to-talk)."""
        frames: list[np.ndarray] = []
        chunks_needed = int(duration_s * 1000 / CHUNK_DURATION_MS)

        for _ in range(chunks_needed):
            chunk = await self._recorder.read_chunk()
            if chunk is None:
                break
            frames.append(chunk)

        return frames

    async def _transcribe_frames(self, frames: list[np.ndarray]) -> TranscribeResult:
        """Convert frames to WAV and transcribe via STT provider."""
        wav_bytes = AudioConverter.frames_to_wav(frames)
        duration_ms = int(len(frames) * CHUNK_DURATION_MS)

        self._emit(EarsState.TRANSCRIBING, "Transcribing...")
        logger.info("Transcribing %d ms of audio...", duration_ms)

        result = await self._stt_provider.transcribe(
            wav_bytes,
            language=self._config.stt.language,
        )

        self._emit(
            EarsState.LISTENING_FOR_WAKE_WORD,
            f"Transcribed: '{result.text}'",
        )
        logger.info("Transcription: '%s' (confidence=%.2f)", result.text, result.confidence)
        return result
