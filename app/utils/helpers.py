"""
Utility helpers for the log analyzer.

Common functions used across modules.
"""

from __future__ import annotations

import re
from typing import Optional


# Pre-compiled regex for ANSI escape codes
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from a string."""
    return _ANSI_ESCAPE_RE.sub("", text)


def safe_strip(text: Optional[str]) -> str:
    """Strip whitespace safely, returning empty string for None."""
    if text is None:
        return ""
    return text.strip()


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp a numeric value between min and max."""
    return max(min_val, min(max_val, value))


def truncate(text: str, max_length: int = 500) -> str:
    """Truncate text to max_length, appending '...' if truncated."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
