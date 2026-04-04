"""EARS module: Wake word detection + STT transcription.

Pipeline: Mic → Wake Word Detector → VAD → STT → Raw text

This module is provider-agnostic: it delegates STT to whatever
provider is injected via the constructor. Wake word and VAD run
locally using lightweight ONNX models.
"""

from __future__ import annotations

import asyncio
import io
import logging
import wave
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

    from core.config import VoxAgentConfig
    from providers.base import STTProvider, TranscribeResult

logger = logging.getLogger("voxagent.ears")

# ── Named Constants ───────────────────────────────
# naming-constants: extract all magic values

SAMPLE_RATE: int = 16_000  # 16 kHz — standard for speech models
CHANNELS: int = 1  # Mono
CHUNK_DURATION_MS: int = 80  # 80ms chunks — good balance for OWW
CHUNK_SAMPLES: int = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)

VAD_SILENCE_TIMEOUT_S: float = 1.5  # Stop recording after 1.5s of silence
VAD_SPEECH_THRESHOLD: float = 0.5  # Silero VAD confidence threshold
MAX_RECORDING_S: int = 30  # Safety cap: max 30s recording
ENERGY_VAD_THRESHOLD: float = 500.0  # RMS energy threshold for fallback VAD

WAKE_WORD_THRESHOLD: float = 0.7  # Detection confidence threshold
AUDIO_QUEUE_TIMEOUT_S: float = 0.5  # Timeout for async queue reads


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

    Mirrors the TranscribeResult interface from providers.base without
    importing it at runtime (solid-dip compliance).
    """

    text: str = ""
    confidence: float = 0.0
    language: str = "vi"
    duration_ms: int = 0


# ── Main Class ────────────────────────────────────


class Ears:
    """Manages the voice input pipeline.

    Handles wake word detection (OpenWakeWord), Voice Activity Detection
    (Silero VAD via ONNX), and Speech-to-Text transcription delegated
    to an injected STTProvider.

    This class is provider-agnostic: it never imports concrete STT
    implementations. All audio processing (wake word, VAD) runs locally
    using lightweight ONNX models.

    Args:
        stt_provider: Injected STT provider for transcription.
        config: VoxAgent configuration for audio/wake word settings.
    """

    def __init__(
        self,
        stt_provider: STTProvider,
        config: VoxAgentConfig,
    ) -> None:
        self._stt_provider = stt_provider
        self._config = config
        self._state = EarsState.IDLE

        # Audio stream (initialized in start_listening)
        self._stream: object | None = None
        self._audio_queue: asyncio.Queue[np.ndarray] = asyncio.Queue()

        # Wake word model (lazy-loaded)
        self._wake_word_model: object | None = None

        # VAD model (lazy-loaded)
        self._vad_model: object | None = None

        # Callbacks for UI state updates
        self._event_callbacks: list[Callable[[EarsEvent], None]] = []

    # ── Properties ────────────────────────────────

    @property
    def state(self) -> EarsState:
        """Current state of the Ears pipeline."""
        return self._state

    # ── Event System ──────────────────────────────

    def on_event(self, callback: Callable[[EarsEvent], None]) -> None:
        """Register a callback for pipeline state changes.

        Args:
            callback: Function that receives EarsEvent objects.
        """
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
        """Start microphone capture and wake word detection.

        Opens an audio stream via sounddevice and initializes the
        OpenWakeWord model. Uses approximately 1-2% CPU when idle.

        Raises:
            RuntimeError: If microphone is unavailable.
        """
        # deps-lazy-load: heavy imports at use site
        import sounddevice as sd

        self._emit(EarsState.LISTENING_FOR_WAKE_WORD, "Initializing microphone...")

        # Initialize models
        self._wake_word_model = self._load_wake_word_model()
        self._vad_model = self._load_vad_model()

        # Clear stale audio queue
        self._drain_audio_queue()

        # Open audio stream with callback
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SAMPLES,
                callback=self._audio_stream_callback,
            )
            self._stream.start()
            self._emit(
                EarsState.LISTENING_FOR_WAKE_WORD,
                f"Listening for wake word '{self._config.wake_word.phrase}'...",
            )
            logger.info("Ears started — listening for wake word")
        except (OSError, sd.PortAudioError) as exc:
            self._emit(EarsState.STOPPED, f"Microphone error: {exc}")
            raise RuntimeError(f"Failed to open microphone: {exc}") from exc

    async def stop_listening(self) -> None:
        """Stop listening and release audio resources.

        Closes the audio stream and frees microphone access.
        Safe to call multiple times.
        """
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except OSError:
                logger.exception("Error closing audio stream")
            finally:
                self._stream = None

        self._wake_word_model = None
        self._vad_model = None
        self._emit(EarsState.STOPPED, "Ears stopped")
        logger.info("Ears stopped — microphone released")

    # ── Main Pipeline ─────────────────────────────

    async def wait_for_command(self) -> TranscribeResult | EmptyTranscribeResult:
        """Block until wake word detected, then transcribe speech.

        Full pipeline:
        1. Wait for wake word ("hey vox") in audio stream
        2. Capture speech until VAD detects silence (>1.5s)
        3. Convert captured audio to WAV bytes
        4. Delegate transcription to injected STTProvider

        Returns:
            TranscribeResult with the transcribed text and metadata,
            or EmptyTranscribeResult if no audio was captured.

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
        self._emit(EarsState.RECORDING_SPEECH, "Recording speech...")
        logger.info("Wake word detected — recording speech")
        audio_frames = await self._record_until_silence()

        if not audio_frames:
            return EmptyTranscribeResult()

        # Step 3: Convert to WAV bytes
        wav_bytes = self._frames_to_wav(audio_frames)
        duration_ms = int(len(audio_frames) * CHUNK_DURATION_MS)

        # Step 4: Transcribe via injected STT provider
        self._emit(EarsState.TRANSCRIBING, "Transcribing...")
        logger.info("Transcribing %d ms of audio...", duration_ms)

        result = await self._stt_provider.transcribe(
            wav_bytes,
            language=self._config.stt.language,
        )

        self._emit(
            EarsState.LISTENING_FOR_WAKE_WORD,
            f"Transcribed: '{result.text}' — listening again...",
        )
        logger.info("Transcription: '%s' (confidence=%.2f)", result.text, result.confidence)
        return result

    async def push_to_talk(self, duration_s: float = 5.0) -> TranscribeResult | EmptyTranscribeResult:
        """Record for a fixed duration and transcribe (bypass wake word).

        Fallback mode for environments where wake word detection
        is unreliable or for keyboard-triggered recording.

        Args:
            duration_s: Duration to record in seconds (default 5s).

        Returns:
            TranscribeResult with the transcribed text and metadata,
            or EmptyTranscribeResult if no audio was captured.

        Raises:
            RuntimeError: If ears are not started.
        """
        self._ensure_started()

        self._emit(EarsState.RECORDING_SPEECH, f"Push-to-talk: recording {duration_s}s...")
        logger.info("Push-to-talk: recording %.1fs", duration_s)

        frames = await self._capture_fixed_duration(duration_s)

        if not frames:
            return EmptyTranscribeResult()

        wav_bytes = self._frames_to_wav(frames)

        self._emit(EarsState.TRANSCRIBING, "Transcribing...")
        result = await self._stt_provider.transcribe(
            wav_bytes,
            language=self._config.stt.language,
        )

        self._emit(EarsState.LISTENING_FOR_WAKE_WORD, f"PTT result: '{result.text}'")
        return result

    # ── Internal: Guard Clauses ───────────────────
    # error-early-return: guard at top, happy path below

    def _ensure_started(self) -> None:
        """Raise if ears are not started."""
        if self._stream is None:
            raise RuntimeError("Ears not started. Call start_listening() first.")

    def _drain_audio_queue(self) -> None:
        """Clear any stale audio from the queue."""
        while not self._audio_queue.empty():
            self._audio_queue.get_nowait()

    # ── Internal: Audio Stream ────────────────────

    def _audio_stream_callback(
        self,
        indata: npt.NDArray[np.int16],
        frames: int,
        time_info: object,
        status: object,
    ) -> None:
        """Callback invoked by sounddevice for each audio chunk."""
        if status:
            logger.warning("Audio stream status: %s", status)
        try:
            self._audio_queue.put_nowait(indata.copy())
        except asyncio.QueueFull:
            pass  # Drop frames if queue is full

    async def _read_audio_chunk(self) -> np.ndarray | None:
        """Read one audio chunk from the queue with timeout.

        Returns:
            Audio chunk or None if timed out.
        """
        try:
            return await asyncio.wait_for(
                self._audio_queue.get(),
                timeout=AUDIO_QUEUE_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            return None

    # ── Internal: Wake Word ───────────────────────

    def _load_wake_word_model(self) -> object:
        """Load the OpenWakeWord model for wake word detection.

        Returns:
            Initialized openwakeword.Model instance.
        """
        # deps-lazy-load: heavy imports at use site
        from openwakeword.model import Model as OpenWakeWordModel

        model = OpenWakeWordModel(inference_framework="onnx")
        logger.info("OpenWakeWord model loaded (ONNX backend)")
        return model

    async def _wait_for_wake_word(self) -> None:
        """Listen continuously until the wake word is detected.

        Feeds audio chunks into the OpenWakeWord model and checks
        prediction scores against the configured sensitivity threshold.
        """
        threshold = self._config.wake_word.sensitivity

        while self._state == EarsState.LISTENING_FOR_WAKE_WORD:
            chunk = await self._read_audio_chunk()
            if chunk is None:
                continue

            audio_flat = chunk.flatten()
            self._wake_word_model.predict(audio_flat)

            if self._check_wake_word_scores(threshold):
                return

    def _check_wake_word_scores(self, threshold: float) -> bool:
        """Check if any wake word score exceeds the threshold.

        Args:
            threshold: Minimum confidence to trigger detection.

        Returns:
            True if a wake word was detected.
        """
        for model_name, score in self._wake_word_model.prediction_buffer.items():
            latest_score = score[-1] if score else 0.0
            if latest_score >= threshold:
                logger.info(
                    "Wake word '%s' detected (score=%.3f, threshold=%.2f)",
                    model_name,
                    latest_score,
                    threshold,
                )
                self._wake_word_model.reset()
                return True
        return False

    # ── Internal: VAD Recording ───────────────────

    def _load_vad_model(self) -> object | None:
        """Load the Silero VAD model via ONNX Runtime.

        Returns:
            Silero VAD model, or None if not installed.
        """
        try:
            # deps-lazy-load: heavy imports at use site
            from silero_vad import load_silero_vad

            model = load_silero_vad(onnx=True)
            logger.info("Silero VAD loaded (ONNX backend)")
            return model
        except ImportError:
            logger.warning("silero-vad not installed — using energy-based VAD fallback")
            return None

    async def _record_until_silence(self) -> list[np.ndarray]:
        """Record audio until VAD detects end-of-speech silence.

        Uses Silero VAD to detect speech vs silence. Recording stops
        when silence exceeds VAD_SILENCE_TIMEOUT_S or total recording
        exceeds MAX_RECORDING_S.

        Returns:
            List of audio frame arrays (int16).
        """
        frames: list[np.ndarray] = []
        silence_chunks = 0
        max_silence_chunks = int(VAD_SILENCE_TIMEOUT_S * 1000 / CHUNK_DURATION_MS)
        max_total_chunks = int(MAX_RECORDING_S * 1000 / CHUNK_DURATION_MS)

        for _ in range(max_total_chunks):
            chunk = await self._read_audio_chunk()
            if chunk is None:
                continue

            frames.append(chunk)

            is_speech = self._detect_speech(chunk)
            if is_speech:
                silence_chunks = 0
            else:
                silence_chunks += 1
                if self._should_stop_recording(silence_chunks, max_silence_chunks, len(frames)):
                    frames = frames[: len(frames) - silence_chunks + 2]
                    logger.debug("VAD: end of speech after %d frames", len(frames))
                    break

        return frames

    @staticmethod
    def _should_stop_recording(
        silence_chunks: int,
        max_silence_chunks: int,
        total_frames: int,
    ) -> bool:
        """Determine if recording should stop based on silence duration.

        Args:
            silence_chunks: Consecutive silent chunks counted.
            max_silence_chunks: Maximum allowed silent chunks.
            total_frames: Total frames recorded so far.

        Returns:
            True if recording should stop.
        """
        return silence_chunks >= max_silence_chunks and total_frames > max_silence_chunks

    async def _capture_fixed_duration(self, duration_s: float) -> list[np.ndarray]:
        """Capture audio for a fixed duration (push-to-talk mode).

        Args:
            duration_s: Duration to record in seconds.

        Returns:
            List of audio frame arrays.
        """
        frames: list[np.ndarray] = []
        chunks_needed = int(duration_s * 1000 / CHUNK_DURATION_MS)

        for _ in range(chunks_needed):
            chunk = await self._read_audio_chunk()
            if chunk is None:
                break
            frames.append(chunk)

        return frames

    def _detect_speech(self, chunk: np.ndarray) -> bool:
        """Determine if an audio chunk contains speech.

        Uses Silero VAD if available, otherwise falls back to
        simple energy-based detection.

        Args:
            chunk: Audio frame (int16 numpy array).

        Returns:
            True if speech is detected in the chunk.
        """
        if self._vad_model is not None:
            return self._silero_vad(chunk)
        return self._energy_vad(chunk)

    def _silero_vad(self, chunk: np.ndarray) -> bool:
        """Run Silero VAD model on an audio chunk.

        Args:
            chunk: Audio frame (int16 numpy array).

        Returns:
            True if speech is detected.
        """
        try:
            # deps-lazy-load: torch only needed for Silero VAD
            import torch

            audio_float = chunk.flatten().astype(np.float32) / 32768.0
            audio_tensor = torch.from_numpy(audio_float)
            confidence = self._vad_model(audio_tensor, SAMPLE_RATE).item()
            return confidence > VAD_SPEECH_THRESHOLD
        except (RuntimeError, ValueError, OSError):
            logger.debug("VAD inference error — falling back to energy detection")
            return self._energy_vad(chunk)

    @staticmethod
    def _energy_vad(chunk: np.ndarray) -> bool:
        """Simple energy-based Voice Activity Detection fallback.

        Args:
            chunk: Audio frame (int16 numpy array).

        Returns:
            True if RMS energy exceeds threshold.
        """
        rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
        return float(rms) > ENERGY_VAD_THRESHOLD

    # ── Internal: Audio Conversion ────────────────

    @staticmethod
    def _frames_to_wav(frames: list[np.ndarray]) -> bytes:
        """Convert a list of audio frames to WAV bytes.

        Args:
            frames: List of int16 numpy arrays.

        Returns:
            WAV file content as bytes.
        """
        audio = np.concatenate(frames, axis=0).flatten()
        buffer = io.BytesIO()

        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(CHANNELS)
            wav_file.setsampwidth(2)  # 16-bit = 2 bytes
            wav_file.setframerate(SAMPLE_RATE)
            wav_file.writeframes(audio.tobytes())

        return buffer.getvalue()
