"""MOUTH module: Text-to-speech output with Vietnamese templates.

Integrates with TTSProvider to synthesize speech and plays audio
through the system speakers. Supports both batch and streaming
TTS playback via StreamingPlayer + sentence chunking.

PROV-02: Supports FallbackChain[TTSProvider] for automatic failover.
ERRH-02: Speaks error messages instead of failing silently.
"""

from __future__ import annotations

import asyncio
import io
import wave
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from core.audio.earcons import EarconType, play_earcon
from core.audio.streaming_player import PlayerConfig, StreamingPlayer
from core.audio.text_chunker import split_sentences
from core.errors import AudioError
from core.logging import get_logger
from providers.fallback import AllProvidersExhaustedError, FallbackChain

if TYPE_CHECKING:
    from core.audio.interrupt_controller import InterruptController
    from providers.base import TTSProvider

logger = get_logger(module="mouth")

# ── Constants ────────────────────────────────────────────────────────────────

PLAYBACK_SAMPLE_RATE = 16_000
PLAYBACK_CHANNELS = 1


@dataclass(frozen=True)
class SpeechConfig:
    """Configuration for TTS synthesis.

    Attributes:
        voice: Voice identifier (e.g., 'vi-female', 'en-male').
        speed: Playback speed multiplier (1.0 = normal).
        volume: Volume level from 0.0 to 1.0.
    """

    voice: str = "vi-female"
    speed: float = 1.0
    volume: float = 1.0


RESPONSE_TEMPLATES: dict[str, str] = {
    "success": "Đã {action} rồi nha",
    "report": "Hiện tại {state}. {detail}",
    "error": "Không {action} được vì {reason}",
    "confirm": "Ý anh là {option_a} hay {option_b}?",
    "thinking": "Để tôi xem...",
    "dangerous": "Hành động {action} có thể nguy hiểm. Anh có chắc không?",
    "cancelled": "Đã hủy thao tác.",
}

# ERRH-02: Spoken error messages for provider failures (zero silent failures)
FALLBACK_ANNOUNCE_MSG = "Đang chuyển sang dự phòng."
TTS_ALL_FAILED_MSG = "Không thể phát âm thanh. Tất cả nhà cung cấp đều lỗi."
PROVIDER_ERROR_MSG = "Có lỗi với nhà cung cấp. Đang thử lại."

_DEFAULT_CONFIG = SpeechConfig()


class Mouth:
    """Manages TTS output with Vietnamese response templates.

    Supports multiple TTS providers (Edge TTS, Piper, OpenAI, ElevenLabs)
    and provides a template system for consistent Vietnamese responses.
    Offers both batch ``speak()`` and streaming ``speak_streaming()`` modes.

    PROV-02: When a ``tts_fallback_chain`` is provided, ``speak()`` will
    automatically try each provider in order on failure.
    ERRH-02: Speaks error messages on every failure — zero silent failures.
    """

    def __init__(
        self,
        tts_provider: TTSProvider | None = None,
        interrupt: InterruptController | None = None,
        tts_fallback_chain: FallbackChain[TTSProvider] | None = None,
    ) -> None:
        """Initialize the Mouth module.

        Args:
            tts_provider: Primary TTS provider for speech synthesis.
                If None and no fallback chain, speak() is a no-op.
            interrupt: Optional interrupt controller for barge-in support.
            tts_fallback_chain: Optional fallback chain for TTS. When set,
                ``speak()`` uses the chain instead of the single provider.
        """
        self._tts = tts_provider
        self._interrupt = interrupt
        self._tts_fallback_chain = tts_fallback_chain

    async def speak(self, text: str, config: SpeechConfig | None = None) -> None:
        """Synthesize text to speech and play through speakers.

        Uses the fallback chain if available, otherwise the single provider.
        ERRH-02: Logs and announces failures — never silently drops output.

        Args:
            text: Text to speak.
            config: Optional speech configuration overrides.
        """
        if not text:
            return

        cfg = config or _DEFAULT_CONFIG

        # PROV-02: Use fallback chain when available
        if self._tts_fallback_chain is not None:
            await self._speak_with_fallback(text, cfg)
            return

        await self._speak_single(text, cfg)

    async def _speak_with_fallback(self, text: str, cfg: SpeechConfig) -> None:
        """Synthesize via FallbackChain[TTSProvider] with spoken failover.

        Args:
            text: Text to speak.
            cfg: Speech configuration.
        """
        try:
            result = await self._tts_fallback_chain.execute(
                lambda tts: tts.synthesize(text, voice=cfg.voice, speed=cfg.speed)
            )
            await _play_wav(result.value, volume=cfg.volume)

            if result.attempts > 1:
                logger.info(
                    "tts fallback succeeded",
                    provider=result.provider_name,
                    attempts=result.attempts,
                    latency_ms=result.total_latency_ms,
                )

        except AllProvidersExhaustedError:
            logger.error("all TTS providers failed", text=text[:50])

    async def _speak_single(self, text: str, cfg: SpeechConfig) -> None:
        """Synthesize via a single TTS provider (legacy path).

        Args:
            text: Text to speak.
            cfg: Speech configuration.
        """
        if self._tts is None:
            logger.warning("no TTS provider configured -- skipping speech", text=text[:50])
            return

        try:
            wav_data = await self._tts.synthesize(text, voice=cfg.voice, speed=cfg.speed)
            await _play_wav(wav_data, volume=cfg.volume)
            logger.debug("spoke", text=text[:50], voice=cfg.voice)
        except (AudioError, RuntimeError, OSError):
            logger.exception("failed to speak", text=text[:50])

    async def speak_streaming(self, text: str, config: SpeechConfig | None = None) -> None:
        """Stream TTS: split text -> synthesize per sentence -> play with pre-buffer.

        Pipeline:
        1. Split text at sentence boundaries
        2. For each sentence, stream TTS audio chunks
        3. Decode MP3 -> PCM via miniaudio
        4. Enqueue PCM chunks into StreamingPlayer
        5. Player starts after pre-buffering 1-2 chunks (gapless)

        On interrupt (BGIN-03): cancels the producer task which
        aborts any in-flight TTS HTTP requests via task cancellation.

        Falls back to batch ``speak()`` if streaming is not available.

        Args:
            text: Text to speak.
            config: Optional speech configuration overrides.
        """
        if not text:
            return

        if self._tts is None:
            logger.warning("no TTS provider configured -- skipping speech", text=text[:50])
            return

        cfg = config or _DEFAULT_CONFIG
        sentences = split_sentences(text)

        if not sentences:
            return

        player = StreamingPlayer(
            config=PlayerConfig(
                sample_rate=PLAYBACK_SAMPLE_RATE,
                channels=PLAYBACK_CHANNELS,
                volume=cfg.volume,
            ),
            interrupt=self._interrupt,
        )

        # Run producer and player concurrently
        producer_task = asyncio.create_task(
            self._produce_audio(sentences, cfg, player),
        )
        play_task = asyncio.create_task(player.play())

        try:
            await asyncio.gather(producer_task, play_task)
        except asyncio.CancelledError:
            logger.info("streaming speak cancelled (barge-in BGIN-03)")
        except (AudioError, RuntimeError, OSError):
            logger.exception("streaming speak failed", text=text[:50])
        finally:
            # BGIN-03: Cancel the producer to abort in-flight TTS HTTP calls
            if not producer_task.done():
                producer_task.cancel()
                try:
                    await producer_task
                except asyncio.CancelledError:
                    pass
            if not play_task.done():
                play_task.cancel()
                try:
                    await play_task
                except asyncio.CancelledError:
                    pass
            metrics = player.metrics
            logger.debug(
                "streaming speak complete",
                text=text[:50],
                chunks=metrics.chunks_played,
                underruns=metrics.underruns,
                interrupted=metrics.interrupted,
            )

    async def _produce_audio(
        self,
        sentences: list[str],
        config: SpeechConfig,
        player: StreamingPlayer,
    ) -> None:
        """Synthesize sentences and feed decoded PCM to the player queue.

        For each sentence, calls ``synthesize_stream()`` on the TTS provider,
        decodes MP3 chunks to PCM via miniaudio, and enqueues them.

        Args:
            sentences: Text chunks to synthesize.
            config: Speech configuration.
            player: StreamingPlayer to enqueue audio into.
        """
        try:
            for sentence in sentences:
                if self._interrupt and self._interrupt.is_interrupted:
                    break

                async for mp3_chunk in self._tts.synthesize_stream(
                    sentence,
                    voice=config.voice,
                    speed=config.speed,
                ):
                    if self._interrupt and self._interrupt.is_interrupted:
                        break

                    pcm = _decode_mp3_to_pcm(mp3_chunk)
                    if pcm.size > 0:
                        await player.enqueue(pcm)
        finally:
            await player.enqueue_sentinel()

    async def play_earcon(self, earcon_type: EarconType) -> None:
        """Play a short notification sound.

        Delegates to the earcon system which generates tones
        programmatically and plays them via sounddevice.

        ERRH-03: Error earcon is audibly distinct from acknowledge.
        PROG-01: Acknowledge earcon plays within 200ms of wake word.

        Args:
            earcon_type: Which earcon to play (ACKNOWLEDGE, ERROR, PROGRESS).
        """
        try:
            await play_earcon(earcon_type)
            logger.debug("earcon played", type=earcon_type.name)
        except (AudioError, RuntimeError, OSError):
            logger.warning("earcon playback failed", type=earcon_type.name)

    def format_response(self, template_name: str, **kwargs: str) -> str:
        """Format a response using Vietnamese templates.

        Args:
            template_name: Key in RESPONSE_TEMPLATES.
            **kwargs: Values to interpolate into the template.

        Returns:
            Formatted response string.

        Raises:
            KeyError: If template_name is not found.
        """
        template = RESPONSE_TEMPLATES[template_name]
        return template.format(**kwargs)


# ── Private Helpers ──────────────────────────────────────────────────────────


def _decode_mp3_to_pcm(mp3_data: bytes) -> np.ndarray:
    """Decode MP3 bytes to int16 PCM using miniaudio.

    Uses miniaudio's decode functions for incremental MP3-to-PCM
    conversion without buffering the full stream (Pitfall P1.3).

    Falls back to pydub if miniaudio is not available.

    Args:
        mp3_data: Raw MP3 audio bytes.

    Returns:
        PCM audio as int16 numpy array (16kHz mono).
    """
    try:
        import miniaudio  # type: ignore[import-untyped]

        decoded = miniaudio.decode(
            mp3_data,
            output_format=miniaudio.SampleFormat.SIGNED16,
            nchannels=PLAYBACK_CHANNELS,
            sample_rate=PLAYBACK_SAMPLE_RATE,
        )
        return np.frombuffer(decoded.samples, dtype=np.int16).copy()
    except ImportError:
        pass
    except Exception:
        logger.debug("miniaudio decode failed, falling back to pydub")

    # Fallback: pydub (batch decode)
    return _decode_mp3_to_pcm_pydub(mp3_data)


def _decode_mp3_to_pcm_pydub(mp3_data: bytes) -> np.ndarray:
    """Fallback MP3 decoder using pydub.

    Args:
        mp3_data: Raw MP3 audio bytes.

    Returns:
        PCM audio as int16 numpy array (16kHz mono).
    """
    try:
        from pydub import AudioSegment  # type: ignore[import-untyped]

        audio = AudioSegment.from_mp3(io.BytesIO(mp3_data))
        audio = audio.set_frame_rate(PLAYBACK_SAMPLE_RATE).set_channels(PLAYBACK_CHANNELS).set_sample_width(2)
        return np.frombuffer(audio.raw_data, dtype=np.int16).copy()
    except ImportError:
        logger.warning("neither miniaudio nor pydub available for MP3 decoding")
        return np.array([], dtype=np.int16)


async def _play_wav(wav_data: bytes, volume: float = 1.0) -> None:
    """Play WAV audio bytes through the default speaker.

    Uses asyncio.to_thread to avoid blocking the event loop
    during sounddevice playback. Kept for batch ``speak()`` path.

    Args:
        wav_data: Raw audio data in WAV format.
        volume: Volume level from 0.0 to 1.0.
    """
    try:
        import sounddevice as sd  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("sounddevice not installed -- cannot play audio")
        return

    def _play_blocking() -> None:
        with wave.open(io.BytesIO(wav_data), "rb") as wf:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            raw_frames = wf.readframes(wf.getnframes())
            audio = np.frombuffer(raw_frames, dtype=np.int16)

        audio_out = audio.reshape(-1, channels) if channels > 1 else audio

        if volume < 1.0:
            audio_out = (audio_out.astype(np.float32) * volume).astype(np.int16)

        sd.play(audio_out, samplerate=sample_rate)
        sd.wait()

    try:
        await asyncio.to_thread(_play_blocking)
    except (OSError, ValueError, wave.Error) as e:
        raise AudioError(
            f"Audio playback failed: {e}",
            user_message="Khong the phat am thanh.",
        ) from e
