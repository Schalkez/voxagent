"""Gemini Vision provider — Google's multimodal AI."""

from __future__ import annotations

import base64
import logging

import httpx

from core.keyring_manager import get_key
from providers.base import ModelInfo, VisionProvider

logger = logging.getLogger("voxagent.providers.vision.gemini")

_DEFAULT_MODEL = "gemini-1.5-pro"


class GeminiVisionProvider(VisionProvider):
    """Google Gemini Vision provider."""

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        self._model = model
        self._api_key = get_key("gemini") or ""

    def _build_url(self) -> str:
        return (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self._model}:generateContent?key={self._api_key}"
        )

    async def analyze_image(self, image: bytes, prompt: str) -> str:
        """Analyze an image using Gemini.

        Args:
            image: Raw image bytes (PNG/JPEG).
            prompt: Analysis prompt.

        Returns:
            Text analysis result.
        """
        if not self._api_key:
            return ""

        b64_image = base64.b64encode(image).decode("utf-8")
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": b64_image,
                            }
                        },
                    ]
                }
            ],
        }

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                self._build_url(),
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                return str(parts[0]["text"]) if parts else ""
            return ""

    def get_model_info(self) -> ModelInfo:
        """Return model metadata."""
        return ModelInfo(name=self._model, provider="gemini")

    async def health_check(self) -> bool:
        """Check if Gemini API key is available."""
        return bool(self._api_key)
