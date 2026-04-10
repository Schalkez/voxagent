"""MEMORY module: SQLite storage for conversations and preferences.

Uses aiosqlite for async database access. Database schema is versioned
for safe migrations. Includes auto-prune for bounded growth with
configurable TTL.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite

logger = logging.getLogger("voxagent.memory")

# ── Constants ──

DEFAULT_CONVERSATION_TTL_DAYS = 30
MIN_CONVERSATION_TTL_DAYS = 1
MAX_CONVERSATIONS_LIMIT = 100_000

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

CREATE TABLE IF NOT EXISTS skill_state (
    skill_name TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (skill_name, key)
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

    async def set_skill_state(self, skill_name: str, key: str, value: str) -> None:
        """Store a skill-specific state value.

        Args:
            skill_name: Name of the skill.
            key: State key.
            value: State value.
        """
        if self._db is None:
            return

        await self._db.execute(
            "INSERT OR REPLACE INTO skill_state (skill_name, key, value) VALUES (?, ?, ?)",
            (skill_name, key, value),
        )
        await self._db.commit()

    async def get_skill_state(self, skill_name: str, key: str, default: str | None = None) -> str | None:
        """Retrieve a skill-specific state value.

        Args:
            skill_name: Name of the skill.
            key: State key.
            default: Fallback if not found.

        Returns:
            The stored value, or default if not set.
        """
        if self._db is None:
            return default

        async with self._db.execute(
            "SELECT value FROM skill_state WHERE skill_name = ? AND key = ?",
            (skill_name, key),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return default
        return str(row[0])

    async def get_all_skill_state(self, skill_name: str) -> dict[str, str]:
        """Retrieve all state entries for a skill.

        Args:
            skill_name: Name of the skill.

        Returns:
            Dict of key-value pairs for the skill.
        """
        if self._db is None:
            return {}

        async with self._db.execute(
            "SELECT key, value FROM skill_state WHERE skill_name = ?",
            (skill_name,),
        ) as cursor:
            rows = await cursor.fetchall()

        return {str(row[0]): str(row[1]) for row in rows}

    async def prune_old_conversations(
        self,
        ttl_days: int = DEFAULT_CONVERSATION_TTL_DAYS,
    ) -> int:
        """Delete conversations older than the TTL threshold.

        Only deletes records older than the safe horizon. Never touches
        conversations from the current day to avoid breaking active
        context windows.

        Args:
            ttl_days: Number of days to retain conversations.
                Must be >= MIN_CONVERSATION_TTL_DAYS.

        Returns:
            Number of deleted conversation entries.
        """
        if self._db is None:
            return 0

        ttl_days = max(ttl_days, MIN_CONVERSATION_TTL_DAYS)
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=ttl_days)
        cutoff_iso = cutoff.isoformat()

        cursor = await self._db.execute(
            "DELETE FROM conversations WHERE timestamp < ?",
            (cutoff_iso,),
        )
        deleted = cursor.rowcount
        await self._db.commit()

        if deleted > 0:
            logger.info(
                "Pruned %d old conversations (older than %d days)",
                deleted,
                ttl_days,
            )

        return deleted

    async def enforce_max_conversations(
        self,
        max_count: int = MAX_CONVERSATIONS_LIMIT,
    ) -> int:
        """Enforce an upper bound on total conversation count.

        Deletes the oldest entries when the total exceeds max_count.

        Args:
            max_count: Maximum number of conversations to retain.

        Returns:
            Number of deleted conversation entries.
        """
        if self._db is None:
            return 0

        total = await self.get_conversation_count()
        if total <= max_count:
            return 0

        excess = total - max_count
        cursor = await self._db.execute(
            "DELETE FROM conversations WHERE id IN "
            "(SELECT id FROM conversations ORDER BY id ASC LIMIT ?)",
            (excess,),
        )
        deleted = cursor.rowcount
        await self._db.commit()

        if deleted > 0:
            logger.info(
                "Enforced max conversations: deleted %d (limit=%d)",
                deleted,
                max_count,
            )

        return deleted

    async def auto_prune(
        self,
        ttl_days: int = DEFAULT_CONVERSATION_TTL_DAYS,
        max_count: int = MAX_CONVERSATIONS_LIMIT,
    ) -> int:
        """Run all pruning strategies for bounded growth.

        Combines TTL-based pruning and count-based pruning.

        Args:
            ttl_days: Number of days to retain conversations.
            max_count: Maximum number of conversations to retain.

        Returns:
            Total number of deleted conversation entries.
        """
        deleted_ttl = await self.prune_old_conversations(ttl_days)
        deleted_cap = await self.enforce_max_conversations(max_count)
        return deleted_ttl + deleted_cap
