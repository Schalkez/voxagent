"""Browser Control Skill: Open URLs and search the web.

Uses webbrowser.open() for Tier A (native API) to launch the
user's default browser with URLs or Google search queries.
"""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
import webbrowser
from typing import ClassVar

from skills.base import BaseSkill, ExecutionTier, SkillIntent, SkillResult
from skills.registry import register_skill

logger = logging.getLogger("voxagent.skills.browser_control")

_GOOGLE_SEARCH_URL = "https://www.google.com/search"


@register_skill
class BrowserControlSkill(BaseSkill):
    """Opens URLs and searches the web via the default browser."""

    name = "browser_control"
    description = "Open URLs and search the web using the default browser."
    keywords: ClassVar[list[str]] = [
        "browser",
        "web",
        "search",
        "google",
        "url",
        "website",
        "trình duyệt",
        "tìm kiếm",
        "mở web",
    ]
    execution_tiers: ClassVar[list[ExecutionTier]] = [
        ExecutionTier.NATIVE_API,
        ExecutionTier.APP_API,
    ]
    permissions: ClassVar[list[str]] = ["browser:control", "network:access"]

    async def can_handle(self, intent: SkillIntent) -> bool:
        """Determine if this skill can handle the given intent."""
        return intent.skill_name == self.name

    async def execute(self, intent: SkillIntent) -> SkillResult:
        """Execute browser control action.

        Supported actions: open_url, search_web.
        """
        action = intent.action

        if action == "open_url":
            return await self._open_url(intent.params.get("url", ""))

        if action == "search_web":
            return await self._search_web(intent.params.get("query", ""))

        return SkillResult.fail(
            error=f"Unsupported action: {action}",
            tts_response=f"Hành động '{action}' không hỗ trợ bởi browser_control.",
            error_code="unsupported_action",
            tier_used=ExecutionTier.NATIVE_API,
        )

    async def _open_url(self, url: str) -> SkillResult:
        """Open a URL in the default browser.

        Args:
            url: The URL to open. Adds https:// if no scheme is present.

        Returns:
            SkillResult indicating success or failure.
        """
        if not url:
            return SkillResult.fail(
                error="No URL provided.",
                tts_response="Anh muốn mở trang web nào?",
                error_code="invalid_params",
                tier_used=ExecutionTier.NATIVE_API,
            )

        # Add scheme if missing
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        try:
            opened = await asyncio.to_thread(webbrowser.open, url)

            if opened:
                logger.info("Opened URL: %s", url)
                return SkillResult.ok(
                    tts_response="Đã mở trang web rồi nha.",
                    data={"url": url},
                    tier_used=ExecutionTier.NATIVE_API,
                )

            return SkillResult.fail(
                error="Browser could not open the URL.",
                tts_response="Không thể mở trình duyệt.",
                error_code="execution_error",
                tier_used=ExecutionTier.NATIVE_API,
            )
        except (OSError, webbrowser.Error) as e:
            logger.warning("Failed to open URL '%s': %s", url, e)
            return SkillResult.fail(
                error=str(e),
                tts_response="Không thể mở trang web.",
                error_code="execution_error",
                tier_used=ExecutionTier.NATIVE_API,
            )

    async def _search_web(self, query: str) -> SkillResult:
        """Search the web using Google in the default browser.

        Args:
            query: The search query string.

        Returns:
            SkillResult indicating success or failure.
        """
        if not query:
            return SkillResult.fail(
                error="No search query provided.",
                tts_response="Anh muốn tìm kiếm gì?",
                error_code="invalid_params",
                tier_used=ExecutionTier.NATIVE_API,
            )

        search_url = f"{_GOOGLE_SEARCH_URL}?{urllib.parse.urlencode({'q': query})}"

        try:
            opened = await asyncio.to_thread(webbrowser.open, search_url)

            if opened:
                logger.info("Web search: %s", query)
                return SkillResult.ok(
                    tts_response=f"Đã tìm kiếm '{query}' trên Google rồi nha.",
                    data={"query": query, "url": search_url},
                    tier_used=ExecutionTier.NATIVE_API,
                )

            return SkillResult.fail(
                error="Browser could not open the search URL.",
                tts_response="Không thể mở trình duyệt để tìm kiếm.",
                error_code="execution_error",
                tier_used=ExecutionTier.NATIVE_API,
            )
        except (OSError, webbrowser.Error) as e:
            logger.warning("Failed to search '%s': %s", query, e)
            return SkillResult.fail(
                error=str(e),
                tts_response="Không thể tìm kiếm trên web.",
                error_code="execution_error",
                tier_used=ExecutionTier.NATIVE_API,
            )
