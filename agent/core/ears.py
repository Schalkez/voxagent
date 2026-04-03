"""EARS module: Wake word detection + STT transcription.

Pipeline: Mic → Wake Word Detector → VAD → STT → Raw text
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TranscribeResult:
    """Result from speech-to-text transcription.

    Attributes:
        text: The transcribed text content.
        confidence: Confidence score between 0.0 and 1.0.
        language: Detected language code (e.g., 'vi', 'en').
        duration_ms: Duration of the audio segment in milliseconds.
    """

    text: str
    confidence: float
    language: str
    duration_ms: int


class Ears:
    """Manages the voice input pipeline.

    Handles wake word detection (openWakeWord), Voice Activity Detection
    (Silero VAD), and Speech-to-Text transcription (Whisper/cloud APIs).
    """

    def __init__(self) -> None:
        """Initialize the EARS module with default configuration."""
        self._listening = False

    async def start_listening(self) -> None:
        """Start microphone capture and wake word detection.

        Opens an audio stream and begins monitoring for the wake word
        "Hey Vox". Uses approximately 2% CPU when idle.
        """
        self._listening = True

    async def stop_listening(self) -> None:
        """Stop listening and release audio resources.

        Closes the audio stream and frees microphone access.
        """
        self._listening = False

    async def wait_for_command(self) -> TranscribeResult:
        """Block until wake word detected, then transcribe speech.

        Waits for "Hey Vox" wake word, plays confirmation beep,
        captures speech until silence detected by VAD, then
        transcribes using the configured STT provider.

        Returns:
            TranscribeResult with the transcribed text and metadata.
        """
        # Placeholder — will be implemented with actual audio pipeline
        return TranscribeResult(
            text="",
            confidence=0.0,
            language="vi",
            duration_ms=0,
        )
