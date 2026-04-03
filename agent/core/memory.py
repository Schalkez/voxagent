"""MEMORY module: Encrypted SQLite storage for conversations and preferences.

Uses aiosqlite for async database access. In production, the database
is encrypted with SQLCipher, with the encryption key stored in the
OS keyring (Keychain on macOS, Credential Manager on Windows, libsecret on Linux).
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ConversationEntry:
    """A single conversation turn stored in memory.

    Attributes:
        role: Speaker role ('user' or 'assistant').
        content: The text content of the message.
        timestamp: When the message was recorded.
        session_id: ID of the conversation session.
    """

    role: str
    content: str
    timestamp: datetime
    session_id: str


class Memory:
    """Manages encrypted SQLite database for conversation history and preferences.

    Provides async methods for storing and retrieving conversation history,
    user preferences, and per-skill state. Database schema is versioned
    for safe migrations.
    """

    SCHEMA_VERSION = 1

    def __init__(self) -> None:
        """Initialize the Memory module."""
        self._connected = False

    async def connect(self, db_path: str) -> None:
        """Open database connection, creating schema if needed.

        Args:
            db_path: Filesystem path to the SQLite database file.
        """
        self._connected = True

    async def close(self) -> None:
        """Close database connection and release resources."""
        self._connected = False

    async def add_conversation(self, entry: ConversationEntry) -> None:
        """Store a conversation entry in the database.

        Args:
            entry: The conversation turn to persist.
        """

    async def get_recent_conversations(self, limit: int = 10) -> list[ConversationEntry]:
        """Retrieve the most recent conversation entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of ConversationEntry, most recent first.
        """
        return []

    async def set_preference(self, key: str, value: str) -> None:
        """Store or update a user preference.

        Args:
            key: Preference key (e.g., 'default_voice', 'language').
            value: Preference value.
        """

    async def get_preference(self, key: str, default: str | None = None) -> str | None:
        """Retrieve a user preference.

        Args:
            key: Preference key to look up.
            default: Value to return if key not found.

        Returns:
            The preference value, or default if not set.
        """
        return default
