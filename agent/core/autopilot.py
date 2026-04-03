"""AUTOPILOT module: Background task scheduling and monitoring.

Supports trigger types: time-based, event-based, condition-based, and idle-based.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TriggerType(Enum):
    """Types of triggers for autopilot tasks.

    TIME_BASED: "5 phút nữa nhắc tao"
    EVENT_BASED: "khi download xong"
    CONDITION_BASED: "khi CPU < 30%"
    IDLE_BASED: "khi Cursor idle 30s"
    """

    TIME_BASED = "time"
    EVENT_BASED = "event"
    CONDITION_BASED = "condition"
    IDLE_BASED = "idle"


@dataclass
class AutopilotTask:
    """A background task managed by the Autopilot engine.

    Attributes:
        id: Unique task identifier.
        description: Human-readable description for TTS reporting.
        trigger_type: What triggers this task to execute.
        condition: Callable that returns True when the task should fire.
        actions: List of callables to execute when triggered.
        repeat: Whether to re-register after completion.
        max_retries: Maximum retry attempts on failure.
        timeout_seconds: Maximum execution time before cancellation.
    """

    id: str
    description: str
    trigger_type: TriggerType
    condition: Callable[[], bool]
    actions: list[Callable[[], Any]]
    repeat: bool = False
    max_retries: int = 3
    timeout_seconds: int = 300
    _retry_count: int = field(default=0, init=False)


class Autopilot:
    """Manages background tasks triggered by time, events, or conditions.

    Runs as a separate asyncio task alongside the main pipeline,
    periodically checking trigger conditions and executing actions.
    """

    def __init__(self) -> None:
        """Initialize the Autopilot with an empty task registry."""
        self._tasks: dict[str, AutopilotTask] = {}
        self._running = False

    async def register_task(self, task: AutopilotTask) -> None:
        """Register a new background task.

        Args:
            task: The AutopilotTask to register and monitor.

        Raises:
            ValueError: If a task with the same ID already exists.
        """
        if task.id in self._tasks:
            msg = f"Task '{task.id}' already registered"
            raise ValueError(msg)
        self._tasks[task.id] = task

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a registered task.

        Args:
            task_id: ID of the task to cancel.

        Returns:
            True if the task was found and cancelled, False otherwise.
        """
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

    async def run(self) -> None:
        """Main loop checking triggers and executing tasks.

        Runs continuously until stopped, checking each registered
        task's condition and executing its actions when triggered.
        """
        self._running = True
        # Placeholder — will implement actual trigger checking loop
