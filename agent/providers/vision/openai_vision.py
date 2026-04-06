"""OpenAI Vision provider — GPT-4o with image input."""

from __future__ import annotations

import base64
import logging

import httpx

from core.keyring_manager import get_key
from providers.base import ModelInfo, VisionProvider

logger = logging.getLogger("voxagent.providers.vision.openai")

_API_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o"


class OpenAIVisionProvider(VisionProvider):
    """OpenAI GPT-4o Vision provider."""

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        self._model = model
        self._api_key = get_key("openai") or ""

    async def analyze_image(self, image: bytes, prompt: str) -> str:
        """Analyze an image using GPT-4o.

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
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64_image}"},
                        },
                    ],
                }
            ],
            "max_tokens": 1024,
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(_API_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return str(data["choices"][0]["message"]["content"])

    def get_model_info(self) -> ModelInfo:
        """Return model metadata."""
        return ModelInfo(name=self._model, provider="openai")

    async def health_check(self) -> bool:
        """Check if OpenAI API key is available."""
        return bool(self._api_key)
