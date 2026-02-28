"""Tests for app.parsing.parser — log parsing (10+ tests required)."""

import pytest
from datetime import datetime
from app.parsing.parser import (
    parse_line,
    parse_log_entries,
    detect_log_type,
    normalize_log_level,
    parse_timestamp,
)
from app.parsing.patterns import PATTERN_REGISTRY
from models.schemas import LogLevel


class TestNormalizeLogLevel:
    """Tests for log level normalization."""

    def test_standard_levels(self):
        assert normalize_log_level("DEBUG") == LogLevel.DEBUG
        assert normalize_log_level("INFO") == LogLevel.INFO
        assert normalize_log_level("WARNING") == LogLevel.WARNING
        assert normalize_log_level("ERROR") == LogLevel.ERROR
        assert normalize_log_level("CRITICAL") == LogLevel.CRITICAL

    def test_case_insensitive(self):
        assert normalize_log_level("error") == LogLevel.ERROR
        assert normalize_log_level("Warning") == LogLevel.WARNING

    def test_aliases(self):
        assert normalize_log_level("WARN") == LogLevel.WARNING
        assert normalize_log_level("FATAL") == LogLevel.CRITICAL
        assert normalize_log_level("ERR") == LogLevel.ERROR

    def test_none_returns_unknown(self):
        assert normalize_log_level(None) == LogLevel.UNKNOWN

    def test_unknown_string_returns_unknown(self):
        assert normalize_log_level("GARBAGE") == LogLevel.UNKNOWN


class TestParseTimestamp:
    """Tests for timestamp parsing."""

    def test_iso_format(self):
        ts = parse_timestamp("2024-01-15 10:30:45")
        assert ts is not None
        assert ts.year == 2024
        assert ts.month == 1
        assert ts.hour == 10

    def test_iso_with_millis(self):
        ts = parse_timestamp("2024-01-15 10:30:45,123")
        assert ts is not None

    def test_syslog_format(self):
        ts = parse_timestamp("Jan 15 10:30:45")
        assert ts is not None
        assert ts.month == 1
        assert ts.day == 15

    def test_unparseable_returns_none(self):
        assert parse_timestamp("not a timestamp") is None

    def test_none_returns_none(self):
        assert parse_timestamp(None) is None


class TestParseLine:
    """Tests for single-line parsing."""

    def test_syslog_format(self):
        line = "Jan 15 10:30:45 webserver sshd[12345]: Accepted password for admin from 192.168.1.100 port 22"
        entry = parse_line(line, 1)
        assert entry.log_type == "syslog"
        assert entry.source in ("webserver", "sshd")
        assert "Accepted password" in entry.message

    def test_python_log_format(self):
        line = "2024-01-15 10:30:45,123 - myapp.auth - ERROR - Login failed for user admin"
        entry = parse_line(line, 1)
        assert entry.log_type == "python"
        assert entry.log_level == LogLevel.ERROR
        assert "Login failed" in entry.message

    def test_simple_level_format(self):
        line = "ERROR: Something went wrong with the database"
        entry = parse_line(line, 1)
        assert entry.log_level == LogLevel.ERROR
        assert "Something went wrong" in entry.message

    def test_json_log_format(self):
        line = '{"timestamp": "2024-01-15T10:30:45", "level": "ERROR", "message": "Connection failed", "ip": "10.0.0.1"}'
        entry = parse_line(line, 1)
        assert entry.log_type == "json"
        assert entry.log_level == LogLevel.ERROR
        assert entry.ip_address == "10.0.0.1"

    def test_iso_generic_format(self):
        line = "2024-01-15T10:30:45.123Z ERROR [myservice] Failed to process request"
        entry = parse_line(line, 1)
        assert entry.log_level == LogLevel.ERROR
        assert "Failed to process" in entry.message

    def test_unclassified_format(self):
        """Anti-hallucination: unknown patterns → UNCLASSIFIED."""
        line = "this is just random text with no log format"
        entry = parse_line(line, 1)
        assert entry.log_type == "UNCLASSIFIED"
        assert entry.log_level == LogLevel.UNKNOWN

    def test_ip_extraction_from_message(self):
        line = "ERROR: Connection refused from 192.168.1.50"
        entry = parse_line(line, 1)
        assert entry.ip_address == "192.168.1.50"

    def test_error_code_extraction(self):
        line = "ERROR: Request failed with error code ERR_CONNECTION_REFUSED"
        entry = parse_line(line, 1)
        # error_code should be extracted from message
        assert entry.error_code is not None


class TestDetectLogType:
    """Tests for auto-detection of log format."""

    def test_detects_syslog(self):
        lines = [
            "Jan 15 10:30:45 host sshd[123]: message one",
            "Jan 15 10:30:46 host app[456]: message two",
            "Jan 15 10:30:47 host kernel: message three",
        ]
        pattern = detect_log_type(lines)
        assert pattern is not None
        assert pattern.name == "syslog"

    def test_detects_python(self):
        lines = [
            "2024-01-15 10:30:45,123 - mod - INFO - msg1",
            "2024-01-15 10:30:46,456 - mod - ERROR - msg2",
            "2024-01-15 10:30:47,789 - mod - DEBUG - msg3",
        ]
        pattern = detect_log_type(lines)
        assert pattern is not None
        assert pattern.name == "python"

    def test_returns_none_for_unknown(self):
        lines = ["random text", "more random", "nothing formatted"]
        pattern = detect_log_type(lines)
        assert pattern is None

    def test_empty_input(self):
        assert detect_log_type([]) is None


class TestParseLogEntries:
    """Tests for batch parsing."""

    def test_parses_syslog_file(self, sample_log_path):
        from app.ingestion.reader import read_lines
        from app.ingestion.normalizer import normalize_entries
        lines = list(normalize_entries(read_lines(sample_log_path)))
        entries = parse_log_entries(lines=lines)
        assert len(entries) > 0
        # At least some entries should be classified
        classified = [e for e in entries if e.log_type != "UNCLASSIFIED"]
        assert len(classified) > 0

    def test_parses_python_log_file(self, python_log_path):
        from app.ingestion.reader import read_lines
        from app.ingestion.normalizer import normalize_entries
        lines = list(normalize_entries(read_lines(python_log_path)))
        entries = parse_log_entries(lines=lines)
        assert len(entries) > 0
        python_entries = [e for e in entries if e.log_type == "python"]
        assert len(python_entries) > 0

    def test_empty_input(self):
        entries = parse_log_entries(lines=[])
        assert entries == []

    def test_corrupted_file_parses_as_unclassified(self, corrupted_log_path):
        from app.ingestion.reader import read_lines
        from app.ingestion.normalizer import normalize_entries
        lines = list(normalize_entries(read_lines(corrupted_log_path)))
        entries = parse_log_entries(lines=lines)
        # All entries should be UNCLASSIFIED
        for e in entries:
            assert e.log_type == "UNCLASSIFIED"
