"""Tests for the Memory database module."""

from datetime import datetime

import pytest

from core.memory import ConversationEntry, Memory


@pytest.fixture
async def memory(tmp_path):
    """Create a Memory instance connected to a temporary database."""
    db_path = str(tmp_path / "test_memory.db")
    mem = Memory()
    await mem.connect(db_path)
    yield mem
    await mem.close()


class TestMemoryConnection:
    """Test database connection lifecycle."""

    @pytest.mark.asyncio
    async def test_connect_creates_tables(self, tmp_path) -> None:
        """connect() should create the database schema."""
        mem = Memory()
        db_path = str(tmp_path / "new.db")
        await mem.connect(db_path)
        assert mem._connected is True
        await mem.close()

    @pytest.mark.asyncio
    async def test_close_disconnects(self, tmp_path) -> None:
        """close() should release the database connection."""
        mem = Memory()
        await mem.connect(str(tmp_path / "close_test.db"))
        await mem.close()
        assert mem._connected is False

    @pytest.mark.asyncio
    async def test_operations_without_connection(self) -> None:
        """Operations should be safe to call without a connection."""
        mem = Memory()
        result = await mem.get_recent_conversations()
        assert result == []

        pref = await mem.get_preference("key", "default")
        assert pref == "default"


class TestConversations:
    """Test conversation CRUD operations."""

    @pytest.mark.asyncio
    async def test_add_and_retrieve(self, memory: Memory) -> None:
        """Should store and retrieve conversation entries."""
        entry = ConversationEntry(
            role="user",
            content="Mở Chrome đi",
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            session_id="test-session",
        )
        await memory.add_conversation(entry)

        results = await memory.get_recent_conversations(limit=10)
        assert len(results) == 1
        assert results[0].role == "user"
        assert results[0].content == "Mở Chrome đi"
        assert results[0].session_id == "test-session"

    @pytest.mark.asyncio
    async def test_recent_conversations_limit(self, memory: Memory) -> None:
        """Should respect the limit parameter."""
        for i in range(5):
            entry = ConversationEntry(
                role="user",
                content=f"Message {i}",
                timestamp=datetime(2024, 1, 1, 12, i, 0),
                session_id="test",
            )
            await memory.add_conversation(entry)

        results = await memory.get_recent_conversations(limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_recent_conversations_ordered(self, memory: Memory) -> None:
        """Should return most recent conversations first."""
        for i in range(3):
            entry = ConversationEntry(
                role="user",
                content=f"Message {i}",
                timestamp=datetime(2024, 1, 1, 12, i, 0),
                session_id="test",
            )
            await memory.add_conversation(entry)

        results = await memory.get_recent_conversations(limit=10)
        assert results[0].content == "Message 2"  # Most recent

    @pytest.mark.asyncio
    async def test_conversation_count(self, memory: Memory) -> None:
        """Should count total conversations."""
        assert await memory.get_conversation_count() == 0

        entry = ConversationEntry(
            role="user", content="Test", timestamp=datetime.now(), session_id="s"
        )
        await memory.add_conversation(entry)
        assert await memory.get_conversation_count() == 1


class TestPreferences:
    """Test preference CRUD operations."""

    @pytest.mark.asyncio
    async def test_set_and_get(self, memory: Memory) -> None:
        """Should store and retrieve preferences."""
        await memory.set_preference("language", "vi")
        result = await memory.get_preference("language")
        assert result == "vi"

    @pytest.mark.asyncio
    async def test_get_missing_returns_default(self, memory: Memory) -> None:
        """Should return default for missing keys."""
        result = await memory.get_preference("nonexistent", "fallback")
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_update_existing(self, memory: Memory) -> None:
        """Should update existing preferences."""
        await memory.set_preference("voice", "vi-female")
        await memory.set_preference("voice", "en-male")
        result = await memory.get_preference("voice")
        assert result == "en-male"


class TestConversationEntry:
    """Test ConversationEntry dataclass."""

    def test_is_frozen(self) -> None:
        """ConversationEntry should be immutable."""
        entry = ConversationEntry(
            role="user",
            content="test",
            timestamp=datetime.now(),
            session_id="s",
        )
        with pytest.raises(AttributeError):
            entry.role = "assistant"  # type: ignore[misc]
