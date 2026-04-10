"""OpenRouter LLM provider implementation.

OpenRouter uses an OpenAI-compatible API and aggregates many model
providers behind a single endpoint. Requires an HTTP-Referer header.
Uses the shared httpx.AsyncClient from HttpProvider for connection pooling.
"""

from __future__ import annotations

import httpx

from core.keyring_manager import get_key
from providers.base import LLMProvider, Message, ModelInfo

_API_URL = "https://openrouter.ai/api/v1/chat/completions"
_DEFAULT_MODEL = "meta-llama/llama-3.1-8b-instruct:free"
_HTTP_REFERER = "https://voxagent.dev"


class OpenRouterProvider(LLMProvider):
    """OpenRouter Chat Completions provider (OpenAI-compatible)."""

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        """Initialize the OpenRouter provider.

        Args:
            model: OpenRouter model identifier.
        """
        self._model = model
        self._api_key = get_key("openrouter") or ""

    def _build_headers(self) -> dict[str, str]:
        """Build request headers with authorization and referer.

        Returns:
            Dict of HTTP headers for the OpenRouter API.
        """
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": _HTTP_REFERER,
        }

    async def chat(self, messages: list[Message], **kwargs: object) -> str:
        """Send messages to OpenRouter and return the text response."""
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            **kwargs,
        }
        resp = await self.http_client.post(_API_URL, json=payload, headers=self._build_headers())
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
        resp = await self.http_client.post(_API_URL, json=payload, headers=self._build_headers())
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]["message"]
        if choice.get("tool_calls"):
            tc = choice["tool_calls"][0]
            return {"tool": tc["function"]["name"], "result": tc["function"]["arguments"]}
        return {"tool": "", "result": choice.get("content", "")}

    def get_model_info(self) -> ModelInfo:
        """Return metadata about the OpenRouter model."""
        return ModelInfo(name=self._model, provider="openrouter")

    async def health_check(self) -> bool:
        """Check if OpenRouter API is reachable with the stored key."""
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
