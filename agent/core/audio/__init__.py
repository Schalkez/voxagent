"""Audio sub-package: components for the Ears voice pipeline.

Each module has a single responsibility:
- recorder: Microphone stream management
- ring_buffer: Bounded circular buffer with drop-oldest policy
- normalizer: Validate/convert audio to int16/16kHz/mono
- interrupt_controller: Shared cancellation primitive for barge-in
- converter: Audio frame → WAV conversion
- wake_word: Wake word detection (OpenWakeWord)
- vad: Voice Activity Detection (Silero VAD + energy fallback)
"""

from core.audio.converter import AudioConverter
from core.audio.interrupt_controller import InterruptController
from core.audio.normalizer import AudioNormalizer
from core.audio.recorder import AudioRecorder
from core.audio.ring_buffer import AudioRingBuffer
from core.audio.vad import VoiceActivityDetector
from core.audio.wake_word import WakeWordDetector

__all__ = [
    "AudioConverter",
    "AudioNormalizer",
    "AudioRecorder",
    "AudioRingBuffer",
    "InterruptController",
    "VoiceActivityDetector",
    "WakeWordDetector",
]
