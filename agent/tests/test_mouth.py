"""Tests for the Mouth TTS output module."""

import pytest

from core.mouth import Mouth, SpeechConfig, RESPONSE_TEMPLATES, _play_wav
from unittest.mock import AsyncMock, MagicMock, patch


class TestSpeechConfig:
    """Test SpeechConfig dataclass."""

    def test_defaults(self) -> None:
        """SpeechConfig should have sensible defaults."""
        config = SpeechConfig()
        assert config.voice == "vi-female"
        assert config.speed == 1.0
        assert config.volume == 1.0

    def test_custom_values(self) -> None:
        """SpeechConfig should accept custom values."""
        config = SpeechConfig(voice="en-male", speed=1.5, volume=0.8)
        assert config.voice == "en-male"
        assert config.speed == 1.5
        assert config.volume == 0.8

    def test_is_frozen(self) -> None:
        """SpeechConfig should be immutable."""
        config = SpeechConfig()
        with pytest.raises(AttributeError):
            config.voice = "changed"  # type: ignore[misc]


class TestResponseTemplates:
    """Test Vietnamese response template system."""

    def test_success_template(self) -> None:
        """Success template should format correctly."""
        mouth = Mouth()
        result = mouth.format_response("success", action="phát nhạc")
        assert result == "Đã phát nhạc rồi nha"

    def test_error_template(self) -> None:
        """Error template should format correctly."""
        mouth = Mouth()
        result = mouth.format_response("error", action="mở Chrome", reason="không tìm thấy")
        assert result == "Không mở Chrome được vì không tìm thấy"

    def test_confirm_template(self) -> None:
        """Confirm template should format correctly."""
        mouth = Mouth()
        result = mouth.format_response("confirm", option_a="tắt máy", option_b="khởi động lại")
        assert "tắt máy" in result
        assert "khởi động lại" in result

    def test_invalid_template_raises(self) -> None:
        """Unknown template name should raise KeyError."""
        mouth = Mouth()
        with pytest.raises(KeyError):
            mouth.format_response("nonexistent")

    def test_all_templates_present(self) -> None:
        """All expected templates should exist."""
        expected = {"success", "report", "error", "confirm", "thinking", "dangerous", "cancelled"}
        assert expected.issubset(set(RESPONSE_TEMPLATES.keys()))


class TestMouthSpeak:
    """Test Mouth.speak() method."""

    @pytest.mark.asyncio
    async def test_speak_without_provider_logs_warning(self) -> None:
        """speak() should not raise when no TTS provider is configured."""
        mouth = Mouth(tts_provider=None)
        await mouth.speak("Hello")  # Should not raise

    @pytest.mark.asyncio
    async def test_speak_empty_text_is_noop(self) -> None:
        """speak() should do nothing for empty text."""
        mock_tts = AsyncMock()
        mouth = Mouth(tts_provider=mock_tts)
        await mouth.speak("")
        mock_tts.synthesize.assert_not_called()

    @pytest.mark.asyncio
    async def test_speak_calls_provider(self) -> None:
        """speak() should call TTS provider with correct args."""
        mock_tts = AsyncMock()
        # Return valid WAV data
        mock_tts.synthesize.return_value = b""
        mouth = Mouth(tts_provider=mock_tts)

        with patch("core.mouth._play_wav", new_callable=AsyncMock):
            await mouth.speak("Xin chào")

        mock_tts.synthesize.assert_called_once_with(
            "Xin chào", voice="vi-female", speed=1.0
        )
