"""Multi-device synchronization via shared directory.

Implements file-based sync using a shared folder (local network, Dropbox,
OneDrive, etc.). Each device writes its config to a device-specific JSON
file. sync_preferences() merges configs with last-writer-wins semantics.
"""

from __future__ import annotations

import json
import logging
import platform
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger("voxagent.sync")

_DEFAULT_SYNC_DIR = Path.home() / ".voxagent" / "sync"
_DEVICE_ID_FILE = Path.home() / ".voxagent" / ".device_id"


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


def _get_or_create_device_id() -> str:
    """Get a persistent device ID, creating one on first run."""
    if _DEVICE_ID_FILE.exists():
        return _DEVICE_ID_FILE.read_text(encoding="utf-8").strip()

    device_id = str(uuid.uuid4())
    _DEVICE_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _DEVICE_ID_FILE.write_text(device_id, encoding="utf-8")
    return device_id


class SyncManager:
    """Manages configuration and preference synchronization across devices.

    Sync works via a shared directory. Each device writes:
      sync_dir/{device_id}.json  — device info + preferences

    sync_preferences() reads all device files and merges them
    with last-writer-wins based on timestamp.
    """

    def __init__(self, sync_dir: Path | None = None) -> None:
        """Initialize the sync manager.

        Args:
            sync_dir: Shared directory for sync files.
                     Defaults to ~/.voxagent/sync/.
        """
        self._sync_dir = sync_dir or _DEFAULT_SYNC_DIR
        self._sync_dir.mkdir(parents=True, exist_ok=True)
        self._device_id = _get_or_create_device_id()

    async def register_device(self) -> DeviceInfo:
        """Register the current device and write its info to the sync dir.

        Returns:
            DeviceInfo for the current machine.
        """
        device = DeviceInfo(
            device_id=self._device_id,
            hostname=platform.node(),
            platform=platform.system(),
            last_seen=datetime.now(tz=UTC).isoformat(),
        )
        device_file = self._sync_dir / f"{self._device_id}.json"
        device_file.write_text(
            json.dumps({"device": asdict(device), "preferences": {}}, indent=2),
            encoding="utf-8",
        )
        logger.info("Device registered: %s (%s)", device.hostname, device.device_id[:8])
        return device

    async def sync_preferences(self, local_prefs: dict[str, object] | None = None) -> dict[str, object]:
        """Sync preferences across registered devices.

        Writes local preferences to the device file, then reads
        all device files and returns the merged result (last-writer-wins).

        Args:
            local_prefs: This device's preferences to write. If None, only reads.

        Returns:
            Merged preferences dict from all devices.
        """
        device_file = self._sync_dir / f"{self._device_id}.json"

        # Write local prefs
        if local_prefs is not None:
            data: dict[str, object] = {"preferences": local_prefs}
            if device_file.exists():
                try:
                    existing = json.loads(device_file.read_text(encoding="utf-8"))
                    data["device"] = existing.get("device", {})
                except (json.JSONDecodeError, OSError):
                    pass
            data["preferences"] = local_prefs
            data["synced_at"] = datetime.now(tz=UTC).isoformat()
            device_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

        # Read and merge all device files (last-writer-wins by synced_at)
        merged: dict[str, object] = {}
        latest_ts = ""

        for path in self._sync_dir.glob("*.json"):
            try:
                content = json.loads(path.read_text(encoding="utf-8"))
                ts = content.get("synced_at", "")
                prefs = content.get("preferences", {})
                if ts >= latest_ts:
                    merged.update(prefs)
                    latest_ts = ts
            except (json.JSONDecodeError, OSError):
                logger.warning("Skipping corrupt sync file: %s", path.name)
                continue

        logger.info("Synced preferences from %d devices", len(list(self._sync_dir.glob("*.json"))))
        return merged

    async def list_devices(self) -> list[DeviceInfo]:
        """List all registered devices from the sync directory.

        Returns:
            List of known DeviceInfo objects.
        """
        devices: list[DeviceInfo] = []
        for path in self._sync_dir.glob("*.json"):
            try:
                content = json.loads(path.read_text(encoding="utf-8"))
                d = content.get("device", {})
                if d:
                    devices.append(
                        DeviceInfo(
                            device_id=d.get("device_id", path.stem),
                            hostname=d.get("hostname", "unknown"),
                            platform=d.get("platform", "unknown"),
                            last_seen=d.get("last_seen", ""),
                        )
                    )
            except (json.JSONDecodeError, OSError):
                continue
        return devices

    async def remove_device(self, device_id: str) -> bool:
        """Remove a device from the sync directory.

        Args:
            device_id: ID of the device to remove.

        Returns:
            True if device file was deleted.
        """
        target = self._sync_dir / f"{device_id}.json"
        if not target.exists():
            return False
        try:
            target.unlink()
            logger.info("Removed device: %s", device_id[:8])
            return True
        except OSError:
            logger.exception("Failed to remove device file")
            return False
