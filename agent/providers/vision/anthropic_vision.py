"""Anthropic Vision provider — Claude with image input."""

from __future__ import annotations

import base64
import logging

import httpx

from core.keyring_manager import get_key
from providers.base import ModelInfo, VisionProvider

logger = logging.getLogger("voxagent.providers.vision.anthropic")

_API_URL = "https://api.anthropic.com/v1/messages"
_DEFAULT_MODEL = "claude-sonnet-4-20250514"
_API_VERSION = "2023-06-01"


class AnthropicVisionProvider(VisionProvider):
    """Anthropic Claude Vision provider."""

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        self._model = model
        self._api_key = get_key("anthropic") or ""

    async def analyze_image(self, image: bytes, prompt: str) -> str:
        """Analyze an image using Claude.

        Args:
            image: Raw image bytes (PNG/JPEG).
            prompt: Analysis prompt.

        Returns:
            Text analysis result.
        """
        if not self._api_key:
            return ""

        b64_image = base64.b64encode(image).decode("utf-8")
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": _API_VERSION,
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64_image,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            content_blocks = data.get("content", [])
            return str(content_blocks[0]["text"]) if content_blocks else ""

    def get_model_info(self) -> ModelInfo:
        """Return model metadata."""
        return ModelInfo(name=self._model, provider="anthropic")

    async def health_check(self) -> bool:
        """Check if Anthropic API key is available."""
        return bool(self._api_key)
