"""conftest.py — Shared test fixtures for the log analyzer test suite."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Project root for test fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_log_path() -> str:
    """Path to the sample syslog fixture."""
    return str(FIXTURES_DIR / "sample.log")


@pytest.fixture
def python_log_path() -> str:
    """Path to the Python-format log fixture."""
    return str(FIXTURES_DIR / "python_app.log")


@pytest.fixture
def corrupted_log_path() -> str:
    """Path to the corrupted/unknown format fixture."""
    return str(FIXTURES_DIR / "corrupted.log")


@pytest.fixture
def empty_log_path(tmp_path) -> str:
    """Path to an empty log file."""
    f = tmp_path / "empty.log"
    f.write_text("")
    return str(f)


@pytest.fixture
def large_log_path(tmp_path) -> str:
    """Path to a large-ish log file (~1MB) for performance tests."""
    f = tmp_path / "large.log"
    line = "Jan 15 10:30:45 host app[1234]: INFO: Processing request id=12345 status=ok\n"
    # ~100 bytes per line × 10000 lines = ~1MB
    with open(f, "w") as fp:
        for i in range(10_000):
            fp.write(f"Jan 15 10:{i//60:02d}:{i%60:02d} host app[1234]: INFO: Processing request id={i} status=ok\n")
    return str(f)


@pytest.fixture
def tmp_log_file(tmp_path):
    """Factory fixture to create temp log files with custom content."""
    def _create(content: str, suffix: str = ".log") -> str:
        f = tmp_path / f"test{suffix}"
        f.write_text(content)
        return str(f)
    return _create
