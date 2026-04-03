"""BRAIN module: Smart tier routing and LLM orchestration.

Routes incoming text through a tiered system:
- Tier 0: Keyword pattern matching (no LLM, < 50ms)
- Tier 1: Small LLM for simple intents (1-3B params)
- Tier 2: Medium LLM for reasoning (7-8B params)
- Tier 3: Large LLM for complex tasks (32B+/cloud)
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import ClassVar


class Tier(IntEnum):
    """LLM routing tiers, ordered by cost/latency."""

    ZERO = 0
    ONE = 1
    TWO = 2
    THREE = 3


@dataclass(frozen=True)
class Intent:
    """Parsed user intent from voice command.

    Attributes:
        skill_name: Name of the skill to execute (e.g., 'media_control').
        action: Specific action within the skill (e.g., 'skip', 'pause').
        params: Key-value parameters extracted from the command.
        confidence: Confidence score of the intent classification.
        tier_used: Which routing tier was used to classify this intent.
    """

    skill_name: str
    action: str
    params: dict[str, str]
    confidence: float
    tier_used: Tier


class Brain:
    """Routes text to the appropriate LLM tier and extracts structured intent.

    Uses a cascading strategy: try the cheapest tier first, escalate if needed.
    """

    TIER_0_KEYWORDS: ClassVar[dict[str, str]] = {
        "skip": "media_control",
        "pause": "media_control",
        "next": "media_control",
        "stop": "media_control",
        "tắt": "system_control",
        "mở": "app_launcher",
    }

    async def process(self, text: str) -> Intent:
        """Route text through tier system and return structured intent.

        Attempts Tier 0 (keyword) first, then escalates to higher tiers
        if keyword matching fails or confidence is too low.

        Args:
            text: Raw transcribed text from EARS module.

        Returns:
            Intent with skill name, action, params, and routing metadata.
        """
        # Try Tier 0 first
        tier_zero_result = self._try_tier_zero(text)
        if tier_zero_result is not None:
            return tier_zero_result

        # Tier 1+ will be implemented with actual LLM providers
        return Intent(
            skill_name="unknown",
            action="unknown",
            params={},
            confidence=0.0,
            tier_used=Tier.ONE,
        )

    def _try_tier_zero(self, text: str) -> Intent | None:
        """Attempt keyword matching for instant responses.

        Checks if the input text matches any known keywords for
        direct skill routing without LLM inference.

        Args:
            text: Raw text to match against keywords.

        Returns:
            Intent if keyword matched, None otherwise.
        """
        text_lower = text.strip().lower()
        for keyword, skill_name in self.TIER_0_KEYWORDS.items():
            if keyword in text_lower:
                return Intent(
                    skill_name=skill_name,
                    action=keyword,
                    params={},
                    confidence=1.0,
                    tier_used=Tier.ZERO,
                )
        return None
