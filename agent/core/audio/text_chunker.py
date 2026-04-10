"""TextChunker: Split text at sentence boundaries for streaming TTS.

Handles both Vietnamese and English sentence boundaries. Produces
sentence-sized chunks suitable for individual TTS synthesis calls,
enabling the streaming pipeline to start playback before the full
response is synthesized.
"""

from __future__ import annotations

import re

from core.logging import get_logger

logger = get_logger(module="text_chunker")

# ── Constants ────────────────────────────────────────────────────────────────

# Sentence-ending punctuation: standard + Vietnamese-relevant marks
_SENTENCE_PATTERN = re.compile(
    r"(?<=[.!?\u2026])"  # Lookbehind: period, exclamation, question, ellipsis
    r"(?:\s+|$)"  # Followed by whitespace or end-of-string
)

# Minimum chunk length to avoid micro-chunks (e.g. "OK." alone)
MIN_CHUNK_LENGTH = 10

# Maximum chunk length before force-splitting at clause boundaries
MAX_CHUNK_LENGTH = 300

# Secondary split pattern for long sentences (clause-level)
_CLAUSE_PATTERN = re.compile(
    r"(?<=[,;:\u2014\u2013])"  # Lookbehind: comma, semicolon, colon, em/en dash
    r"\s+"
)


def split_sentences(text: str) -> list[str]:
    """Split text into sentence-level chunks for streaming TTS.

    Processing order:
    1. Split at sentence boundaries (. ! ? ...)
    2. Merge short fragments into neighbors
    3. Split oversized chunks at clause boundaries

    Handles Vietnamese text (which uses the same sentence-ending
    punctuation as English) and mixed-language content.

    Args:
        text: Input text to split.

    Returns:
        List of sentence chunks, each suitable for one TTS call.
        Empty list if text is empty/whitespace.
    """
    stripped = text.strip()
    if not stripped:
        return []

    raw_chunks = _split_at_sentences(stripped)
    merged = _merge_short_chunks(raw_chunks)
    final = _split_long_chunks(merged)

    logger.debug("chunked text", input_len=len(stripped), chunks=len(final))
    return final


def _split_at_sentences(text: str) -> list[str]:
    """Split text at sentence-ending punctuation.

    Args:
        text: Non-empty text string.

    Returns:
        List of raw sentence fragments.
    """
    parts = _SENTENCE_PATTERN.split(text)
    return [p.strip() for p in parts if p.strip()]


def _merge_short_chunks(chunks: list[str]) -> list[str]:
    """Merge fragments shorter than MIN_CHUNK_LENGTH with their neighbor.

    Args:
        chunks: List of raw sentence fragments.

    Returns:
        Merged list where no fragment is unreasonably short.
    """
    if len(chunks) <= 1:
        return chunks

    merged: list[str] = []
    buffer = ""

    for chunk in chunks:
        if buffer:
            buffer = f"{buffer} {chunk}"
        else:
            buffer = chunk

        if len(buffer) >= MIN_CHUNK_LENGTH:
            merged.append(buffer)
            buffer = ""

    # Flush remaining buffer
    if buffer:
        if merged:
            merged[-1] = f"{merged[-1]} {buffer}"
        else:
            merged.append(buffer)

    return merged


def _split_long_chunks(chunks: list[str]) -> list[str]:
    """Split chunks exceeding MAX_CHUNK_LENGTH at clause boundaries.

    Args:
        chunks: List of merged sentence chunks.

    Returns:
        Final list with no chunk exceeding MAX_CHUNK_LENGTH
        (unless no clause boundary exists).
    """
    result: list[str] = []

    for chunk in chunks:
        if len(chunk) <= MAX_CHUNK_LENGTH:
            result.append(chunk)
            continue

        sub_parts = _CLAUSE_PATTERN.split(chunk)
        sub_parts = [p.strip() for p in sub_parts if p.strip()]

        # Re-merge clause fragments to stay under MAX_CHUNK_LENGTH
        buffer = ""
        for part in sub_parts:
            candidate = f"{buffer} {part}".strip() if buffer else part
            if len(candidate) > MAX_CHUNK_LENGTH and buffer:
                result.append(buffer)
                buffer = part
            else:
                buffer = candidate

        if buffer:
            result.append(buffer)

    return result
