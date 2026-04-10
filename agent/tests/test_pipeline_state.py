"""Tests for PipelineStateMachine (BGIN-04).

Verifies state transition enforcement, invalid transition rejection,
thread safety, and force_reset behavior.
"""

from __future__ import annotations

import threading

import pytest

from core.pipeline_state import (
    PipelineState,
    PipelineStateMachine,
)


class TestPipelineStateMachine:
    """Test the pipeline state machine transitions."""

    def test_initial_state_is_listening(self) -> None:
        """State machine starts in LISTENING."""
        sm = PipelineStateMachine()
        assert sm.current_state == PipelineState.LISTENING

    def test_custom_initial_state(self) -> None:
        """Can start with a custom initial state."""
        sm = PipelineStateMachine(initial=PipelineState.PROCESSING)
        assert sm.current_state == PipelineState.PROCESSING

    def test_valid_transition_listening_to_processing(self) -> None:
        """LISTENING -> PROCESSING is valid."""
        sm = PipelineStateMachine()
        assert sm.transition_to(PipelineState.PROCESSING) is True
        assert sm.current_state == PipelineState.PROCESSING

    def test_valid_transition_processing_to_speaking(self) -> None:
        """PROCESSING -> SPEAKING is valid."""
        sm = PipelineStateMachine()
        sm.transition_to(PipelineState.PROCESSING)
        assert sm.transition_to(PipelineState.SPEAKING) is True
        assert sm.current_state == PipelineState.SPEAKING

    def test_valid_transition_speaking_to_interrupted(self) -> None:
        """SPEAKING -> INTERRUPTED is valid (barge-in)."""
        sm = PipelineStateMachine()
        sm.transition_to(PipelineState.PROCESSING)
        sm.transition_to(PipelineState.SPEAKING)
        assert sm.transition_to(PipelineState.INTERRUPTED) is True
        assert sm.current_state == PipelineState.INTERRUPTED

    def test_valid_transition_interrupted_to_listening(self) -> None:
        """INTERRUPTED -> LISTENING is valid (reset after barge-in)."""
        sm = PipelineStateMachine()
        sm.transition_to(PipelineState.PROCESSING)
        sm.transition_to(PipelineState.SPEAKING)
        sm.transition_to(PipelineState.INTERRUPTED)
        assert sm.transition_to(PipelineState.LISTENING) is True
        assert sm.current_state == PipelineState.LISTENING

    def test_valid_transition_speaking_to_listening(self) -> None:
        """SPEAKING -> LISTENING is valid (normal TTS completion)."""
        sm = PipelineStateMachine()
        sm.transition_to(PipelineState.PROCESSING)
        sm.transition_to(PipelineState.SPEAKING)
        assert sm.transition_to(PipelineState.LISTENING) is True
        assert sm.current_state == PipelineState.LISTENING

    def test_valid_transition_processing_to_listening(self) -> None:
        """PROCESSING -> LISTENING is valid (no TTS needed)."""
        sm = PipelineStateMachine()
        sm.transition_to(PipelineState.PROCESSING)
        assert sm.transition_to(PipelineState.LISTENING) is True
        assert sm.current_state == PipelineState.LISTENING

    def test_invalid_transition_listening_to_speaking(self) -> None:
        """LISTENING -> SPEAKING is invalid (must go through PROCESSING)."""
        sm = PipelineStateMachine()
        assert sm.transition_to(PipelineState.SPEAKING) is False
        assert sm.current_state == PipelineState.LISTENING

    def test_invalid_transition_speaking_to_processing(self) -> None:
        """SPEAKING -> PROCESSING is invalid."""
        sm = PipelineStateMachine()
        sm.transition_to(PipelineState.PROCESSING)
        sm.transition_to(PipelineState.SPEAKING)
        assert sm.transition_to(PipelineState.PROCESSING) is False
        assert sm.current_state == PipelineState.SPEAKING

    def test_invalid_transition_listening_to_interrupted(self) -> None:
        """LISTENING -> INTERRUPTED is invalid."""
        sm = PipelineStateMachine()
        assert sm.transition_to(PipelineState.INTERRUPTED) is False
        assert sm.current_state == PipelineState.LISTENING

    def test_invalid_transition_interrupted_to_processing(self) -> None:
        """INTERRUPTED -> PROCESSING is invalid (must go to LISTENING first)."""
        sm = PipelineStateMachine()
        sm.transition_to(PipelineState.PROCESSING)
        sm.transition_to(PipelineState.SPEAKING)
        sm.transition_to(PipelineState.INTERRUPTED)
        assert sm.transition_to(PipelineState.PROCESSING) is False
        assert sm.current_state == PipelineState.INTERRUPTED

    def test_full_barge_in_cycle(self) -> None:
        """Full cycle: LISTENING -> PROCESSING -> SPEAKING -> INTERRUPTED -> LISTENING."""
        sm = PipelineStateMachine()
        assert sm.transition_to(PipelineState.PROCESSING)
        assert sm.transition_to(PipelineState.SPEAKING)
        assert sm.transition_to(PipelineState.INTERRUPTED)
        assert sm.transition_to(PipelineState.LISTENING)
        assert sm.current_state == PipelineState.LISTENING

    def test_full_normal_cycle(self) -> None:
        """Normal cycle: LISTENING -> PROCESSING -> SPEAKING -> LISTENING."""
        sm = PipelineStateMachine()
        assert sm.transition_to(PipelineState.PROCESSING)
        assert sm.transition_to(PipelineState.SPEAKING)
        assert sm.transition_to(PipelineState.LISTENING)
        assert sm.current_state == PipelineState.LISTENING

    def test_is_speaking_property(self) -> None:
        """is_speaking returns True only in SPEAKING state."""
        sm = PipelineStateMachine()
        assert sm.is_speaking is False
        sm.transition_to(PipelineState.PROCESSING)
        assert sm.is_speaking is False
        sm.transition_to(PipelineState.SPEAKING)
        assert sm.is_speaking is True

    def test_is_listening_property(self) -> None:
        """is_listening returns True only in LISTENING state."""
        sm = PipelineStateMachine()
        assert sm.is_listening is True
        sm.transition_to(PipelineState.PROCESSING)
        assert sm.is_listening is False

    def test_force_reset(self) -> None:
        """force_reset returns to LISTENING from any state."""
        sm = PipelineStateMachine()
        sm.transition_to(PipelineState.PROCESSING)
        sm.transition_to(PipelineState.SPEAKING)
        sm.force_reset()
        assert sm.current_state == PipelineState.LISTENING

    def test_force_reset_from_interrupted(self) -> None:
        """force_reset from INTERRUPTED."""
        sm = PipelineStateMachine()
        sm.transition_to(PipelineState.PROCESSING)
        sm.transition_to(PipelineState.SPEAKING)
        sm.transition_to(PipelineState.INTERRUPTED)
        sm.force_reset()
        assert sm.current_state == PipelineState.LISTENING

    def test_thread_safety(self) -> None:
        """Multiple threads can transition without corruption."""
        sm = PipelineStateMachine()
        results: list[bool] = []
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for _ in range(100):
                    sm.transition_to(PipelineState.PROCESSING)
                    sm.force_reset()
                results.append(True)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 4
        # State should be LISTENING after all force_resets
        assert sm.current_state == PipelineState.LISTENING

    def test_self_transition_rejected(self) -> None:
        """Transitioning to the same state is rejected."""
        sm = PipelineStateMachine()
        assert sm.transition_to(PipelineState.LISTENING) is False
