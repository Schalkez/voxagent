"""BRAIN module: Smart tier routing and LLM orchestration.

Routes incoming text through a tiered system:
- Tier 0: Keyword pattern matching (no LLM, < 50ms)
- Tier 1: Small LLM for simple intents (1-3B params)
- Tier 2: Medium LLM for reasoning (7-8B params)
- Tier 3: Large LLM for complex tasks (32B+/cloud)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING

from core.errors import PipelineError, ProviderError
from core.eyes import Eyes
from providers.base import Message
from providers.registry import ProviderNotFoundError, ProviderRegistry
from skills.base import BaseSkill

if TYPE_CHECKING:
    from core.config import VoxAgentConfig

logger = logging.getLogger("voxagent.brain")


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

    def __init__(
        self,
        registry: ProviderRegistry,
        skills: list[BaseSkill],
        routing_config: dict[str, object] | None = None,
        config: VoxAgentConfig | None = None,
    ) -> None:
        """Initialize the Brain orchestrator.

        Args:
            registry: The LLM Provider registry.
            skills: List of registered BaseSkill objects.
            routing_config: Tier-based routing configurations (legacy).
            config: Full VoxAgentConfig (preferred). Overrides routing_config.
        """
        self.registry = registry
        self.skills = {skill.name: skill for skill in skills}
        self.eyes = Eyes()

        if config is not None:
            # Extract routing tiers from config into dict format
            self.routing_config: dict[str, object] = {
                "tiers": [
                    {"provider": config.routing.tier_1.provider, "model": config.routing.tier_1.model},
                    {"provider": config.routing.tier_2.provider, "model": config.routing.tier_2.model},
                    {"provider": config.routing.tier_3.provider, "model": config.routing.tier_3.model},
                ],
            }
        else:
            self.routing_config = routing_config or {}

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

        # Escalate to Tier 1 via LLM
        return await self._try_llm_routing(text, Tier.ONE)

    def _try_tier_zero(self, text: str) -> Intent | None:
        """Attempt keyword matching for instant responses.

        Checks against keywords declared natively inside each BaseSkill.
        """
        text_lower = text.strip().lower()
        for skill_name, skill in self.skills.items():
            for keyword in skill.keywords:
                if keyword in text_lower:
                    return Intent(
                        skill_name=skill_name,
                        action=keyword,  # Default action mapped to keyword
                        params={},
                        confidence=1.0,
                        tier_used=Tier.ZERO,
                    )
        return None

    async def _try_llm_routing(self, text: str, target_tier: Tier) -> Intent:
        """Call the LLM using Function Calling / Tools to classify intent."""
        # 1. Resolve Provider from Config
        # In a real app, logic would map target_tier -> specific tier in config
        tier_idx = target_tier.value - 1
        tiers = self.routing_config.get("tiers", [])
        if tier_idx < 0 or tier_idx >= len(tiers):
            tier_config = {"provider": "ollama", "model": "llama3.1:8b"}
        else:
            tier_config = tiers[tier_idx]

        provider_name = str(tier_config.get("provider", "ollama")).lower()

        try:
            llm = self.registry.get_llm(provider_name)
        except ProviderNotFoundError:
            # Fallback to local
            try:
                llm = self.registry.get_llm("ollama")
            except ProviderNotFoundError as fallback_err:
                raise PipelineError(
                    "No LLM providers available",
                    stage="brain",
                    user_message="Khong co mo hinh AI nao san sang.",
                ) from fallback_err

        # 2. Build Tools from Skills
        tools = self._build_tools_schema()

        # 3. System Prompt
        sys_prompt = "You are VoxAgent, an AI desktop assistant. Analyze the user's voice command and select the appropriate tool (skill) to execute. Always use tool calling."

        # Optionally inject vision context if the command references the screen
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["màn hình", "screen", "đọc", "nhìn", "thấy"]):
            try:
                screen_content = await self.eyes.read_screen_text()
                if screen_content:
                    sys_prompt += f"\n\nCURRENT SCREEN TEXT CONTEXT:\n{screen_content}"
            except (OSError, RuntimeError) as e:
                logger.warning("Failed to inject screen context: %s", e)

        messages = [Message(role="system", content=sys_prompt), Message(role="user", content=text)]

        # 4. Inference
        try:
            response = await llm.chat_with_tools(messages=messages, tools=tools)
            tool_name = str(response.get("tool", ""))
            args = response.get("result", {})

            if not isinstance(args, dict):
                # Provider might have returned a JSON string instead of dict
                try:
                    args = json.loads(str(args))
                except json.JSONDecodeError:
                    args = {}

            if tool_name in self.skills:
                action = str(args.get("action", "default"))
                params = {str(k): str(v) for k, v in args.items() if k not in ("action", "confidence")}

                try:
                    confidence = float(args.get("confidence", 0.9))
                except (ValueError, TypeError):
                    confidence = 0.9

                return Intent(
                    skill_name=tool_name,
                    action=action,
                    params=params,
                    confidence=confidence,
                    tier_used=target_tier,
                )

        except ProviderError:
            raise  # Let provider errors propagate for fallback handling
        except (KeyError, json.JSONDecodeError, TypeError, ValueError) as e:
            # On failure, return unknown intent instead of crashing the pipeline
            logger.error("Failed to extract intent from LLM response: %s", e)

        return Intent(
            skill_name="unknown",
            action="unknown",
            params={},
            confidence=0.0,
            tier_used=target_tier,
        )

    def _build_tools_schema(self) -> list[dict[str, object]]:
        """Convert loaded skills to OpenAI-compatible Tools JSON Schema."""
        tools: list[dict[str, object]] = []
        for skill_name, skill in self.skills.items():
            tool: dict[str, object] = {
                "type": "function",
                "function": {
                    "name": skill_name,
                    "description": skill.description or f"Skill for {skill_name}",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "description": "The specific task to perform.",
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidence score from 0.0 to 1.0 of the classification."
                            }
                        },
                        "required": ["action", "confidence"],
                    },
                },
            }
            tools.append(tool)

        # Add fallback
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "unknown",
                    "description": "Use this if the user command doesn't match any known skill.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string"},
                            "message": {
                                "type": "string",
                                "description": "Direct conversation response",
                            },
                        },
                        "required": ["message"],
                    },
                },
            }
        )
        return tools
