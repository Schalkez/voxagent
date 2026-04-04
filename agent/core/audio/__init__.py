"""Audio sub-package: components for the Ears voice pipeline.

Each module has a single responsibility:
- recorder: Microphone stream management
- converter: Audio frame → WAV conversion
- wake_word: Wake word detection (OpenWakeWord)
- vad: Voice Activity Detection (Silero VAD + energy fallback)
"""

from core.audio.converter import AudioConverter
from core.audio.recorder import AudioRecorder
from core.audio.vad import VoiceActivityDetector
from core.audio.wake_word import WakeWordDetector

__all__ = [
    "AudioConverter",
    "AudioRecorder",
    "VoiceActivityDetector",
    "WakeWordDetector",
]
