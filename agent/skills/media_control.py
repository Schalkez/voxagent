"""Media Control Skill: Play, pause, skip, volume control.

Uses ctypes on Windows for native media key simulation (Tier A),
with keyboard fallback (Tier D) for unsupported platforms.
"""

import ctypes
import logging
import platform
from typing import ClassVar

from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult
from skills.registry import register_skill

logger = logging.getLogger("voxagent.skills.media_control")

_IS_WINDOWS = platform.system() == "Windows"

# Windows Virtual Key Codes
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_VOLUME_UP = 0xAF
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_MUTE = 0xAD

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002


def _send_media_key(vk_code: int) -> bool:
    """Send a virtual key press on Windows.

    Args:
        vk_code: Windows Virtual Key code.

    Returns:
        True if the key was sent successfully.
    """
    if not _IS_WINDOWS:
        return False

    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY, 0)
        user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
        return True
    except (AttributeError, OSError):
        logger.exception("Failed to send media key: 0x%02X", vk_code)
        return False


@register_skill
class MediaControlSkill(BaseSkill):
    """Controls media playback and system volume."""

    name = "media_control"
    description = "Control media playback: play, pause, skip tracks, adjust volume."
    keywords: ClassVar[list[str]] = [
        "play",
        "pause",
        "stop",
        "next",
        "previous",
        "skip",
        "volume",
        "mute",
        "unmute",
        "louder",
        "quieter",
        "nhạc",
        "tạm dừng",
        "tiếp",
        "tăng âm",
        "giảm âm",
        "tắt tiếng",
    ]
    execution_tiers: ClassVar[list[ExecutionTier]] = [
        ExecutionTier.NATIVE_API,
        ExecutionTier.KEYBOARD,
    ]
    permissions: ClassVar[list[str]] = ["media:control"]

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Determine if this skill can handle the given intent."""
        return intent.skill_name == self.name

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Execute media control action.

        Supported actions: play_pause, next_track, prev_track,
        volume_up, volume_down, mute.
        """
        action = intent.action
        action_map: dict[str, tuple[int, str]] = {
            "play_pause": (VK_MEDIA_PLAY_PAUSE, "chuyển trạng thái phát nhạc"),
            "play": (VK_MEDIA_PLAY_PAUSE, "phát nhạc"),
            "pause": (VK_MEDIA_PLAY_PAUSE, "tạm dừng nhạc"),
            "next_track": (VK_MEDIA_NEXT_TRACK, "chuyển bài tiếp"),
            "next": (VK_MEDIA_NEXT_TRACK, "chuyển bài tiếp"),
            "prev_track": (VK_MEDIA_PREV_TRACK, "quay lại bài trước"),
            "previous": (VK_MEDIA_PREV_TRACK, "quay lại bài trước"),
            "volume_up": (VK_VOLUME_UP, "tăng âm lượng"),
            "volume_down": (VK_VOLUME_DOWN, "giảm âm lượng"),
            "mute": (VK_VOLUME_MUTE, "tắt tiếng"),
            "unmute": (VK_VOLUME_MUTE, "bật tiếng"),
        }

        if action not in action_map:
            return SkillResult.fail(
                error=f"Unsupported action: {action}",
                tts_response=f"Hành động '{action}' không hỗ trợ bởi media_control.",
                error_code="unsupported_action",
                tier_used=ExecutionTier.NATIVE_API,
            )

        vk_code, description = action_map[action]

        if _send_media_key(vk_code):
            return SkillResult.ok(
                tts_response=f"Đã {description} rồi nha.",
                tier_used=ExecutionTier.NATIVE_API,
            )

        return SkillResult.fail(
            error="Media key simulation not available on this platform.",
            tts_response="Không thể điều khiển media trên nền tảng này.",
            error_code="platform_unsupported",
            tier_used=ExecutionTier.NATIVE_API,
        )
