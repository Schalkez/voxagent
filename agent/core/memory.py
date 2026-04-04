"""MEMORY module: SQLite storage for conversations and preferences.

Uses aiosqlite for async database access. Database schema is versioned
for safe migrations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import aiosqlite

logger = logging.getLogger("voxagent.memory")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    session_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);
"""


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
    """Manages SQLite database for conversation history and preferences.

    Provides async methods for storing and retrieving conversation history,
    user preferences, and per-skill state. Database schema is versioned
    for safe migrations.
    """

    SCHEMA_VERSION = 1

    def __init__(self) -> None:
        """Initialize the Memory module."""
        self._connected = False
        self._db: aiosqlite.Connection | None = None

    async def connect(self, db_path: str) -> None:
        """Open database connection, creating schema if needed.

        Args:
            db_path: Filesystem path to the SQLite database file.
        """
        db_dir = Path(db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self._db = await aiosqlite.connect(db_path)
        self._db.row_factory = aiosqlite.Row

        await self._db.executescript(_SCHEMA_SQL)

        # Ensure version record exists
        async with self._db.execute("SELECT COUNT(*) FROM schema_version") as cursor:
            row = await cursor.fetchone()
            if row is not None and row[0] == 0:
                await self._db.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (self.SCHEMA_VERSION,),
                )

        await self._db.commit()
        self._connected = True
        logger.info("Memory connected: %s", db_path)

    async def close(self) -> None:
        """Close database connection and release resources."""
        if self._db is not None:
            await self._db.close()
            self._db = None
        self._connected = False
        logger.info("Memory connection closed")

    async def add_conversation(self, entry: ConversationEntry) -> None:
        """Store a conversation entry in the database.

        Args:
            entry: The conversation turn to persist.
        """
        if self._db is None:
            return

        await self._db.execute(
            "INSERT INTO conversations (role, content, timestamp, session_id) VALUES (?, ?, ?, ?)",
            (entry.role, entry.content, entry.timestamp.isoformat(), entry.session_id),
        )
        await self._db.commit()

    async def get_recent_conversations(self, limit: int = 10) -> list[ConversationEntry]:
        """Retrieve the most recent conversation entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of ConversationEntry, most recent first.
        """
        if self._db is None:
            return []

        async with self._db.execute(
            "SELECT role, content, timestamp, session_id "
            "FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [
            ConversationEntry(
                role=row[0],
                content=row[1],
                timestamp=datetime.fromisoformat(row[2]),
                session_id=row[3],
            )
            for row in rows
        ]

    async def set_preference(self, key: str, value: str) -> None:
        """Store or update a user preference.

        Args:
            key: Preference key (e.g., 'default_voice', 'language').
            value: Preference value.
        """
        if self._db is None:
            return

        await self._db.execute(
            "INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)",
            (key, value),
        )
        await self._db.commit()

    async def get_preference(self, key: str, default: str | None = None) -> str | None:
        """Retrieve a user preference.

        Args:
            key: Preference key to look up.
            default: Value to return if key not found.

        Returns:
            The preference value, or default if not set.
        """
        if self._db is None:
            return default

        async with self._db.execute(
            "SELECT value FROM preferences WHERE key = ?",
            (key,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return default
        return str(row[0])

    async def get_conversation_count(self) -> int:
        """Get total number of conversation entries.

        Returns:
            Number of stored conversation entries.
        """
        if self._db is None:
            return 0

        async with self._db.execute("SELECT COUNT(*) FROM conversations") as cursor:
            row = await cursor.fetchone()

        return int(row[0]) if row is not None else 0
