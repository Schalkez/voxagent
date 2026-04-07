"""AUTOPILOT module: Background task scheduling and monitoring.

Supports trigger types: time-based, event-based, condition-based, and idle-based.
Runs as a separate asyncio task alongside the main pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("voxagent.autopilot")

# ── Constants ──

POLL_INTERVAL_SECONDS = 1.0


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
    actions: list[Callable[[], object]]
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
        logger.info("Registered autopilot task: %s (%s)", task.id, task.description)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a registered task.

        Args:
            task_id: ID of the task to cancel.

        Returns:
            True if the task was found and cancelled, False otherwise.
        """
        if task_id in self._tasks:
            del self._tasks[task_id]
            logger.info("Cancelled autopilot task: %s", task_id)
            return True
        return False

    async def run(self) -> None:
        """Main loop: check triggers every 1s, execute matching tasks.

        Runs continuously until stopped, checking each registered
        task's condition and executing its actions when triggered.
        Failed tasks increment their retry count and are removed
        when max_retries is reached.
        """
        self._running = True
        logger.info("Autopilot started with %d tasks", len(self._tasks))

        while self._running:
            for task_id, task in list(self._tasks.items()):
                try:
                    if task.condition():
                        logger.info("Task triggered: %s", task_id)
                        for action in task.actions:
                            await asyncio.to_thread(action)
                        if not task.repeat:
                            del self._tasks[task_id]
                            logger.info("Task completed and removed: %s", task_id)
                except (RuntimeError, OSError, ValueError) as e:
                    task._retry_count += 1
                    logger.warning(
                        "Task '%s' failed (attempt %d/%d): %s",
                        task_id,
                        task._retry_count,
                        task.max_retries,
                        e,
                    )
                    if task._retry_count >= task.max_retries:
                        del self._tasks[task_id]
                        logger.warning("Task '%s' removed after max retries", task_id)

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    async def stop(self) -> None:
        """Stop the autopilot main loop.

        The loop will exit after the current sleep interval completes.
        """
        self._running = False
        logger.info("Autopilot stopping...")

    @property
    def is_running(self) -> bool:
        """Whether the autopilot main loop is currently active."""
        return self._running

    @property
    def task_count(self) -> int:
        """Number of currently registered tasks."""
        return len(self._tasks)

    def list_tasks(self) -> list[dict[str, str]]:
        """List all registered tasks with their metadata.

        Returns:
            List of dicts with task id, description, and trigger type.
        """
        return [
            {
                "id": task.id,
                "description": task.description,
                "trigger_type": task.trigger_type.value,
                "retries": str(task._retry_count),
            }
            for task in self._tasks.values()
        ]
