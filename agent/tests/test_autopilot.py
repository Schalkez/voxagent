"""Tests for the Autopilot module."""

import pytest

from core.autopilot import Autopilot, AutopilotTask, TriggerType


class TestTriggerType:
    """Test TriggerType enum."""

    def test_all_types(self) -> None:
        assert TriggerType.TIME_BASED.value == "time"
        assert TriggerType.EVENT_BASED.value == "event"
        assert TriggerType.CONDITION_BASED.value == "condition"
        assert TriggerType.IDLE_BASED.value == "idle"


class TestAutopilotTask:
    """Test AutopilotTask dataclass."""

    def test_task_creation(self) -> None:
        task = AutopilotTask(
            id="test",
            description="Test task",
            trigger_type=TriggerType.TIME_BASED,
            condition=lambda: True,
            actions=[lambda: None],
        )
        assert task.id == "test"
        assert task.repeat is False
        assert task.max_retries == 3
        assert task.timeout_seconds == 300


class TestAutopilot:
    """Test Autopilot engine."""

    @pytest.mark.asyncio
    async def test_register_task(self) -> None:
        ap = Autopilot()
        task = AutopilotTask(
            id="t1",
            description="Test",
            trigger_type=TriggerType.TIME_BASED,
            condition=lambda: False,
            actions=[],
        )
        await ap.register_task(task)
        assert "t1" in ap._tasks

    @pytest.mark.asyncio
    async def test_duplicate_task_raises(self) -> None:
        ap = Autopilot()
        task = AutopilotTask(
            id="t1",
            description="Test",
            trigger_type=TriggerType.TIME_BASED,
            condition=lambda: False,
            actions=[],
        )
        await ap.register_task(task)
        with pytest.raises(ValueError, match="already registered"):
            await ap.register_task(task)

    @pytest.mark.asyncio
    async def test_cancel_task(self) -> None:
        ap = Autopilot()
        task = AutopilotTask(
            id="t1",
            description="Test",
            trigger_type=TriggerType.TIME_BASED,
            condition=lambda: False,
            actions=[],
        )
        await ap.register_task(task)
        result = await ap.cancel_task("t1")
        assert result is True
        assert "t1" not in ap._tasks

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self) -> None:
        ap = Autopilot()
        result = await ap.cancel_task("nope")
        assert result is False

    @pytest.mark.asyncio
    async def test_stop(self) -> None:
        ap = Autopilot()
        ap._running = True
        await ap.stop()
        assert ap._running is False
