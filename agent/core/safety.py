"""Prompt injection detection and sanitization.

Protects VoxAgent from prompt injection attacks by detecting
common injection patterns and sanitizing user input before
it reaches the LLM providers.
"""

from __future__ import annotations

import re

# ── Injection Patterns ──
# Each pattern targets a known prompt injection technique.

INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?)", re.IGNORECASE),
        "Attempted to override system instructions",
    ),
    (
        re.compile(r"disregard\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|prompts?|rules?)", re.IGNORECASE),
        "Attempted to disregard system instructions",
    ),
    (
        re.compile(r"forget\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|context|prompts?)", re.IGNORECASE),
        "Attempted to erase system context",
    ),
    (
        re.compile(r"you\s+are\s+now\s+(a|an|the)\s+", re.IGNORECASE),
        "Attempted role reassignment",
    ),
    (
        re.compile(r"act\s+as\s+(a|an|if)\s+", re.IGNORECASE),
        "Attempted role reassignment via act-as",
    ),
    (
        re.compile(r"pretend\s+(you\s+are|to\s+be)\s+", re.IGNORECASE),
        "Attempted role reassignment via pretend",
    ),
    (
        re.compile(r"system\s*:\s*", re.IGNORECASE),
        "Attempted system message injection",
    ),
    (
        re.compile(r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>", re.IGNORECASE),
        "Attempted template injection (Llama format)",
    ),
    (
        re.compile(r"<\|im_start\|>|<\|im_end\|>", re.IGNORECASE),
        "Attempted template injection (ChatML format)",
    ),
    (
        re.compile(r"BEGININSTRUCTION|ENDINSTRUCTION", re.IGNORECASE),
        "Attempted delimiter injection",
    ),
    (
        re.compile(r"override\s+(safety|security|content)\s+(filter|policy|guidelines?)", re.IGNORECASE),
        "Attempted safety override",
    ),
    (
        re.compile(r"jailbreak|DAN\s*mode|developer\s*mode|unrestricted\s*mode", re.IGNORECASE),
        "Attempted jailbreak keyword",
    ),
    (
        re.compile(r"reveal\s+(your|the|system)\s+(prompt|instructions?|rules?)", re.IGNORECASE),
        "Attempted to extract system prompt",
    ),
    (
        re.compile(
            r"(show|tell|reveal|display|repeat|what).*system\s+prompt", re.IGNORECASE
        ),
        "Attempted to extract system prompt",
    ),
    (
        re.compile(r"print\s+(your|the|system)\s+(prompt|instructions?|initial)", re.IGNORECASE),
        "Attempted to print system prompt",
    ),
    (
        re.compile(r"output\s+(your|the)\s+(system|initial)\s+(prompt|message)", re.IGNORECASE),
        "Attempted to output system prompt",
    ),
]

# Patterns to strip from input (less aggressive — used in sanitize)
_STRIP_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"<\|im_start\|>.*?<\|im_end\|>", re.IGNORECASE | re.DOTALL),
    re.compile(r"\[INST\].*?\[/INST\]", re.IGNORECASE | re.DOTALL),
    re.compile(r"<<SYS>>.*?<</SYS>>", re.IGNORECASE | re.DOTALL),
    re.compile(r"system\s*:\s*[^\n]+", re.IGNORECASE),
]

# Maximum input length to prevent resource exhaustion
MAX_INPUT_LENGTH = 10000


class PromptGuard:
    """Detects and blocks prompt injection attempts.

    Uses regex-based pattern matching to identify common injection
    techniques in user input text. Designed to be fast enough for
    real-time voice command processing.
    """

    def check(self, text: str) -> tuple[bool, str]:
        """Check if text contains prompt injection attempts.

        Args:
            text: User input text to validate.

        Returns:
            Tuple of (is_safe, reason). is_safe is True if no
            injection detected; reason explains the rejection.
        """
        if not text:
            return True, ""

        if len(text) > MAX_INPUT_LENGTH:
            return False, f"Input exceeds maximum length ({MAX_INPUT_LENGTH} chars)"

        for pattern, reason in INJECTION_PATTERNS:
            if pattern.search(text):
                return False, reason

        return True, ""

    def sanitize(self, text: str) -> str:
        """Strip dangerous patterns from text while preserving intent.

        Use this for inputs that should still be processed but with
        dangerous elements removed (e.g., OCR text from screen).

        Args:
            text: Input text to sanitize.

        Returns:
            Sanitized text with injection patterns removed.
        """
        if not text:
            return text

        result = text[:MAX_INPUT_LENGTH]

        for pattern in _STRIP_PATTERNS:
            result = pattern.sub("", result)

        # Collapse excessive whitespace left by removals
        result = re.sub(r"\n{3,}", "\n\n", result)
        return result.strip()
