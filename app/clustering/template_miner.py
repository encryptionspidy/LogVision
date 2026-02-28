"""
Drain-style log template extraction.

Extracts structural templates from raw log messages by replacing
variable tokens (IPs, timestamps, numbers, paths, hex strings)
with wildcard placeholders. Groups messages by their template
structure to reduce noise and improve ML signal quality.

Reference: He et al., "Drain: An Online Log Parsing Approach with
Fixed Depth Tree" (ICWS 2017).

This is a simplified implementation suitable for batch processing.
"""

from __future__ import annotations

import re
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from models.schemas import LogEntry

logger = logging.getLogger(__name__)

# Ordered replacement patterns — more specific first
_TEMPLATE_PATTERNS = [
    # ISO timestamps: 2024-01-15T10:30:00Z
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[\.\d]*[Z]?"), "<TIMESTAMP>"),
    # Syslog timestamps: Jan 15 10:30:00
    (re.compile(r"[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}"), "<TIMESTAMP>"),
    # IPv4
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?\b"), "<IP>"),
    # UUIDs
    (re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"), "<UUID>"),
    # Hex strings (8+ chars)
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "<HEX>"),
    (re.compile(r"\b[0-9a-fA-F]{8,}\b"), "<HEX>"),
    # File paths
    (re.compile(r"(?:/[\w\.\-]+)+/?"), "<PATH>"),
    # URLs
    (re.compile(r"https?://\S+"), "<URL>"),
    # Email addresses
    (re.compile(r"\b[\w.+-]+@[\w.-]+\.\w{2,}\b"), "<EMAIL>"),
    # Quoted strings
    (re.compile(r'"[^"]*"'), "<STR>"),
    (re.compile(r"'[^']*'"), "<STR>"),
    # Numbers (integers, floats, with optional units)
    (re.compile(r"\d+\.\d+"), "<FLOAT>"),
    (re.compile(r"\d+"), "<NUM>"),
]

# Collapse repeated wildcards
_COLLAPSE_PATTERN = re.compile(r"(<\w+>\s*){2,}")


@dataclass
class LogTemplate:
    """A discovered log template."""

    template_id: int
    pattern: str  # The template string with wildcards
    count: int  # Number of matching messages
    example: str  # One original message for reference
    frequency: float  # count / total_entries


@dataclass
class TemplateMiningResult:
    """Complete template mining output."""

    templates: list[LogTemplate]
    assignments: dict[int, int]  # line_number -> template_id
    n_templates: int
    n_entries: int


def extract_template(message: str) -> str:
    """
    Convert a log message to its structural template.

    Replaces all variable tokens with typed placeholders.

    Args:
        message: Raw log message.

    Returns:
        Template string with wildcards.
    """
    text = message.strip()

    for pattern, replacement in _TEMPLATE_PATTERNS:
        text = pattern.sub(replacement, text)

    # Collapse consecutive identical wildcards
    text = _COLLAPSE_PATTERN.sub(
        lambda m: m.group(0).split()[0] + " ",
        text,
    )

    # Normalize whitespace
    text = " ".join(text.split())

    return text


def mine_templates(
    entries: list[LogEntry],
    top_n: int = 50,
    min_count: int = 1,
) -> TemplateMiningResult:
    """
    Extract log templates from a batch of entries.

    Groups messages by their structural template, counts frequency,
    and returns the top-N templates.

    Args:
        entries: Parsed log entries.
        top_n: Maximum templates to return.
        min_count: Minimum occurrences for a template to be included.

    Returns:
        TemplateMiningResult with templates and per-entry assignments.
    """
    if not entries:
        return TemplateMiningResult(
            templates=[], assignments={}, n_templates=0, n_entries=0
        )

    # Extract templates
    template_map: dict[str, list[int]] = defaultdict(list)  # template -> line_numbers
    template_examples: dict[str, str] = {}  # template -> first example

    for entry in entries:
        template = extract_template(entry.message)
        template_map[template].append(entry.line_number)
        if template not in template_examples:
            template_examples[template] = entry.message[:300]

    # Sort by frequency, take top N
    sorted_templates = sorted(
        template_map.items(),
        key=lambda x: len(x[1]),
        reverse=True,
    )

    n_total = len(entries)
    templates: list[LogTemplate] = []
    assignments: dict[int, int] = {}

    for tid, (pattern, line_numbers) in enumerate(sorted_templates[:top_n]):
        count = len(line_numbers)
        if count < min_count:
            continue

        templates.append(
            LogTemplate(
                template_id=tid,
                pattern=pattern,
                count=count,
                example=template_examples[pattern],
                frequency=round(count / n_total, 4),
            )
        )

        for ln in line_numbers:
            assignments[ln] = tid

    # Assign remaining entries (beyond top_n) to a catch-all template id
    catch_all_id = len(templates)
    for pattern, line_numbers in sorted_templates[top_n:]:
        for ln in line_numbers:
            assignments[ln] = catch_all_id

    logger.info(
        "Mined %d templates from %d entries (top %d returned)",
        len(template_map),
        n_total,
        len(templates),
    )

    return TemplateMiningResult(
        templates=templates,
        assignments=assignments,
        n_templates=len(templates),
        n_entries=n_total,
    )
