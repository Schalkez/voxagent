"""StreamingPlayer: Gapless audio playback from an asyncio.Queue.

Uses ``sounddevice.OutputStream`` with a callback that pulls PCM
chunks from a thread-safe queue. Supports pre-buffering (start
playback after N chunks arrive) and interrupt via InterruptController.

Design note (Pitfall P1.1): This replaces ``sd.play() + sd.wait()``
to enable true streaming — audio plays while the next chunk synthesizes.
"""

from __future__ import annotations

import asyncio
import queue
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from core.errors import AudioError
from core.logging import get_logger

if TYPE_CHECKING:
    from core.audio.interrupt_controller import InterruptController

logger = get_logger(module="streaming_player")

# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_SAMPLE_RATE = 16_000
DEFAULT_CHANNELS = 1
DEFAULT_BLOCKSIZE = 1024
PRE_BUFFER_CHUNKS = 2
QUEUE_MAX_SIZE = 10
SENTINEL = None  # Signals end of stream


@dataclass
class PlaybackMetrics:
    """Runtime metrics for a streaming playback session.

    Attributes:
        chunks_played: Number of audio chunks played.
        underruns: Times the callback had no data (output silence).
        interrupted: Whether playback was interrupted.
    """

    chunks_played: int = 0
    underruns: int = 0
    interrupted: bool = False


@dataclass
class PlayerConfig:
    """Configuration for StreamingPlayer.

    Attributes:
        sample_rate: Audio sample rate in Hz.
        channels: Number of audio channels.
        blocksize: Frames per callback invocation.
        pre_buffer_chunks: Chunks to buffer before starting playback.
        volume: Playback volume from 0.0 to 1.0.
    """

    sample_rate: int = DEFAULT_SAMPLE_RATE
    channels: int = DEFAULT_CHANNELS
    blocksize: int = DEFAULT_BLOCKSIZE
    pre_buffer_chunks: int = PRE_BUFFER_CHUNKS
    volume: float = 1.0


class StreamingPlayer:
    """Plays audio chunks from an async producer via sd.OutputStream.

    The producer enqueues ``np.ndarray`` (int16) chunks. The player's
    sounddevice callback dequeues and writes them to the output buffer.
    A sentinel (None) signals end-of-stream.

    Thread safety: The internal queue bridges the asyncio world
    (producer) and the PortAudio C-thread (callback consumer).
    ``queue.Queue`` (not ``asyncio.Queue``) is used because the
    callback cannot await.
    """

    def __init__(
        self,
        config: PlayerConfig | None = None,
        interrupt: InterruptController | None = None,
    ) -> None:
        """Initialize the streaming player.

        Args:
            config: Playback configuration. Defaults to 16kHz mono.
            interrupt: Optional interrupt controller for barge-in.
        """
        self._config = config or PlayerConfig()
        self._interrupt = interrupt
        self._chunk_queue: queue.Queue[np.ndarray | None] = queue.Queue(
            maxsize=QUEUE_MAX_SIZE,
        )
        self._metrics = PlaybackMetrics()
        self._remainder: np.ndarray = np.array([], dtype=np.int16)
        self._started = threading.Event()
        self._finished = asyncio.Event()

    @property
    def metrics(self) -> PlaybackMetrics:
        """Return playback metrics for the current session."""
        return self._metrics

    async def enqueue(self, chunk: np.ndarray) -> None:
        """Add an audio chunk to the playback queue.

        Runs ``put`` in a thread to avoid blocking the event loop
        if the queue is full.

        Args:
            chunk: PCM audio as int16 numpy array.
        """
        await asyncio.to_thread(self._chunk_queue.put, chunk)

    async def enqueue_sentinel(self) -> None:
        """Signal that no more chunks will be enqueued."""
        await asyncio.to_thread(self._chunk_queue.put, SENTINEL)

    async def play(self) -> PlaybackMetrics:
        """Pre-buffer then play all enqueued audio until sentinel or interrupt.

        Blocks (async) until playback completes or is interrupted.

        Returns:
            Playback metrics for this session.

        Raises:
            AudioError: If sounddevice is not available.
        """
        try:
            import sounddevice as sd  # type: ignore[import-untyped]
        except ImportError as exc:
            raise AudioError(
                "sounddevice not installed",
                user_message="Khong the phat am thanh.",
            ) from exc

        self._metrics = PlaybackMetrics()
        self._remainder = np.array([], dtype=np.int16)
        self._finished.clear()

        # Pre-buffer: wait for N chunks before opening the stream
        await self._pre_buffer()

        stream = sd.OutputStream(
            samplerate=self._config.sample_rate,
            channels=self._config.channels,
            dtype="int16",
            blocksize=self._config.blocksize,
            callback=self._audio_callback,
            finished_callback=self._on_stream_finished,
        )

        try:
            stream.start()
            self._started.set()
            logger.debug(
                "playback started",
                sample_rate=self._config.sample_rate,
                pre_buffered=self._chunk_queue.qsize(),
            )

            # Wait for stream to finish or interrupt
            await self._wait_for_completion()
        finally:
            stream.stop()
            stream.close()
            self._drain_queue()
            self._started.clear()
            logger.debug("playback stopped", metrics=self._metrics)

        return self._metrics

    def _audio_callback(
        self,
        outdata: np.ndarray,
        frames: int,
        time_info: object,
        status: object,
    ) -> None:
        """Sounddevice OutputStream callback — runs on PortAudio C-thread.

        Pulls audio from the chunk queue and writes to ``outdata``.
        MUST NOT block, allocate large memory, or raise exceptions.

        Args:
            outdata: Output buffer to fill (int16, shape: [frames, channels]).
            frames: Number of frames requested.
            time_info: PortAudio time info (unused).
            status: PortAudio status flags (unused).
        """
        # Check interrupt
        if self._interrupt and self._interrupt.is_interrupted:
            outdata[:] = 0
            self._metrics.interrupted = True
            raise _StopCallback

        needed = frames * self._config.channels
        collected = self._remainder.copy() if len(self._remainder) > 0 else np.array([], dtype=np.int16)

        while len(collected) < needed:
            try:
                chunk = self._chunk_queue.get_nowait()
            except queue.Empty:
                break

            if chunk is SENTINEL:
                # End of stream — pad with silence and signal stop
                break

            collected = np.concatenate([collected, chunk.ravel()])
            self._metrics.chunks_played += 1

        if len(collected) == 0:
            # Complete underrun — output silence
            outdata[:] = 0
            self._metrics.underruns += 1
            # If queue is also empty and sentinel was received, stop
            if self._chunk_queue.empty():
                raise _StopCallback
            return

        # Apply volume
        if self._config.volume < 1.0:
            collected = (collected.astype(np.float32) * self._config.volume).astype(np.int16)

        if len(collected) >= needed:
            outdata[:, 0] = collected[:needed] if self._config.channels == 1 else collected[:needed]
            self._remainder = collected[needed:]
        else:
            # Partial fill — pad with silence
            outdata[:, 0] = 0
            outdata[: len(collected), 0] = collected
            self._remainder = np.array([], dtype=np.int16)

    def _on_stream_finished(self) -> None:
        """Called by sounddevice when the stream stops."""
        self._finished.set()

    async def _pre_buffer(self) -> None:
        """Wait until pre_buffer_chunks are available in the queue.

        Polls the queue with short sleeps to avoid blocking. Returns
        early if a sentinel arrives during pre-buffering.
        """
        target = self._config.pre_buffer_chunks
        poll_interval = 0.01  # 10ms

        while self._chunk_queue.qsize() < target:
            # Check if interrupted before we even start
            if self._interrupt and self._interrupt.is_interrupted:
                return
            await asyncio.sleep(poll_interval)

            # Peek: if the queue has a sentinel, don't wait for more
            # (short response may have fewer chunks than pre-buffer target)
            # We can't peek a queue.Queue, so check if qsize > 0 and break
            # if we've waited a reasonable time
            if self._chunk_queue.qsize() > 0:
                # At least one chunk — start after a brief extra wait
                # to allow a second chunk to arrive if it's close behind
                await asyncio.sleep(poll_interval)
                break

        logger.debug("pre-buffer complete", queued=self._chunk_queue.qsize())

    async def _wait_for_completion(self) -> None:
        """Wait for playback to finish or interrupt to fire."""
        if self._interrupt:
            interrupt_task = asyncio.create_task(self._interrupt.wait_for_interrupt())
            finish_task = asyncio.create_task(self._finished.wait())

            done, pending = await asyncio.wait(
                {interrupt_task, finish_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

            if interrupt_task in done:
                self._metrics.interrupted = True
                logger.info("playback interrupted")
        else:
            await self._finished.wait()

    def _drain_queue(self) -> None:
        """Remove all remaining items from the chunk queue."""
        while not self._chunk_queue.empty():
            try:
                self._chunk_queue.get_nowait()
            except queue.Empty:
                break


class _StopCallback(Exception):
    """Raised inside the audio callback to signal sounddevice to stop the stream.

    sounddevice treats any exception from the callback as a stop signal.
    This is the documented mechanism — not an error.
    """
