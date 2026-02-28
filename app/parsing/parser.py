"""
Log parser — extracts structured data from raw log lines.

Auto-detects log format, then parses each line into a LogEntry.
Unknown patterns produce entries with log_type = "UNCLASSIFIED".
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional

from app.config.settings import DEFAULT_CONFIG, ParsingConfig
from app.parsing.patterns import (
    PATTERN_REGISTRY,
    LogPattern,
    JSON_LOG_PATTERN,
)
from models.schemas import LogEntry, LogLevel


# ─── Level Normalization ────────────────────────────────────────────────

_LEVEL_MAP: dict[str, LogLevel] = {
    "debug": LogLevel.DEBUG,
    "info": LogLevel.INFO,
    "information": LogLevel.INFO,
    "notice": LogLevel.INFO,
    "verbose": LogLevel.DEBUG,
    "warn": LogLevel.WARNING,
    "warning": LogLevel.WARNING,
    "error": LogLevel.ERROR,
    "err": LogLevel.ERROR,
    "critical": LogLevel.CRITICAL,
    "crit": LogLevel.CRITICAL,
    "fatal": LogLevel.CRITICAL,
    "alert": LogLevel.CRITICAL,
    "emerg": LogLevel.CRITICAL,
}


def normalize_log_level(raw_level: Optional[str]) -> LogLevel:
    """Map a raw log level string to the standardized LogLevel enum."""
    if raw_level is None:
        return LogLevel.UNKNOWN
    return _LEVEL_MAP.get(raw_level.strip().lower(), LogLevel.UNKNOWN)


# ─── Timestamp Parsing ──────────────────────────────────────────────────

_TIMESTAMP_FORMATS = [
    "%Y-%m-%d %H:%M:%S,%f",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%b %d %H:%M:%S",
    "%d/%b/%Y:%H:%M:%S %z",
    "%m/%d/%Y %I:%M:%S %p",
]


def parse_timestamp(raw_ts: Optional[str]) -> Optional[datetime]:
    """
    Parse a timestamp string into a datetime object.

    Tries multiple known formats. Returns None if parsing fails.
    Does NOT hallucinate timestamps — if unparseable, returns None.
    """
    if raw_ts is None:
        return None

    raw_ts = raw_ts.strip()

    # Handle trailing 'Z' (UTC marker)
    if raw_ts.endswith("Z"):
        raw_ts = raw_ts[:-1]

    for fmt in _TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(raw_ts, fmt)
        except ValueError:
            continue

    return None


# ─── Log Type Detection ─────────────────────────────────────────────────

def detect_log_type(
    sample_lines: list[str],
    config: Optional[ParsingConfig] = None,
) -> Optional[LogPattern]:
    """
    Auto-detect log format by testing sample lines against all patterns.

    Returns the pattern that matches the most lines.
    Returns None if no pattern matches a majority.

    Args:
        sample_lines: First N lines from the log file.
        config: Parsing config override.

    Returns:
        Best-matching LogPattern, or None.
    """
    if not sample_lines:
        return None

    match_counts: dict[str, int] = {}

    for line in sample_lines:
        for pattern in PATTERN_REGISTRY:
            if pattern.regex.match(line):
                match_counts[pattern.name] = match_counts.get(pattern.name, 0) + 1
                break  # First match wins (patterns ordered by specificity)

    if not match_counts:
        return None

    best_name = max(match_counts, key=match_counts.get)  # type: ignore
    best_count = match_counts[best_name]

    # Require at least 30% of sample lines to match
    if best_count < max(1, len(sample_lines) * 0.3):
        return None

    for pattern in PATTERN_REGISTRY:
        if pattern.name == best_name:
            return pattern

    return None


# ─── JSON Log Parsing ───────────────────────────────────────────────────

_JSON_LEVEL_KEYS = ("level", "log_level", "severity", "loglevel")
_JSON_MESSAGE_KEYS = ("message", "msg", "text", "log")
_JSON_TIMESTAMP_KEYS = ("timestamp", "time", "datetime", "ts", "@timestamp")
_JSON_SOURCE_KEYS = ("source", "logger", "module", "service", "component")


def _parse_json_entry(line: str, line_number: int) -> Optional[LogEntry]:
    """Parse a JSON-structured log line into a LogEntry."""
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(data, dict):
        return None

    # Extract fields by trying multiple key names
    raw_level = None
    for key in _JSON_LEVEL_KEYS:
        if key in data:
            raw_level = str(data[key])
            break

    message = ""
    for key in _JSON_MESSAGE_KEYS:
        if key in data:
            message = str(data[key])
            break

    raw_ts = None
    for key in _JSON_TIMESTAMP_KEYS:
        if key in data:
            raw_ts = str(data[key])
            break

    source = ""
    for key in _JSON_SOURCE_KEYS:
        if key in data:
            source = str(data[key])
            break

    return LogEntry(
        raw=line,
        line_number=line_number,
        timestamp=parse_timestamp(raw_ts),
        log_level=normalize_log_level(raw_level),
        message=message or line,
        source=source,
        ip_address=data.get("ip") or data.get("remote_addr"),
        username=data.get("username") or data.get("user"),
        error_code=data.get("error_code") or data.get("status"),
        log_type="json",
    )


# ─── Regex-Based Parsing ────────────────────────────────────────────────

# IP regex for extraction from message body when not captured by pattern
_IP_RE = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")

# Error code patterns in messages
_ERROR_CODE_RE = re.compile(
    r"\b(?:error|err|code|status)[:\s#=]+([A-Z0-9_-]+)\b",
    re.IGNORECASE,
)


def _extract_ip_from_message(message: str) -> Optional[str]:
    """Extract first IP address from a message string."""
    match = _IP_RE.search(message)
    return match.group(1) if match else None


def _extract_error_code_from_message(message: str) -> Optional[str]:
    """Extract an error code pattern from a message string."""
    match = _ERROR_CODE_RE.search(message)
    return match.group(1) if match else None


def parse_line(
    line: str,
    line_number: int,
    pattern: Optional[LogPattern] = None,
) -> LogEntry:
    """
    Parse a single log line into a LogEntry.

    If a pattern is provided, use it. Otherwise, try all patterns.
    If no pattern matches, returns an UNCLASSIFIED entry.

    Args:
        line: Normalized log line.
        line_number: 1-indexed line number from the source file.
        pattern: Optional pre-detected pattern to use.

    Returns:
        LogEntry with extracted fields.
    """
    # Try JSON first if it looks like JSON
    if line.lstrip().startswith("{"):
        json_entry = _parse_json_entry(line, line_number)
        if json_entry is not None:
            return json_entry

    # Try specific pattern or all patterns
    patterns_to_try = [pattern] if pattern else PATTERN_REGISTRY

    for pat in patterns_to_try:
        if pat is None or pat.name == "json":
            continue  # Skip JSON pattern in regex loop

        match = pat.regex.match(line)
        if match is None:
            continue

        groups = match.groupdict()

        # Extract standard fields
        raw_ts = groups.get("timestamp")
        raw_level = groups.get("log_level")
        message = groups.get("message", line)
        source = groups.get("source") or groups.get("process", "")
        ip = groups.get("ip")
        username = groups.get("username")
        error_code = groups.get("error_code") or groups.get("status")

        # Derive HTTP status as error code for access logs
        if error_code is None and "status" in groups:
            status = groups["status"]
            if status and int(status) >= 400:
                error_code = status

        # Try to extract IP from message if not in pattern
        if ip is None and message:
            ip = _extract_ip_from_message(message)

        # Try to extract error code from message if not in pattern
        if error_code is None and message:
            error_code = _extract_error_code_from_message(message)

        # Filter out placeholder usernames
        if username in ("-", "", None):
            username = None

        return LogEntry(
            raw=line,
            line_number=line_number,
            timestamp=parse_timestamp(raw_ts),
            log_level=normalize_log_level(raw_level),
            message=message or line,
            source=source,
            ip_address=ip,
            username=username,
            error_code=error_code,
            log_type=pat.name,
        )

    # No pattern matched — UNCLASSIFIED (anti-hallucination: never guess)
    return LogEntry(
        raw=line,
        line_number=line_number,
        message=line,
        log_type="UNCLASSIFIED",
    )


def parse_log_entries(
    lines: list[tuple[int, str]] | None = None,
    lines_iter=None,
    config: Optional[ParsingConfig] = None,
) -> list[LogEntry]:
    """
    Parse a collection of log lines into LogEntry objects.

    Auto-detects log format from the first N lines, then parses all entries.

    Args:
        lines: List of (line_number, normalized_line) tuples.
        lines_iter: Alternative — generator of (line_number, line) tuples.
                    If provided, lines is consumed from this generator.
        config: Parsing config override.

    Returns:
        List of LogEntry objects.
    """
    cfg = config or DEFAULT_CONFIG.parsing

    # Collect lines if given an iterator
    if lines is None and lines_iter is not None:
        lines = list(lines_iter)
    elif lines is None:
        return []

    if not lines:
        return []

    # Auto-detect format from sample
    sample_texts = [text for _, text in lines[:cfg.auto_detect_sample_lines]]
    detected_pattern = detect_log_type(sample_texts, cfg)

    # Parse all lines
    entries: list[LogEntry] = []
    for line_num, text in lines:
        # Truncate very long lines
        if len(text) > cfg.max_line_length:
            text = text[:cfg.max_line_length]

        entry = parse_line(text, line_num, detected_pattern)
        entries.append(entry)

    return entries
