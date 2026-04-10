"""Gemini Vision provider -- Google's multimodal AI.

Uses the shared httpx.AsyncClient from HttpProvider for connection pooling.
"""

from __future__ import annotations

import base64

import httpx

from core.keyring_manager import get_key
from core.logging import get_logger
from providers.base import ModelInfo, VisionProvider

logger = get_logger(module="providers.vision.gemini")

_DEFAULT_MODEL = "gemini-1.5-pro"
_VISION_READ_TIMEOUT_SECONDS = 60.0


class GeminiVisionProvider(VisionProvider):
    """Google Gemini Vision provider."""

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        """Initialize the Gemini Vision provider.

        Args:
            model: Gemini model identifier.
        """
        self._model = model
        self._api_key = get_key("gemini") or ""

    def _get_http_timeout(self) -> httpx.Timeout:
        """Return longer read timeout for vision analysis.

        Returns:
            httpx.Timeout configured for Gemini vision latencies.
        """
        return httpx.Timeout(
            connect=5.0,
            read=_VISION_READ_TIMEOUT_SECONDS,
            write=_VISION_READ_TIMEOUT_SECONDS,
            pool=5.0,
        )

    def _build_url(self) -> str:
        """Build the Gemini API URL with API key.

        Returns:
            Full API endpoint URL.
        """
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

        resp = await self.http_client.post(
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
