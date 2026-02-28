"""
Regex pattern templates for various log formats.

Each pattern is a compiled regex with named groups that map to
LogEntry fields. The module provides a registry of known patterns
and a function to detect the log format from sample lines.

Anti-hallucination rule: If no pattern matches → "UNCLASSIFIED".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class LogPattern:
    """
    A named log format pattern.

    Attributes:
        name: Human-readable format name (e.g., 'syslog').
        regex: Compiled regex with named capture groups.
        timestamp_format: strptime format string for parsing timestamps.
        description: Brief description of the format.
    """
    name: str
    regex: re.Pattern
    timestamp_format: Optional[str]
    description: str


# ─── Pattern Definitions ────────────────────────────────────────────────

# Syslog: "Jan 15 10:30:45 hostname process[pid]: message"
SYSLOG_PATTERN = LogPattern(
    name="syslog",
    regex=re.compile(
        r"^(?P<timestamp>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
        r"(?P<source>\S+)\s+"
        r"(?P<process>\S+?)(?:\[(?P<pid>\d+)\])?\s*:\s*"
        r"(?P<message>.+)$"
    ),
    timestamp_format="%b %d %H:%M:%S",
    description="Standard syslog format (RFC 3164)",
)

# Apache Access Log: '127.0.0.1 - user [15/Jan/2024:10:30:45 +0000] "GET /path HTTP/1.1" 200 1234'
APACHE_ACCESS_PATTERN = LogPattern(
    name="apache_access",
    regex=re.compile(
        r'^(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+'
        r'(?P<ident>\S+)\s+'
        r'(?P<username>\S+)\s+'
        r'\[(?P<timestamp>[^\]]+)\]\s+'
        r'"(?P<method>\w+)\s+(?P<path>\S+)\s+(?P<protocol>[^"]+)"\s+'
        r'(?P<status>\d{3})\s+'
        r'(?P<size>\d+|-)'
        r'(?:\s+"(?P<referer>[^"]*)")?\s*'
        r'(?:"(?P<user_agent>[^"]*)")?'
    ),
    timestamp_format="%d/%b/%Y:%H:%M:%S %z",
    description="Apache/Nginx combined access log",
)

# Apache Error Log: "[Fri Jan 15 10:30:45.123456 2024] [module:level] [pid N] message"
APACHE_ERROR_PATTERN = LogPattern(
    name="apache_error",
    regex=re.compile(
        r'^\[(?P<timestamp>[^\]]+)\]\s+'
        r'\[(?:(?P<module>\w+):)?(?P<log_level>\w+)\]\s+'
        r'(?:\[pid\s+(?P<pid>\d+)\]\s+)?'
        r'(?:\[client\s+(?P<ip>[^\]]+)\]\s+)?'
        r'(?P<message>.+)$'
    ),
    timestamp_format=None,  # Variable format, parsed manually
    description="Apache error log format",
)

# Python/Application Log: "2024-01-15 10:30:45,123 - module - ERROR - message"
PYTHON_LOG_PATTERN = LogPattern(
    name="python",
    regex=re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[,.]?\d*)\s+'
        r'[-–]\s*(?P<source>\S+)\s+'
        r'[-–]\s*(?P<log_level>[A-Z]+)\s+'
        r'[-–]\s*(?P<message>.+)$'
    ),
    timestamp_format="%Y-%m-%d %H:%M:%S,%f",
    description="Python logging format",
)

# ISO timestamp generic: "2024-01-15T10:30:45.123Z LEVEL message"
ISO_GENERIC_PATTERN = LogPattern(
    name="iso_generic",
    regex=re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+'
        r'(?P<log_level>[A-Z]+)\s+'
        r'(?:\[(?P<source>[^\]]+)\]\s+)?'
        r'(?P<message>.+)$'
    ),
    timestamp_format=None,  # Parsed with flexible ISO parser
    description="ISO 8601 timestamp with level",
)

# Simple Level: Message format: "ERROR: Something went wrong"
SIMPLE_LEVEL_PATTERN = LogPattern(
    name="simple_level",
    regex=re.compile(
        r'^(?P<log_level>DEBUG|INFO|NOTICE|WARNING|WARN|ERROR|ERR|CRITICAL|CRIT|FATAL|ALERT|EMERG)\s*'
        r'[:\-]\s*(?P<message>.+)$',
        re.IGNORECASE,
    ),
    timestamp_format=None,
    description="Simple LEVEL: message format",
)

# JSON-structured log: {"timestamp": "...", "level": "...", "message": "..."}
# NOTE: This is handled separately in the parser since it's not regex-based.
# We include a detection pattern here.
JSON_LOG_PATTERN = LogPattern(
    name="json",
    regex=re.compile(r'^\s*\{.*"(?:level|log_level|severity)".*\}\s*$'),
    timestamp_format=None,
    description="JSON-structured log entries",
)

# Windows Event Log style: "Information 1/15/2024 10:30:45 AM Source EventID Message"
WINDOWS_EVENT_PATTERN = LogPattern(
    name="windows_event",
    regex=re.compile(
        r'^(?P<log_level>Information|Warning|Error|Critical|Verbose)\s+'
        r'(?P<timestamp>\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\s*(?:AM|PM)?)\s+'
        r'(?P<source>\S+)\s+'
        r'(?:(?P<error_code>\d+)\s+)?'
        r'(?P<message>.+)$',
        re.IGNORECASE,
    ),
    timestamp_format="%m/%d/%Y %I:%M:%S %p",
    description="Windows Event Log format",
)


# ─── Pattern Registry ───────────────────────────────────────────────────

# Ordered by specificity: more specific patterns first
PATTERN_REGISTRY: list[LogPattern] = [
    APACHE_ACCESS_PATTERN,
    APACHE_ERROR_PATTERN,
    SYSLOG_PATTERN,
    PYTHON_LOG_PATTERN,
    WINDOWS_EVENT_PATTERN,
    ISO_GENERIC_PATTERN,
    SIMPLE_LEVEL_PATTERN,
    JSON_LOG_PATTERN,
]


def get_pattern_by_name(name: str) -> Optional[LogPattern]:
    """Look up a pattern by name. Returns None if not found."""
    for pattern in PATTERN_REGISTRY:
        if pattern.name == name:
            return pattern
    return None
