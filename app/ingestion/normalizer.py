"""
Log normalizer.

Normalizes raw log lines by stripping ANSI codes, collapsing whitespace,
and handling multiline log entries (continuation lines joined to previous).
"""

from __future__ import annotations

import re
from typing import Generator

from app.utils.helpers import strip_ansi


# Continuation line: starts with whitespace or common continuation markers
_CONTINUATION_RE = re.compile(r"^(\s+|\t)")

# Multiple spaces collapsed to single space
_MULTI_SPACE_RE = re.compile(r"  +")

# Common timestamp patterns that mark the START of a new log entry
_TIMESTAMP_START_RE = re.compile(
    r"^("
    r"\d{4}[-/]\d{2}[-/]\d{2}"  # 2024-01-15 or 2024/01/15
    r"|[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}"  # Jan 15 10:30:45
    r"|\d{1,2}/[A-Z][a-z]{2}/\d{4}"  # 15/Jan/2024
    r"|\[\d{4}[-/]\d{2}[-/]\d{2}"  # [2024-01-15
    r"|\d{2}:\d{2}:\d{2}"  # 10:30:45
    r")"
)


def normalize_line(line: str) -> str:
    """
    Normalize a single log line.

    Operations:
    1. Strip ANSI escape codes.
    2. Replace tabs with spaces.
    3. Collapse multiple spaces to single space.
    4. Strip leading/trailing whitespace.

    Args:
        line: Raw log line.

    Returns:
        Normalized line.
    """
    line = strip_ansi(line)
    line = line.replace("\t", " ")
    line = _MULTI_SPACE_RE.sub(" ", line)
    line = line.strip()
    return line


def is_continuation_line(line: str) -> bool:
    """
    Determine if a line is a continuation of the previous log entry.

    A line is considered a continuation if:
    - It starts with whitespace AND does not look like a new timestamped entry.

    Args:
        line: Raw (un-normalized) log line.

    Returns:
        True if this line should be appended to the previous entry.
    """
    if not line or not _CONTINUATION_RE.match(line):
        return False
    # If it starts with a timestamp, it's a new entry even if indented
    stripped = line.lstrip()
    if _TIMESTAMP_START_RE.match(stripped):
        return False
    return True


def normalize_entries(
    lines: Generator[tuple[int, str], None, None],
) -> Generator[tuple[int, str], None, None]:
    """
    Normalize and merge multiline log entries.

    Continuation lines (starting with whitespace, no timestamp) are
    appended to the previous entry with a space separator.

    Args:
        lines: Generator of (line_number, raw_line) from reader.

    Yields:
        (line_number, normalized_merged_entry) — line_number is the
        line number of the FIRST line in the merged entry.
    """
    current_line_num: int | None = None
    current_entry: str | None = None

    for line_num, raw_line in lines:
        if is_continuation_line(raw_line):
            # Append to current entry
            if current_entry is not None:
                normalized = normalize_line(raw_line)
                if normalized:
                    current_entry += " " + normalized
            else:
                # Continuation without a preceding entry — treat as new
                current_line_num = line_num
                current_entry = normalize_line(raw_line)
        else:
            # Yield previous entry if it exists
            if current_entry is not None and current_line_num is not None:
                yield current_line_num, current_entry
            # Start new entry
            current_line_num = line_num
            current_entry = normalize_line(raw_line)

    # Yield final entry
    if current_entry is not None and current_line_num is not None:
        yield current_line_num, current_entry
