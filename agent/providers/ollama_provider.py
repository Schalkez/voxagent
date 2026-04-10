"""Ollama local LLM provider implementation.

Connects to a locally running Ollama instance. No API key required.
Uses the shared httpx.AsyncClient from HttpProvider for connection pooling.
"""

from __future__ import annotations

import httpx

from providers.base import LLMProvider, Message, ModelInfo

_DEFAULT_BASE_URL = "http://localhost:11434"
_DEFAULT_MODEL = "llama3.1:8b"
_OLLAMA_READ_TIMEOUT_SECONDS = 120.0


class OllamaProvider(LLMProvider):
    """Ollama local inference provider."""

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        base_url: str = _DEFAULT_BASE_URL,
    ) -> None:
        """Initialize the Ollama provider.

        Args:
            model: Ollama model identifier.
            base_url: Base URL of the Ollama server.
        """
        self._model = model
        self._base_url = base_url.rstrip("/")

    def _get_http_timeout(self) -> httpx.Timeout:
        """Return longer read timeout for local inference.

        Returns:
            httpx.Timeout configured for Ollama latencies.
        """
        return httpx.Timeout(
            connect=5.0,
            read=_OLLAMA_READ_TIMEOUT_SECONDS,
            write=_OLLAMA_READ_TIMEOUT_SECONDS,
            pool=5.0,
        )

    async def chat(self, messages: list[Message], **kwargs: object) -> str:
        """Send messages to Ollama and return the text response."""
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            **kwargs,
        }
        resp = await self.http_client.post(f"{self._base_url}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return str(data.get("message", {}).get("content", ""))

    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict[str, object]],
        **kwargs: object,
    ) -> dict[str, object]:
        """Send messages with tool definitions (Ollama tool calling)."""
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "tools": tools,
            "stream": False,
            **kwargs,
        }
        resp = await self.http_client.post(f"{self._base_url}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        msg = data.get("message", {})
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            tc = tool_calls[0]
            fn = tc.get("function", {})
            return {"tool": fn.get("name", ""), "result": fn.get("arguments", {})}
        return {"tool": "", "result": msg.get("content", "")}

    def get_model_info(self) -> ModelInfo:
        """Return metadata about the Ollama model."""
        return ModelInfo(name=self._model, provider="ollama")

    async def health_check(self) -> bool:
        """Check if Ollama is running and has models available."""
        try:
            resp = await self.http_client.get(f"{self._base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = data.get("models", [])
            return len(models) > 0
        except (httpx.HTTPError, ConnectionError):
            return False

    async def list_models(self) -> list[str]:
        """List available models on the Ollama instance.

        Returns:
            List of model names.
        """
        try:
            resp = await self.http_client.get(f"{self._base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except (httpx.HTTPError, ConnectionError):
            return []
