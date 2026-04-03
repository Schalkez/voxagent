"""Abstract base classes for all provider types.

All provider implementations must inherit from these ABCs.
Providers are registered in the ProviderRegistry and accessed
through it — never imported directly by core modules.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


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


class LLMProvider(ABC):
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


class STTProvider(ABC):
    """Abstract base class for Speech-to-Text providers."""

    @abstractmethod
    async def transcribe(self, audio: bytes, language: str = "vi") -> TranscribeResult:
        """Transcribe audio bytes to text.

        Args:
            audio: Raw audio data (WAV format).
            language: Target language code for transcription.

        Returns:
            TranscribeResult with text and metadata.
        """


class TTSProvider(ABC):
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


class VisionProvider(ABC):
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
