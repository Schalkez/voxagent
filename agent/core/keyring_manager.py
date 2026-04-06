"""Keyring-based API key management for VoxAgent providers.

Stores and retrieves API keys securely using the OS credential manager
(Windows Credential Locker, macOS Keychain, Linux SecretService).
"""

from __future__ import annotations

import keyring

SERVICE_NAME = "voxagent"

# Known cloud providers that require API keys
CLOUD_PROVIDERS = ("openai", "groq", "anthropic", "gemini", "deepseek", "mistral", "openrouter")


def save_key(provider: str, api_key: str) -> None:
    """Save an API key to the OS keyring.

    Args:
        provider: Provider identifier (e.g., 'openai', 'groq').
        api_key: The API key to store securely.
    """
    keyring.set_password(SERVICE_NAME, provider, api_key)


def get_key(provider: str) -> str | None:
    """Retrieve an API key from the OS keyring.

    Args:
        provider: Provider identifier.

    Returns:
        The stored API key, or None if not found.
    """
    return keyring.get_password(SERVICE_NAME, provider)


def delete_key(provider: str) -> None:
    """Remove an API key from the OS keyring.

    Args:
        provider: Provider identifier.

    Raises:
        keyring.errors.PasswordDeleteError: If the key does not exist.
    """
    keyring.delete_password(SERVICE_NAME, provider)


def list_provider_keys() -> dict[str, bool]:
    """Check which cloud providers have API keys stored.

    Returns:
        Dict mapping provider name to whether a key exists.
    """
    return {name: get_key(name) is not None for name in CLOUD_PROVIDERS}
