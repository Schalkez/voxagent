"""Tests for the configuration system."""

import pytest
from pathlib import Path

from core.config import (
    VoxAgentConfig,
    ProviderConfig,
    RoutingConfig,
    STTConfig,
    TTSConfig,
    AudioConfig,
    WakeWordConfig,
    SecurityConfig,
    load_config,
    save_config,
    list_profiles,
    load_profile,
)


class TestConfigDefaults:
    """Test default configuration values."""

    def test_stt_defaults(self) -> None:
        """STTConfig should have Vietnamese defaults."""
        stt = STTConfig()
        assert stt.provider == "local"
        assert stt.model == "whisper-base"
        assert stt.language == "vi"

    def test_tts_defaults(self) -> None:
        """TTSConfig should have Vietnamese defaults."""
        tts = TTSConfig()
        assert tts.provider == "piper"
        assert tts.voice == "vi-female"
        assert tts.speed == 1.0

    def test_wake_word_defaults(self) -> None:
        """WakeWordConfig should default to 'hey vox'."""
        ww = WakeWordConfig()
        assert ww.engine == "openwakeword"
        assert ww.phrase == "hey vox"
        assert ww.sensitivity == 0.7

    def test_security_defaults(self) -> None:
        """SecurityConfig should be cautious by default."""
        sec = SecurityConfig()
        assert sec.confirm_dangerous_actions is True
        assert sec.max_file_delete_without_confirm == 0

    def test_audio_defaults(self) -> None:
        """AudioConfig should match standard recording settings."""
        audio = AudioConfig()
        assert audio.sample_rate == 16_000
        assert audio.channels == 1
        assert audio.chunk_duration_ms == 80


class TestConfigLoadSave:
    """Test config file operations."""

    def test_load_returns_defaults_when_no_file(self, tmp_path: Path) -> None:
        """load_config should return defaults when config file doesn't exist."""
        config = load_config(tmp_path / "nonexistent")
        assert isinstance(config, VoxAgentConfig)

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        """save_config + load_config should preserve values."""
        config = VoxAgentConfig(
            providers={"test": ProviderConfig(model="test-model")},
            stt=STTConfig(language="en"),
            tts=TTSConfig(voice="en-male", speed=1.5),
        )
        save_config(config, tmp_path)
        loaded = load_config(tmp_path)

        assert loaded.stt.language == "en"
        assert loaded.tts.voice == "en-male"
        assert loaded.tts.speed == 1.5

    def test_save_creates_directory(self, tmp_path: Path) -> None:
        """save_config should create the config directory if needed."""
        new_dir = tmp_path / "new" / "config"
        config = VoxAgentConfig()
        save_config(config, new_dir)
        assert (new_dir / "config.yaml").exists()


class TestConfigFrozen:
    """Test config immutability."""

    def test_provider_config_frozen(self) -> None:
        """ProviderConfig should be immutable."""
        pc = ProviderConfig(model="test")
        with pytest.raises(AttributeError):
            pc.model = "changed"  # type: ignore[misc]

    def test_stt_config_frozen(self) -> None:
        """STTConfig should be immutable."""
        stt = STTConfig()
        with pytest.raises(AttributeError):
            stt.provider = "changed"  # type: ignore[misc]


class TestProfiles:
    """Test built-in configuration profiles."""

    def test_list_profiles_returns_all(self) -> None:
        """list_profiles should return all 4 built-in profiles."""
        profiles = list_profiles()
        assert len(profiles) == 4
        assert "full_local" in profiles
        assert "cloud_free" in profiles
        assert "hybrid" in profiles
        assert "budget_cloud" in profiles

    def test_list_profiles_has_descriptions(self) -> None:
        """Each profile should have a description."""
        profiles = list_profiles()
        for name, desc in profiles.items():
            assert isinstance(desc, str)
            assert len(desc) > 10

    @pytest.mark.parametrize("profile_name", ["full_local", "cloud_free", "hybrid", "budget_cloud"])
    def test_load_profile_returns_valid_config(self, profile_name: str) -> None:
        """Each profile should produce a valid VoxAgentConfig."""
        config = load_profile(profile_name)
        assert isinstance(config, VoxAgentConfig)
        assert config.stt.language == "vi"
        assert config.tts.voice == "vi-female"

    def test_load_profile_full_local_uses_ollama(self) -> None:
        """full_local profile should use Ollama."""
        config = load_profile("full_local")
        assert "ollama" in config.providers
        assert config.routing.fallback_chain == ["ollama"]

    def test_load_profile_hybrid_uses_groq_and_anthropic(self) -> None:
        """hybrid profile should use Groq + Anthropic."""
        config = load_profile("hybrid")
        assert "groq" in config.providers
        assert "anthropic" in config.providers

    def test_load_profile_invalid_raises(self) -> None:
        """Loading an unknown profile should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown profile"):
            load_profile("nonexistent_profile")
