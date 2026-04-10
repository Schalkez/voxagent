"""Abstract base classes for all provider types.

All provider implementations must inherit from these ABCs.
Providers are registered in the ProviderRegistry and accessed
through it -- never imported directly by core modules.

Includes ``HttpProvider`` mixin for shared httpx.AsyncClient lifecycle.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    pass

# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_POOL_MAX_CONNECTIONS = 10
DEFAULT_POOL_MAX_KEEPALIVE = 5
DEFAULT_CONNECT_TIMEOUT_SECONDS = 5.0
DEFAULT_READ_TIMEOUT_SECONDS = 30.0


@dataclass(frozen=True)
class ModelInfo:
    """Metadata about a model served by a provider.

    Attributes:
        name: Model identifier (e.g., 'llama3.1:8b').
        provider: Provider name (e.g., 'ollama', 'openai').
        parameters: Number of model parameters, if known.
        context_length: Maximum context window size in tokens.
    """

    name: str
    provider: str
    parameters: int | None = None
    context_length: int | None = None


@dataclass(frozen=True)
class Message:
    """A chat message in the LLM conversation.

    Attributes:
        role: Message role ('system', 'user', or 'assistant').
        content: The text content of the message.
    """

    role: str
    content: str


@dataclass(frozen=True)
class TranscribeResult:
    """Result from STT transcription.

    Attributes:
        text: Transcribed text.
        confidence: Confidence score between 0.0 and 1.0.
        language: Detected language code.
        duration_ms: Audio duration in milliseconds.
    """

    text: str
    confidence: float
    language: str
    duration_ms: int


# ── Shared HTTP Client Mixin ────────────────────────────────────────────────


class HttpProvider:
    """Mixin providing a shared httpx.AsyncClient per provider instance.

    Creates exactly one ``httpx.AsyncClient`` lazily on first access
    and reuses it across all requests. Connection pooling is configured
    with sensible defaults. Call ``close()`` during application shutdown
    to release connections.
    """

    _http_client: httpx.AsyncClient | None = None

    def _get_http_timeout(self) -> httpx.Timeout:
        """Return the httpx timeout configuration for this provider.

        Subclasses can override to customise timeouts.

        Returns:
            httpx.Timeout instance.
        """
        return httpx.Timeout(
            connect=DEFAULT_CONNECT_TIMEOUT_SECONDS,
            read=DEFAULT_READ_TIMEOUT_SECONDS,
            write=DEFAULT_READ_TIMEOUT_SECONDS,
            pool=DEFAULT_CONNECT_TIMEOUT_SECONDS,
        )

    @property
    def http_client(self) -> httpx.AsyncClient:
        """Lazily initialise and return the shared httpx.AsyncClient.

        Returns:
            A reusable async HTTP client with connection pooling.
        """
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=self._get_http_timeout(),
                limits=httpx.Limits(
                    max_connections=DEFAULT_POOL_MAX_CONNECTIONS,
                    max_keepalive_connections=DEFAULT_POOL_MAX_KEEPALIVE,
                ),
            )
        return self._http_client

    async def close(self) -> None:
        """Close the shared HTTP client and release connections.

        Safe to call multiple times. Should be called during
        application shutdown (e.g., from ``VoxAgentApp.stop()``).
        """
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None


# ── Provider ABCs ────────────────────────────────────────────────────────────


class LLMProvider(HttpProvider, ABC):
    """Abstract base class for Large Language Model providers."""

    @abstractmethod
    async def chat(self, messages: list[Message], **kwargs: object) -> str:
        """Send messages to the LLM and get a text response.

        Args:
            messages: Conversation history as Message objects.
            **kwargs: Provider-specific parameters (temperature, max_tokens, etc.).

        Returns:
            The model's text response.
        """

    @abstractmethod
    async def chat_with_tools(
        self,
        messages: list[Message],
        tools: list[dict[str, object]],
        **kwargs: object,
    ) -> dict[str, object]:
        """Send messages with tool definitions for function calling.

        Args:
            messages: Conversation history.
            tools: Tool/function definitions in OpenAI format.
            **kwargs: Provider-specific parameters.

        Returns:
            Dict with 'tool' (tool name) and 'result' (call arguments).
        """

    @abstractmethod
    def get_model_info(self) -> ModelInfo:
        """Get metadata about the model this provider serves.

        Returns:
            ModelInfo with name, provider, parameters, context length.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available and responding.

        Returns:
            True if the provider is healthy, False otherwise.
        """


class STTProvider(HttpProvider, ABC):
    """Abstract base class for Speech-to-Text providers."""

    @abstractmethod
    async def transcribe(
        self, audio: bytes, language: str = "vi", task: str = "transcribe"
    ) -> TranscribeResult:
        """Transcribe audio bytes to text.

        Args:
            audio: Raw audio data (WAV format).
            language: Target language code for transcription.
            task: Task type -- 'transcribe' or 'translate' (to English).

        Returns:
            TranscribeResult with text and metadata.
        """


class TTSProvider(HttpProvider, ABC):
    """Abstract base class for Text-to-Speech providers."""

    @abstractmethod
    async def synthesize(self, text: str, voice: str = "vi-female", speed: float = 1.0) -> bytes:
        """Synthesize text into audio.

        Args:
            text: Text to convert to speech.
            voice: Voice identifier.
            speed: Playback speed multiplier.

        Returns:
            Raw audio bytes (WAV format).
        """

    async def synthesize_stream(
        self,
        text: str,
        voice: str = "vi-female",
        speed: float = 1.0,
    ) -> AsyncIterator[bytes]:
        """Stream audio chunks as they become available.

        Default implementation falls back to ``synthesize()`` and yields
        the complete result as a single chunk. Providers with native
        streaming (Edge TTS, ElevenLabs) should override this.

        Args:
            text: Text to convert to speech.
            voice: Voice identifier.
            speed: Playback speed multiplier.

        Yields:
            Raw audio bytes — format depends on provider (MP3 or WAV).
        """
        full_audio = await self.synthesize(text, voice=voice, speed=speed)
        yield full_audio


class VisionProvider(HttpProvider, ABC):
    """Abstract base class for Vision/Image understanding providers."""

    @abstractmethod
    async def analyze_image(self, image: bytes, prompt: str) -> str:
        """Analyze an image with a text prompt.

        Args:
            image: Image data (PNG/JPEG bytes).
            prompt: Question or instruction about the image.

        Returns:
            Text analysis result.
        """
