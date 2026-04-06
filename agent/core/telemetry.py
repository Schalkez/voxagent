"""Opt-in anonymous telemetry for VoxAgent usage analytics."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger("voxagent.telemetry")

_ENDPOINT = "https://telemetry.voxagent.dev/v1/events"


@dataclass(frozen=True)
class TelemetryEvent:
    """An anonymous telemetry event.

    Attributes:
        event_type: Event category (e.g., 'command', 'skill_used', 'error').
        timestamp: ISO 8601 timestamp.
        metadata: Additional event data.
    """

    event_type: str
    timestamp: str
    metadata: dict[str, str]


class TelemetryClient:
    """Manages opt-in telemetry collection.

    All tracking is no-op when disabled. No data is collected without
    explicit user consent.
    """

    def __init__(self, enabled: bool = False) -> None:
        """Initialize the telemetry client.

        Args:
            enabled: Whether telemetry is enabled. Default is off.
        """
        self._enabled = enabled

    def is_enabled(self) -> bool:
        """Check if telemetry is enabled."""
        return self._enabled

    def enable(self) -> None:
        """Enable telemetry collection."""
        self._enabled = True
        logger.info("Telemetry enabled")

    def disable(self) -> None:
        """Disable telemetry collection."""
        self._enabled = False
        logger.info("Telemetry disabled")

    async def track(self, event: TelemetryEvent) -> None:
        """Send a telemetry event (no-op if disabled).

        Args:
            event: The telemetry event to send.
        """
        if not self._enabled:
            return

        try:
            import httpx

            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    _ENDPOINT,
                    json={
                        "event_type": event.event_type,
                        "timestamp": event.timestamp,
                        "metadata": event.metadata,
                    },
                )
        except (ImportError, ConnectionError, OSError):
            logger.debug("Telemetry send failed (non-critical)")

    @staticmethod
    def create_event(event_type: str, **metadata: str) -> TelemetryEvent:
        """Create a timestamped telemetry event.

        Args:
            event_type: Event category.
            **metadata: Additional key-value data.

        Returns:
            A TelemetryEvent with current timestamp.
        """
        return TelemetryEvent(
            event_type=event_type,
            timestamp=datetime.now(tz=UTC).isoformat(),
            metadata=metadata,
        )
