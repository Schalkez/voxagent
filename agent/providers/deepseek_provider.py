"""DeepSeek LLM provider implementation.

DeepSeek uses an OpenAI-compatible API, so this follows the same pattern
as the OpenAI provider but with a different endpoint and default model.
Uses the shared httpx.AsyncClient from HttpProvider for connection pooling.
"""

from __future__ import annotations

import httpx

from core.keyring_manager import get_key
from providers.base import LLMProvider, Message, ModelInfo

_API_URL = "https://api.deepseek.com/v1/chat/completions"
_DEFAULT_MODEL = "deepseek-chat"


class DeepSeekProvider(LLMProvider):
    """DeepSeek Chat Completions provider (OpenAI-compatible)."""

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        """Initialize the DeepSeek provider.

        Args:
            model: DeepSeek model identifier.
        """
        self._model = model
        self._api_key = get_key("deepseek") or ""

    def _headers(self) -> dict[str, str]:
        """Build authorization headers.

        Returns:
            Dict of HTTP headers.
        """
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def chat(self, messages: list[Message], **kwargs: object) -> str:
        """Send messages to DeepSeek and return the text response."""
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            **kwargs,
        }
        resp = await self.http_client.post(_API_URL, json=payload, headers=self._headers())
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
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "tools": tools,
            **kwargs,
        }
        resp = await self.http_client.post(_API_URL, json=payload, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]
        if choice.get("tool_calls"):
            tc = choice["tool_calls"][0]
            return {"tool": tc["function"]["name"], "result": tc["function"]["arguments"]}
        return {"tool": "", "result": choice.get("content", "")}

    def get_model_info(self) -> ModelInfo:
        """Return metadata about the DeepSeek model."""
        return ModelInfo(name=self._model, provider="deepseek")

    async def health_check(self) -> bool:
        """Check if DeepSeek API is reachable with the stored key."""
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
