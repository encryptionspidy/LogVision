"""
Log file reader with streaming support and encoding detection.

Reads log files line-by-line using generators to avoid loading
entire files into memory. Handles encoding detection via chardet.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator, Optional

import chardet

from app.config.settings import DEFAULT_CONFIG, IngestionConfig


class ReaderError(Exception):
    """Raised when the reader encounters an unrecoverable error."""
    pass


def validate_file(
    file_path: str,
    config: Optional[IngestionConfig] = None,
) -> Path:
    """
    Validate that a file exists, is readable, and meets constraints.

    Args:
        file_path: Path to the log file.
        config: Ingestion config; uses default if None.

    Returns:
        Resolved Path object.

    Raises:
        ReaderError: If validation fails.
    """
    cfg = config or DEFAULT_CONFIG.ingestion
    path = Path(file_path)

    if not path.exists():
        raise ReaderError(f"File not found: {file_path}")

    if not path.is_file():
        raise ReaderError(f"Not a regular file: {file_path}")

    suffix = path.suffix.lower()
    if suffix not in cfg.allowed_extensions:
        raise ReaderError(
            f"Unsupported file extension '{suffix}'. "
            f"Allowed: {cfg.allowed_extensions}"
        )

    file_size = path.stat().st_size
    if file_size > cfg.max_file_size_bytes:
        raise ReaderError(
            f"File too large: {file_size} bytes "
            f"(max: {cfg.max_file_size_bytes} bytes)"
        )

    if file_size == 0:
        raise ReaderError(f"File is empty: {file_path}")

    return path


def detect_encoding(
    file_path: Path,
    sample_bytes: int = 10_240,
) -> str:
    """
    Detect file encoding by sampling the first N bytes.

    Args:
        file_path: Path to the file.
        sample_bytes: Number of bytes to sample.

    Returns:
        Detected encoding string (e.g., 'utf-8').
        Falls back to 'utf-8' if detection fails.
    """
    try:
        with open(file_path, "rb") as f:
            raw = f.read(sample_bytes)
        if not raw:
            return "utf-8"
        result = chardet.detect(raw)
        encoding = result.get("encoding")
        if encoding is None:
            # ASSUMPTION: If chardet cannot detect, default to utf-8
            return "utf-8"
        return encoding
    except (OSError, IOError) as e:
        # PROPOSED SAFE APPROACH: Fall back to utf-8 on read errors
        return "utf-8"


def read_lines(
    file_path: str,
    config: Optional[IngestionConfig] = None,
) -> Generator[tuple[int, str], None, None]:
    """
    Stream log file lines as (line_number, line_text) tuples.

    This is the primary entry point for ingestion. It validates the file,
    detects encoding, and yields lines one at a time to support large files.

    Args:
        file_path: Path to the log file.
        config: Optional ingestion config override.

    Yields:
        (line_number, stripped_line_text) — 1-indexed line numbers.

    Raises:
        ReaderError: If file validation fails.
    """
    cfg = config or DEFAULT_CONFIG.ingestion
    path = validate_file(file_path, cfg)
    encoding = detect_encoding(path, cfg.encoding_sample_bytes)

    try:
        with open(path, "r", encoding=encoding, errors="replace") as f:
            for line_number, line in enumerate(f, start=1):
                stripped = line.rstrip("\n\r")
                if stripped:  # Skip completely empty lines
                    yield line_number, stripped
    except (OSError, IOError) as e:
        raise ReaderError(f"Error reading file: {e}") from e
