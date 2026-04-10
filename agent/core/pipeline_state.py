"""Pipeline state machine for VoxAgent voice pipeline.

Enforces valid transitions between pipeline states (BGIN-04).
Prevents race conditions by using a threading lock and logs
all transitions + rejected violations via structlog.

States:
    LISTENING    -> PROCESSING
    PROCESSING   -> SPEAKING
    SPEAKING     -> INTERRUPTED | LISTENING
    INTERRUPTED  -> LISTENING
"""

from __future__ import annotations

import threading
import time
from enum import Enum, auto

from core.logging import get_logger

logger = get_logger(module="pipeline_state")

# ── Constants ────────────────────────────────────────────────────────────────

# Valid state transitions: source -> set of allowed targets
_VALID_TRANSITIONS: dict[PipelineState, frozenset[PipelineState]] = {}


class PipelineState(Enum):
    """Pipeline state for the EARS->BRAIN->HANDS->MOUTH loop.

    Attributes:
        LISTENING: Waiting for wake word / recording speech.
        PROCESSING: Brain + Hands executing a command.
        SPEAKING: Mouth is playing TTS audio.
        INTERRUPTED: Barge-in detected; TTS stopped, transitioning.
    """

    LISTENING = auto()
    PROCESSING = auto()
    SPEAKING = auto()
    INTERRUPTED = auto()


# Populate after enum is defined
_VALID_TRANSITIONS.update(
    {
        PipelineState.LISTENING: frozenset({PipelineState.PROCESSING}),
        PipelineState.PROCESSING: frozenset({PipelineState.SPEAKING, PipelineState.LISTENING}),
        PipelineState.SPEAKING: frozenset(
            {PipelineState.INTERRUPTED, PipelineState.LISTENING}
        ),
        PipelineState.INTERRUPTED: frozenset({PipelineState.LISTENING}),
    }
)


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted.

    Attributes:
        from_state: The current state.
        to_state: The rejected target state.
    """

    def __init__(self, from_state: PipelineState, to_state: PipelineState) -> None:
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid transition: {from_state.name} -> {to_state.name}")


class PipelineStateMachine:
    """Thread-safe state machine for the voice pipeline.

    Enforces that only valid transitions occur. Invalid transitions
    are rejected and logged as violations — never silently ignored.

    Usage::

        sm = PipelineStateMachine()
        sm.transition_to(PipelineState.PROCESSING)
        sm.transition_to(PipelineState.SPEAKING)
        sm.transition_to(PipelineState.INTERRUPTED)  # barge-in
        sm.transition_to(PipelineState.LISTENING)     # reset

    Thread safety: all state reads/writes are protected by a
    threading.Lock so the sounddevice callback thread can safely
    query ``current_state`` while the asyncio loop transitions.
    """

    def __init__(self, initial: PipelineState = PipelineState.LISTENING) -> None:
        """Initialize the state machine.

        Args:
            initial: Starting state. Defaults to LISTENING.
        """
        self._state = initial
        self._lock = threading.Lock()
        self._last_transition_time: float = time.monotonic()
        logger.info("pipeline state machine initialized", state=initial.name)

    @property
    def current_state(self) -> PipelineState:
        """Return the current pipeline state (thread-safe read)."""
        with self._lock:
            return self._state

    @property
    def is_speaking(self) -> bool:
        """Whether the pipeline is currently in SPEAKING state."""
        return self.current_state == PipelineState.SPEAKING

    @property
    def is_listening(self) -> bool:
        """Whether the pipeline is currently in LISTENING state."""
        return self.current_state == PipelineState.LISTENING

    def transition_to(self, target: PipelineState) -> bool:
        """Attempt a state transition.

        If the transition is valid, the state is updated and logged.
        If invalid, the transition is rejected, a violation is logged,
        and False is returned (no exception raised in normal usage).

        Args:
            target: The desired next state.

        Returns:
            True if the transition succeeded, False if rejected.
        """
        with self._lock:
            allowed = _VALID_TRANSITIONS.get(self._state, frozenset())
            if target not in allowed:
                logger.warning(
                    "invalid state transition rejected",
                    from_state=self._state.name,
                    to_state=target.name,
                    allowed=[s.name for s in allowed],
                )
                return False

            previous = self._state
            now = time.monotonic()
            elapsed_ms = int((now - self._last_transition_time) * 1000)

            self._state = target
            self._last_transition_time = now

            logger.info(
                "pipeline state transition",
                from_state=previous.name,
                to_state=target.name,
                elapsed_ms=elapsed_ms,
            )
            return True

    def force_reset(self) -> None:
        """Force the state machine back to LISTENING.

        Use only for error recovery — bypasses transition validation.
        Logs the forced reset as a warning.
        """
        with self._lock:
            previous = self._state
            self._state = PipelineState.LISTENING
            self._last_transition_time = time.monotonic()
            logger.warning(
                "pipeline state force-reset to LISTENING",
                from_state=previous.name,
            )
