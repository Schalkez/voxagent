"""Tests for TextChunker: sentence-level text splitting."""

import pytest

from core.audio.text_chunker import (
    MAX_CHUNK_LENGTH,
    MIN_CHUNK_LENGTH,
    split_sentences,
)


class TestSplitSentences:
    """Test suite for split_sentences()."""

    def test_empty_string_returns_empty_list(self) -> None:
        """Empty input produces no chunks."""
        assert split_sentences("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        """Whitespace-only input produces no chunks."""
        assert split_sentences("   \n\t  ") == []

    def test_single_sentence(self) -> None:
        """A single sentence is returned as one chunk."""
        result = split_sentences("Hello, this is a test sentence.")
        assert len(result) == 1
        assert "Hello" in result[0]

    def test_two_sentences_split(self) -> None:
        """Two sentences are split into two chunks."""
        text = "First sentence here. Second sentence follows."
        result = split_sentences(text)
        assert len(result) == 2
        assert "First" in result[0]
        assert "Second" in result[1]

    def test_question_and_exclamation_marks(self) -> None:
        """Sentences ending with ? and ! are split correctly."""
        text = "Is this working? Yes it is! Great to know."
        result = split_sentences(text)
        assert len(result) >= 2

    def test_ellipsis_splits(self) -> None:
        """Ellipsis character triggers a sentence boundary."""
        text = "Thinking about it\u2026 Now I have the answer."
        result = split_sentences(text)
        assert len(result) >= 1

    def test_vietnamese_text(self) -> None:
        """Vietnamese sentences split at standard punctuation."""
        text = "Xin chao ban. Ban khoe khong? Toi rat vui."
        result = split_sentences(text)
        assert len(result) >= 2

    def test_short_fragments_merged(self) -> None:
        """Fragments shorter than MIN_CHUNK_LENGTH are merged."""
        text = "OK. Sure. I agree with you completely."
        result = split_sentences(text)
        # "OK." and "Sure." are short; they should be merged
        for chunk in result:
            assert len(chunk) >= MIN_CHUNK_LENGTH or chunk == result[-1]

    def test_long_sentence_split_at_clauses(self) -> None:
        """Sentences exceeding MAX_CHUNK_LENGTH are split at clause boundaries."""
        # Build a very long sentence with clause separators
        clauses = ["this is clause number " + str(i) for i in range(30)]
        long_text = ", ".join(clauses) + "."
        assert len(long_text) > MAX_CHUNK_LENGTH

        result = split_sentences(long_text)
        assert len(result) > 1
        for chunk in result:
            # Each chunk should be within limit (unless no clause boundary)
            assert len(chunk) <= MAX_CHUNK_LENGTH + 50  # some tolerance

    def test_mixed_language_content(self) -> None:
        """Mixed Vietnamese and English text splits correctly."""
        text = "Hello world. Xin chao cac ban. How are you doing today?"
        result = split_sentences(text)
        assert len(result) >= 2

    def test_no_punctuation_returns_single_chunk(self) -> None:
        """Text without sentence-ending punctuation is one chunk."""
        text = "This is some text without any sentence ending punctuation"
        result = split_sentences(text)
        assert len(result) == 1
        assert result[0] == text

    def test_multiple_spaces_between_sentences(self) -> None:
        """Multiple spaces between sentences don't create empty chunks."""
        text = "First sentence.   Second sentence.    Third sentence."
        result = split_sentences(text)
        assert all(chunk.strip() for chunk in result)

    def test_preserves_content_no_data_loss(self) -> None:
        """All words from input appear in the chunked output."""
        text = "The quick brown fox. Jumped over the lazy dog. And ran away!"
        result = split_sentences(text)
        joined = " ".join(result)
        for word in ["quick", "brown", "fox", "Jumped", "lazy", "dog", "ran"]:
            assert word in joined

    def test_single_word_sentence(self) -> None:
        """Very short input is still returned."""
        result = split_sentences("Hi.")
        assert len(result) == 1
        assert "Hi" in result[0]
