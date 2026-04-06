"""In-Memory State Store for API.

Will be replaced by a proper database or file persistent storage mapping later.
"""

from typing import Any

# Provider Metadata
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


# Routing State
routing_config_state: dict[str, Any] = {
    "preset": "balanced",
    "tiers": [
        {
            "tier": 1,
            "title": "Tier 1 (Speed & Simple)",
            "description": "Fastest. Used for simple intents, parsing, and extraction.",
            "provider": "Groq",
            "model": "llama-3.1-8b-instant",
            "provider_options": ["Groq", "OpenAI", "Mistral"],
            "model_options": ["llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma-7b-it"],
        },
        {
            "tier": 2,
            "title": "Tier 2 (Reasoning)",
            "description": "Balanced. Used for logic, file management, and multi-step plans.",
            "provider": "Ollama",
            "model": "qwen2.5:7b",
            "provider_options": ["Ollama", "Azure AI", "AWS Bedrock"],
            "model_options": ["qwen2.5:7b", "llama3:8b-instruct", "mistral-v0.3"],
        },
        {
            "tier": 3,
            "title": "Tier 3 (Complex & Vision)",
            "description": "Heavy lifting. Used for code review, screen reading, and complex problem solving.",
            "provider": "Anthropic",
            "model": "claude-3-5-sonnet",
            "provider_options": ["Anthropic", "Google Vertex", "OpenAI"],
            "model_options": ["claude-3-5-sonnet", "gpt-4o-2024-08-06", "gemini-1.5-pro"],
            "warning": "High Cost",
        },
    ],
    "status": "Optimized for latency",
}


# Skills State
skills_state: list[dict[str, Any]] = [
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
