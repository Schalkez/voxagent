"""Persistent State Store for API.

State is loaded from ~/.voxagent/state.yaml on import and written back
after every mutation. Falls back to hardcoded defaults on first run.
"""

from __future__ import annotations

import logging
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TypedDict

import yaml

logger = logging.getLogger("voxagent.api.state")

_STATE_FILE = Path.home() / ".voxagent" / "state.yaml"


class PermissionEntry(TypedDict):
    """A single permission entry."""

    name: str
    level: str


class TierEntry(TypedDict, total=False):
    """A routing tier configuration."""

    tier: int
    title: str
    description: str
    provider: str
    model: str
    provider_options: list[str]
    model_options: list[str]
    warning: str


class RoutingConfigState(TypedDict):
    """Full routing configuration."""

    preset: str
    tiers: list[TierEntry]
    status: str


class SkillEntry(TypedDict):
    """A skill's full state."""

    id: str
    name: str
    icon: str
    version: str
    author: str
    description: str
    enabled: bool
    permissions: list[PermissionEntry]


# Provider Metadata (static — not persisted)
PROVIDER_META: dict[str, dict[str, str]] = {
    "openai": {"name": "OpenAI", "icon": "psychology", "type": "cloud"},
    "groq": {"name": "Groq", "icon": "bolt", "type": "cloud"},
    "anthropic": {"name": "Anthropic", "icon": "shield", "type": "cloud"},
    "gemini": {"name": "Gemini", "icon": "flare", "type": "cloud"},
    "deepseek": {"name": "DeepSeek", "icon": "explore", "type": "cloud"},
    "mistral": {"name": "Mistral", "icon": "air", "type": "cloud"},
    "openrouter": {"name": "OpenRouter", "icon": "router", "type": "cloud"},
    "ollama": {"name": "Ollama", "icon": "terminal", "type": "local"},
}


# ── Default State ──

_DEFAULT_ROUTING: RoutingConfigState = {
    "preset": "balanced",
    "tiers": [
        {
            "tier": 1,
            "title": "Tier 1 (Speed & Simple)",
            "description": "Fastest. Used for simple intents, parsing, and extraction.",
            "provider": "groq",
            "model": "llama-3.1-8b-instant",
            "provider_options": ["groq", "openai", "mistral"],
            "model_options": ["llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma-7b-it"],
        },
        {
            "tier": 2,
            "title": "Tier 2 (Reasoning)",
            "description": "Balanced. Used for logic, file management, and multi-step plans.",
            "provider": "ollama",
            "model": "qwen2.5:7b",
            "provider_options": ["ollama", "deepseek", "openrouter"],
            "model_options": ["qwen2.5:7b", "llama3:8b-instruct", "mistral-v0.3"],
        },
        {
            "tier": 3,
            "title": "Tier 3 (Complex & Vision)",
            "description": "Heavy lifting. Used for code review, screen reading, and complex tasks.",
            "provider": "anthropic",
            "model": "claude-3-5-sonnet",
            "provider_options": ["anthropic", "openai", "gemini"],
            "model_options": ["claude-3-5-sonnet", "gpt-4o-2024-08-06", "gemini-1.5-pro"],
            "warning": "High Cost",
        },
    ],
    "status": "Optimized for latency",
}

_DEFAULT_SKILLS: list[SkillEntry] = [
    {
        "id": "youtube_ad_skipper",
        "name": "YouTube Ad Skipper",
        "icon": "ads_click",
        "version": "v1.0.0",
        "author": "minhtq",
        "description": "Automatically skips YouTube ads using browser control.",
        "enabled": True,
        "permissions": [
            {"name": "browser:control", "level": "safe"},
            {"name": "screen:read", "level": "elevated"},
        ],
    },
    {
        "id": "terminal_control",
        "name": "Terminal Control",
        "icon": "terminal",
        "version": "v0.9.4",
        "author": "jarvis_core",
        "description": "Execute terminal commands and manage system processes safely.",
        "enabled": False,
        "permissions": [
            {"name": "terminal:write", "level": "dangerous"},
            {"name": "system:info", "level": "safe"},
        ],
    },
    {
        "id": "spotify_controller",
        "name": "Spotify Controller",
        "icon": "music_note",
        "version": "v2.1.0",
        "author": "audio_team",
        "description": "Seamless playback control and playlist management for Spotify.",
        "enabled": True,
        "permissions": [
            {"name": "media:control", "level": "safe"},
            {"name": "account:read", "level": "safe"},
        ],
    },
    {
        "id": "browser_automation",
        "name": "Browser Automation",
        "icon": "robot_2",
        "version": "v1.2.3",
        "author": "web_bot",
        "description": "Automate repetitive web tasks and data scraping.",
        "enabled": True,
        "permissions": [
            {"name": "browser:control", "level": "safe"},
            {"name": "network:access", "level": "elevated"},
        ],
    },
    {
        "id": "voice_recognition",
        "name": "Voice Recognition",
        "icon": "keyboard_voice",
        "version": "v3.0.1",
        "author": "ai_labs",
        "description": "Advanced voice-to-text processing for voice commands.",
        "enabled": True,
        "permissions": [
            {"name": "audio:record", "level": "dangerous"},
        ],
    },
]


# ── Persistence ──


def _load_state() -> tuple[RoutingConfigState, list[SkillEntry]]:
    """Load state from YAML file, falling back to defaults."""
    if not _STATE_FILE.exists():
        return _DEFAULT_ROUTING.copy(), list(_DEFAULT_SKILLS)

    try:
        raw = yaml.safe_load(_STATE_FILE.read_text(encoding="utf-8")) or {}
        routing = raw.get("routing", _DEFAULT_ROUTING)
        skills = raw.get("skills", _DEFAULT_SKILLS)
        return routing, skills
    except (yaml.YAMLError, OSError):
        logger.warning("Corrupt state file — using defaults")
        return _DEFAULT_ROUTING.copy(), list(_DEFAULT_SKILLS)


def save_state() -> None:
    """Persist current routing + skills state to YAML atomically."""
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {"routing": dict(routing_config_state), "skills": list(skills_state)}
    try:
        with NamedTemporaryFile(
            mode="w",
            dir=_STATE_FILE.parent,
            suffix=".yaml",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            yaml.safe_dump(data, tmp, default_flow_style=False, allow_unicode=True)
            tmp_path = Path(tmp.name)
        tmp_path.replace(_STATE_FILE)
    except OSError:
        logger.exception("Failed to save state")


# ── Module-level state (loaded on import) ──

_routing, _skills = _load_state()
routing_config_state: RoutingConfigState = _routing
skills_state: list[SkillEntry] = _skills
