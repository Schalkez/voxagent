"""Multi-device synchronization skeleton."""

from __future__ import annotations

import logging
import platform
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger("voxagent.sync")


@dataclass(frozen=True)
class DeviceInfo:
    """Information about a registered device.

    Attributes:
        device_id: Unique device identifier.
        hostname: Machine hostname.
        platform: OS platform string.
        last_seen: ISO 8601 timestamp of last sync.
    """

    device_id: str
    hostname: str
    platform: str
    last_seen: str


class SyncManager:
    """Manages configuration and preference synchronization across devices."""

    def __init__(self) -> None:
        """Initialize the sync manager."""
        self._devices: dict[str, DeviceInfo] = {}

    async def register_device(self) -> DeviceInfo:
        """Register the current device.

        Returns:
            DeviceInfo for the current machine.
        """
        device = DeviceInfo(
            device_id=str(uuid.uuid4()),
            hostname=platform.node(),
            platform=platform.system(),
            last_seen=datetime.now(tz=UTC).isoformat(),
        )
        self._devices[device.device_id] = device
        logger.info("Device registered: %s (%s)", device.hostname, device.device_id[:8])
        return device

    async def sync_preferences(self) -> bool:
        """Sync preferences across registered devices.

        Returns:
            True if sync completed (currently always True — stub).
        """
        logger.info("Preference sync triggered (stub — local only)")
        return True

    async def list_devices(self) -> list[DeviceInfo]:
        """List all registered devices.

        Returns:
            List of known DeviceInfo objects.
        """
        return list(self._devices.values())
