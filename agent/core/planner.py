"""PLANNER module: Decomposes complex commands into multiple sequential intents.

Instead of outputting a single action, the Planner reads a multi-step user
command (e.g., "Mở web tìm google rồi tắt máy") and breaks it down into an
ordered list of SkillIntents.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from core.brain import Intent, Tier
from providers.base import Message
from providers.registry import ProviderNotFoundError

if TYPE_CHECKING:
    from core.config import VoxAgentConfig
    from providers.registry import ProviderRegistry
    from skills.base import BaseSkill

logger = logging.getLogger("voxagent.planner")


class Planner:
    """Decomposes complex, multi-action commands into sequential intents.

    Uses the Tier 3 LLM (or highest configured tier) to reason about the
    steps required to complete the user's request.
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        skills: list[BaseSkill],
        config: VoxAgentConfig,
    ) -> None:
        """Initialize the Planner.

        Args:
            registry: The LLM Provider registry.
            skills: List of registered skills to map actions against.
            config: Full VoxAgent configuration, containing routing tiers.
        """
        self.registry = registry
        self.skills = {skill.name: skill for skill in skills}
        self.config = config

        # Determine the primary planner tier to use (default Tier 3 if available)
        self.tier = Tier.THREE
        self.tier_config = {"provider": config.routing.tier_3.provider, "model": config.routing.tier_3.model}

    def is_multi_step(self, text: str) -> bool:
        """Quick heuristic check to see if a command contains multiple steps.

        Looks for conjunctions and sequence words.

        Args:
            text: The transcribed text.

        Returns:
            True if text likely contains multiple steps.
        """
        text_lower = text.strip().lower()
        sequence_indicators = [
            " và ", " sau đó ", " rồi ", " tiếp theo ",
            " and ", " then ", " after that "
        ]

        return any(indicator in text_lower for indicator in sequence_indicators)

    async def plan(self, text: str) -> list[Intent]:
        """Decompose a complex command into an ordered list of Intents.

        Args:
            text: Raw transcribed multi-step text.

        Returns:
            List of Intent objects representing sequential steps.
        """
        provider_name = self.tier_config.get("provider", "ollama")
        try:
            llm = self.registry.get_llm(provider_name)
        except ProviderNotFoundError:
            # Fallback if tier 3 not found
            llm = self.registry.get_llm("ollama")

        tools = self._build_planner_tools_schema()

        sys_prompt = (
            "You are VoxAgent Planner. The user wants to perform multiple actions in sequence. "
            "Decompose their request into an ordered sequence of 'tasks'. "
            "Use the provided `create_plan` tool to output the sequence."
        )

        messages = [
            Message(role="system", content=sys_prompt),
            Message(role="user", content=text),
        ]

        logger.info("Decomposing multi-step command using Planner...")
        try:
            response = await llm.chat_with_tools(messages=messages, tools=tools)
            tool_name = str(response.get("tool", ""))
            args = response.get("result", {})

            if not isinstance(args, dict):
                try:
                    args = json.loads(str(args))
                except json.JSONDecodeError:
                    args = {}

            if tool_name == "create_plan" and "steps" in args:
                intents: list[Intent] = []
                steps = args.get("steps", [])

                if isinstance(steps, str):
                    try:
                        steps = json.loads(steps)
                    except json.JSONDecodeError:
                        steps = []

                for step in steps:
                    if isinstance(step, dict):
                        skill_name = str(step.get("skill_name", "unknown"))
                        action = str(step.get("action", "unknown"))
                        params = {str(k): str(v) for k, v in step.get("params", {}).items()}

                        intents.append(Intent(
                            skill_name=skill_name,
                            action=action,
                            params=params,
                            confidence=0.9,
                            tier_used=self.tier,
                        ))

                if intents:
                    return intents

        except Exception as e:
            logger.error("Planner failed to extract plan: %s", e)

        # Fallback: if planning fails, return a single intent representing unknown,
        # or just fallback to Brain's single processing (handled by caller).
        return [Intent(
            skill_name="unknown",
            action="unknown",
            params={},
            confidence=0.0,
            tier_used=self.tier,
        )]

    def _build_planner_tools_schema(self) -> list[dict[str, object]]:
        """Create a specialized tool schema for outputting a plan."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "create_plan",
                    "description": "Create a sequential plan of actions mapping to available skills.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "steps": {
                                "type": "array",
                                "description": "Ordered list of steps to execute.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "skill_name": {
                                            "type": "string",
                                            "description": f"Must be one of [{', '.join(sorted(self.skills.keys()))}].",
                                        },
                                        "action": {
                                            "type": "string",
                                            "description": "The specific task to perform.",
                                        },
                                        "params": {
                                            "type": "object",
                                            "description": "Any arguments needed for the action.",
                                        }
                                    },
                                    "required": ["skill_name", "action"],
                                }
                            }
                        },
                        "required": ["steps"],
                    },
                },
            }
        ]
