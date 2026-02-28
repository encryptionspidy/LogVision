"""
JSON log reader — parses structured JSON log files.

Supports:
- JSON Lines format (one JSON object per line)
- JSON array format (array of objects)
- Common structured logging formats (Bunyan, Pino, generic)

Maps JSON fields to LogEntry schema using configurable field mappings.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from models.schemas import LogEntry, LogLevel

logger = logging.getLogger(__name__)

# Common field name mappings for popular JSON log formats
_FIELD_MAPPINGS = {
    "timestamp": ["timestamp", "time", "ts", "@timestamp", "date", "datetime"],
    "level": ["level", "severity", "log_level", "lvl", "loglevel"],
    "message": ["message", "msg", "text", "log", "body"],
    "source": ["source", "logger", "name", "module", "component", "service"],
    "hostname": ["hostname", "host", "server"],
}

# Level normalization
_LEVEL_MAP = {
    "trace": LogLevel.DEBUG,
    "debug": LogLevel.DEBUG,
    "info": LogLevel.INFO,
    "information": LogLevel.INFO,
    "warn": LogLevel.WARNING,
    "warning": LogLevel.WARNING,
    "error": LogLevel.ERROR,
    "err": LogLevel.ERROR,
    "critical": LogLevel.CRITICAL,
    "fatal": LogLevel.CRITICAL,
    "emergency": LogLevel.CRITICAL,
    "alert": LogLevel.CRITICAL,
}


def _find_field(obj: dict, candidates: list[str]) -> Optional[str]:
    """Find the first matching field name in a JSON object."""
    for name in candidates:
        if name in obj:
            return name
        # Case-insensitive fallback
        for key in obj:
            if key.lower() == name.lower():
                return key
    return None


def _parse_level(value: str | int) -> LogLevel:
    """Normalize a log level value to LogLevel enum."""
    if isinstance(value, int):
        # Bunyan/Pino numeric levels
        if value <= 10:
            return LogLevel.DEBUG
        elif value <= 20:
            return LogLevel.DEBUG
        elif value <= 30:
            return LogLevel.INFO
        elif value <= 40:
            return LogLevel.WARNING
        elif value <= 50:
            return LogLevel.ERROR
        else:
            return LogLevel.CRITICAL

    normalized = str(value).strip().lower()
    return _LEVEL_MAP.get(normalized, LogLevel.UNKNOWN)


def _parse_timestamp(value) -> Optional[datetime]:
    """Parse a timestamp from various formats."""
    if isinstance(value, (int, float)):
        try:
            # Unix timestamp (seconds or milliseconds)
            if value > 1e12:
                return datetime.utcfromtimestamp(value / 1000)
            return datetime.utcfromtimestamp(value)
        except (ValueError, OverflowError, OSError):
            return None

    if isinstance(value, str):
        for fmt in [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
        ]:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        # Try ISO format as last resort
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00").replace("+00:00", ""))
        except ValueError:
            return None

    return None


def _json_obj_to_entry(obj: dict, line_number: int) -> LogEntry:
    """Convert a JSON object to a LogEntry."""
    # Find fields
    ts_field = _find_field(obj, _FIELD_MAPPINGS["timestamp"])
    level_field = _find_field(obj, _FIELD_MAPPINGS["level"])
    msg_field = _find_field(obj, _FIELD_MAPPINGS["message"])
    src_field = _find_field(obj, _FIELD_MAPPINGS["source"])

    timestamp = None
    if ts_field:
        timestamp = _parse_timestamp(obj[ts_field])

    log_level = LogLevel.UNKNOWN
    if level_field:
        log_level = _parse_level(obj[level_field])

    message = ""
    if msg_field:
        message = str(obj[msg_field])
    else:
        # Use the full JSON as message
        message = json.dumps(obj, default=str)

    source = ""
    if src_field:
        source = str(obj[src_field])

    return LogEntry(
        raw=json.dumps(obj, default=str),
        line_number=line_number,
        timestamp=timestamp,
        log_level=log_level,
        message=message,
        source=source,
        log_type="JSON",
    )


def read_json_lines(
    file_path: str,
) -> Generator[tuple[int, str], None, None]:
    """
    Read a JSON log file and yield (line_number, raw_line) tuples.

    Supports both JSON Lines and JSON array formats.
    This produces output compatible with the existing normalizer pipeline.

    Args:
        file_path: Path to the JSON log file.

    Yields:
        (line_number, raw_json_line) tuples.
    """
    path = Path(file_path)

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, IOError) as e:
        logger.error("Failed to read JSON file %s: %s", file_path, e)
        return

    content = content.strip()

    if content.startswith("["):
        # JSON array format
        try:
            items = json.loads(content)
            for i, item in enumerate(items, start=1):
                if isinstance(item, dict):
                    yield i, json.dumps(item)
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON array in %s: %s", file_path, e)
            return
    else:
        # JSON Lines format
        for line_number, line in enumerate(content.splitlines(), start=1):
            line = line.strip()
            if line:
                yield line_number, line


def parse_json_logs(file_path: str) -> list[LogEntry]:
    """
    Parse a JSON log file directly into LogEntry objects.

    This is the high-level API for JSON log ingestion.

    Args:
        file_path: Path to the JSON log file.

    Returns:
        List of LogEntry objects.
    """
    entries: list[LogEntry] = []

    for line_number, raw_line in read_json_lines(file_path):
        try:
            obj = json.loads(raw_line)
            if isinstance(obj, dict):
                entry = _json_obj_to_entry(obj, line_number)
                entries.append(entry)
        except json.JSONDecodeError:
            logger.debug("Skipping non-JSON line %d", line_number)
            continue

    logger.info("Parsed %d JSON log entries from %s", len(entries), file_path)
    return entries
