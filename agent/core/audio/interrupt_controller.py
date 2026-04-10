"""InterruptController: Shared cancellation primitive for barge-in.

Single responsibility: coordinate interruption across producer (TTS)
and consumer (playback) via an asyncio.Event. Skeleton for Phase 6.
"""

from __future__ import annotations

import asyncio

from core.logging import get_logger

logger = get_logger(module="interrupt_controller")


class InterruptController:
    """Asyncio.Event-based cancellation controller for barge-in.

    When ``interrupt()`` is called, all coroutines awaiting
    ``wait_for_interrupt()`` wake up and the ``is_interrupted``
    flag becomes True. Components should check this flag before
    each unit of work (e.g., before playing the next TTS chunk).

    Thread-safe: ``interrupt()`` can be called from any thread
    via ``call_soon_threadsafe``.
    """

    def __init__(self) -> None:
        self._event = asyncio.Event()

    @property
    def is_interrupted(self) -> bool:
        """Whether an interrupt has been signalled."""
        return self._event.is_set()

    def interrupt(self) -> None:
        """Signal all listeners to stop. Idempotent.

        Safe to call from the sounddevice callback thread via
        ``loop.call_soon_threadsafe(controller.interrupt)``.
        """
        if not self._event.is_set():
            logger.info("interrupt signalled")
        self._event.set()

    def reset(self) -> None:
        """Clear the interrupt flag. Call after handling the interrupt."""
        self._event.clear()

    async def wait_for_interrupt(self) -> None:
        """Block until ``interrupt()`` is called.

        Use with ``asyncio.wait`` or ``asyncio.gather`` to race
        against other coroutines.
        """
        await self._event.wait()
