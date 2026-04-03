"""MOUTH module: Text-to-speech output with Vietnamese templates."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SpeechConfig:
    """Configuration for TTS synthesis.

    Attributes:
        voice: Voice identifier (e.g., 'vi-female', 'en-male').
        speed: Playback speed multiplier (1.0 = normal).
        volume: Volume level from 0.0 to 1.0.
    """

    voice: str = "vi-female"
    speed: float = 1.0
    volume: float = 1.0


RESPONSE_TEMPLATES: dict[str, str] = {
    "success": "Đã {action} rồi nha",
    "report": "Hiện tại {state}. {detail}",
    "error": "Không {action} được vì {reason}",
    "confirm": "Ý anh là {option_a} hay {option_b}?",
    "thinking": "Để tôi xem...",
}


class Mouth:
    """Manages TTS output with Vietnamese response templates.

    Supports multiple TTS providers (Piper, Edge TTS, OpenAI, ElevenLabs)
    and provides a template system for consistent Vietnamese responses.
    """

    async def speak(self, text: str, config: SpeechConfig | None = None) -> None:
        """Synthesize text to speech and play through speakers.

        Args:
            text: Text to speak.
            config: Optional speech configuration overrides.
        """

    async def play_earcon(self, sound: str) -> None:
        """Play a short notification sound.

        Used for feedback sounds like confirmation beeps,
        error tones, and thinking indicators.

        Args:
            sound: Sound identifier (e.g., 'beep', 'ding', 'error').
        """

    def format_response(self, template_name: str, **kwargs: str) -> str:
        """Format a response using Vietnamese templates.

        Args:
            template_name: Key in RESPONSE_TEMPLATES.
            **kwargs: Values to interpolate into the template.

        Returns:
            Formatted response string.

        Raises:
            KeyError: If template_name is not found.
        """
        template = RESPONSE_TEMPLATES[template_name]
        return template.format(**kwargs)
