"""OpenAI LLM provider implementation.

Uses httpx for async HTTP requests to the OpenAI Chat Completions API.
API key is retrieved from the OS keyring.
"""

from __future__ import annotations

import httpx

from core.keyring_manager import get_key
from providers.base import LLMProvider, Message, ModelInfo

_API_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(LLMProvider):
    """OpenAI Chat Completions provider."""

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        self._model = model
        self._api_key = get_key("openai") or ""

    async def chat(self, messages: list[Message], **kwargs: object) -> str:
        """Send messages to OpenAI and return the text response."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            **kwargs,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return str(data["choices"][0]["message"]["content"])

    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict[str, object]],
        **kwargs: object,
    ) -> dict[str, object]:
        """Send messages with tool definitions for function calling."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "tools": tools,
            **kwargs,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]["message"]
            if choice.get("tool_calls"):
                tc = choice["tool_calls"][0]
                return {"tool": tc["function"]["name"], "result": tc["function"]["arguments"]}
            return {"tool": "", "result": choice.get("content", "")}

    def get_model_info(self) -> ModelInfo:
        """Return metadata about the OpenAI model."""
        return ModelInfo(name=self._model, provider="openai")

    async def health_check(self) -> bool:
        """Check if OpenAI API is reachable with the stored key."""
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
