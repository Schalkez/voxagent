"""Configuration loader for VoxAgent.

Loads settings from ~/.voxagent/config.yaml with fallback to defaults.
Uses Pydantic for typed configuration access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _default_config_path() -> Path:
    """Return the default config directory path."""
    return Path.home() / ".voxagent"


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for a single provider.

    Attributes:
        model: Model identifier (e.g., 'gpt-4o', 'llama3.1:8b').
        base_url: Custom API endpoint (used by Ollama).
    """

    model: str = ""
    base_url: str = ""


@dataclass(frozen=True)
class RoutingTierConfig:
    """Configuration for a single routing tier.

    Attributes:
        type: Tier type ('keyword' for Tier 0).
        provider: Provider name for this tier.
        model: Model to use at this tier.
    """

    type: str = ""
    provider: str = ""
    model: str = ""


@dataclass(frozen=True)
class RoutingConfig:
    """Routing configuration across all tiers.

    Attributes:
        tier_0: Tier 0 config (keyword matching).
        tier_1: Tier 1 config (small LLM).
        tier_2: Tier 2 config (medium LLM).
        tier_3: Tier 3 config (large/cloud LLM).
        fallback_chain: Ordered list of providers to try on failure.
    """

    tier_0: RoutingTierConfig = field(default_factory=RoutingTierConfig)
    tier_1: RoutingTierConfig = field(default_factory=RoutingTierConfig)
    tier_2: RoutingTierConfig = field(default_factory=RoutingTierConfig)
    tier_3: RoutingTierConfig = field(default_factory=RoutingTierConfig)
    fallback_chain: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class STTConfig:
    """Speech-to-Text configuration."""

    provider: str = "local"
    model: str = "whisper-base"
    language: str = "vi"


@dataclass(frozen=True)
class TTSConfig:
    """Text-to-Speech configuration."""

    provider: str = "piper"
    voice: str = "vi-female"
    speed: float = 1.0


@dataclass
class VoxAgentConfig:
    """Root configuration object for VoxAgent.

    Attributes:
        providers: Map of provider name to ProviderConfig.
        routing: Tier routing configuration.
        stt: Speech-to-Text settings.
        tts: Text-to-Speech settings.
    """

    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)


def _parse_provider(data: dict[str, Any]) -> ProviderConfig:
    return ProviderConfig(
        model=data.get("model", ""),
        base_url=data.get("base_url", ""),
    )


def _parse_tier(data: dict[str, Any]) -> RoutingTierConfig:
    return RoutingTierConfig(
        type=data.get("type", ""),
        provider=data.get("provider", ""),
        model=data.get("model", ""),
    )


def load_config(config_dir: Path | None = None) -> VoxAgentConfig:
    """Load VoxAgent configuration from YAML file.

    Looks for config.yaml in the given directory, falling back to
    the bundled config.example.yaml if not found.

    Args:
        config_dir: Directory containing config.yaml.
            Defaults to ~/.voxagent/.

    Returns:
        Parsed VoxAgentConfig instance.
    """
    if config_dir is None:
        config_dir = _default_config_path()

    config_file = config_dir / "config.yaml"

    if not config_file.exists():
        # Fall back to example config bundled with the package
        example = Path(__file__).parent.parent / "config.example.yaml"
        if example.exists():
            config_file = example
        else:
            return VoxAgentConfig()

    raw: dict[str, Any] = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}

    # Parse providers
    providers: dict[str, ProviderConfig] = {}
    for name, pdata in raw.get("providers", {}).items():
        providers[name] = _parse_provider(pdata if isinstance(pdata, dict) else {})

    # Parse routing
    routing_raw = raw.get("routing", {})
    routing = RoutingConfig(
        tier_0=_parse_tier(routing_raw.get("tier_0", {})),
        tier_1=_parse_tier(routing_raw.get("tier_1", {})),
        tier_2=_parse_tier(routing_raw.get("tier_2", {})),
        tier_3=_parse_tier(routing_raw.get("tier_3", {})),
        fallback_chain=routing_raw.get("fallback_chain", []),
    )

    # Parse STT / TTS
    stt_raw = raw.get("stt", {})
    tts_raw = raw.get("tts", {})

    return VoxAgentConfig(
        providers=providers,
        routing=routing,
        stt=STTConfig(
            provider=stt_raw.get("provider", "local"),
            model=stt_raw.get("model", "whisper-base"),
            language=stt_raw.get("language", "vi"),
        ),
        tts=TTSConfig(
            provider=tts_raw.get("provider", "piper"),
            voice=tts_raw.get("voice", "vi-female"),
            speed=float(tts_raw.get("speed", 1.0)),
        ),
    )
