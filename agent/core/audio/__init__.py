"""Audio sub-package: components for the Ears voice pipeline.

Each module has a single responsibility:
- recorder: Microphone stream management
- ring_buffer: Bounded circular buffer with drop-oldest policy
- normalizer: Validate/convert audio to int16/16kHz/mono
- interrupt_controller: Shared cancellation primitive for barge-in
- converter: Audio frame -> WAV conversion
- wake_word: Wake word detection (OpenWakeWord)
- vad: Voice Activity Detection (Silero VAD + energy fallback)
- adaptive_vad: Ambient-aware VAD with hysteresis (AUDR-02, AUDR-03)
- text_chunker: Sentence-level text splitting for streaming TTS
- streaming_player: Gapless audio playback from asyncio.Queue
- earcons: Programmatic audio feedback tones (ERRH-03, PROG-01)
"""

from core.audio.adaptive_vad import AdaptiveVAD, AdaptiveVADConfig
from core.audio.converter import AudioConverter
from core.audio.earcons import EarconType, play_earcon
from core.audio.interrupt_controller import InterruptController
from core.audio.normalizer import AudioNormalizer
from core.audio.recorder import AudioRecorder
from core.audio.ring_buffer import AudioRingBuffer
from core.audio.streaming_player import StreamingPlayer
from core.audio.text_chunker import split_sentences
from core.audio.vad import VoiceActivityDetector
from core.audio.wake_word import WakeWordDetector

__all__ = [
    "AdaptiveVAD",
    "AdaptiveVADConfig",
    "AudioConverter",
    "AudioNormalizer",
    "AudioRecorder",
    "AudioRingBuffer",
    "EarconType",
    "InterruptController",
    "StreamingPlayer",
    "VoiceActivityDetector",
    "WakeWordDetector",
    "play_earcon",
    "split_sentences",
]
