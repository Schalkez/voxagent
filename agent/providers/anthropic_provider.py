"""Anthropic LLM provider implementation.

Uses the Anthropic Messages API which differs from the OpenAI format.
"""

from __future__ import annotations

import httpx

from core.keyring_manager import get_key
from providers.base import LLMProvider, Message, ModelInfo

_API_URL = "https://api.anthropic.com/v1/messages"
_DEFAULT_MODEL = "claude-sonnet-4-20250514"
_API_VERSION = "2023-06-01"


class AnthropicProvider(LLMProvider):
    """Anthropic Messages API provider."""

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        self._model = model
        self._api_key = get_key("anthropic") or ""

    def _build_headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": _API_VERSION,
            "Content-Type": "application/json",
        }

    def _to_anthropic_messages(self, messages: list[Message]) -> tuple[str, list[dict[str, str]]]:
        """Convert Message list to Anthropic format (separate system prompt)."""
        system = ""
        converted: list[dict[str, str]] = []
        for m in messages:
            if m.role == "system":
                system = m.content
            else:
                converted.append({"role": m.role, "content": m.content})
        return system, converted

    async def chat(self, messages: list[Message], **kwargs: object) -> str:
        """Send messages to Anthropic and return the text response."""
        system, msgs = self._to_anthropic_messages(messages)
        payload: dict[str, object] = {
            "model": self._model,
            "messages": msgs,
            "max_tokens": kwargs.get("max_tokens", 1024),
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(_API_URL, json=payload, headers=self._build_headers())
            resp.raise_for_status()
            data = resp.json()
            content_blocks = data.get("content", [])
            return str(content_blocks[0]["text"]) if content_blocks else ""

    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict[str, object]],
        **kwargs: object,
    ) -> dict[str, object]:
        """Send messages with tool definitions."""
        system, msgs = self._to_anthropic_messages(messages)
        payload: dict[str, object] = {
            "model": self._model,
            "messages": msgs,
            "max_tokens": kwargs.get("max_tokens", 1024),
            "tools": tools,
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(_API_URL, json=payload, headers=self._build_headers())
            resp.raise_for_status()
            data = resp.json()
            for block in data.get("content", []):
                if block.get("type") == "tool_use":
                    return {"tool": block["name"], "result": block.get("input", {})}
            return {"tool": "", "result": data.get("content", [{}])[0].get("text", "")}

    def get_model_info(self) -> ModelInfo:
        """Return metadata about the Anthropic model."""
        return ModelInfo(name=self._model, provider="anthropic")

    async def health_check(self) -> bool:
        """Check if Anthropic API is reachable."""
        if not self._api_key:
            return False
        try:
            resp = await self.chat(
                [Message(role="user", content="ping")],
                max_tokens=1,
            )
            return bool(resp)
        except (httpx.HTTPError, KeyError):
            return False
