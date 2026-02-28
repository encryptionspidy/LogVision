"""Tests for multi-source ingestion modules."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from app.ingestion.json_reader import (
    parse_json_logs,
    read_json_lines,
    _parse_level,
    _parse_timestamp,
)
from app.ingestion.directory_watcher import DirectoryWatcher
from models.schemas import LogLevel


class TestJsonReader:
    def test_parse_json_lines_format(self, tmp_path):
        """JSON Lines format (one JSON per line)."""
        log_file = tmp_path / "test.json"
        lines = [
            json.dumps({"timestamp": "2024-01-15T14:00:00Z", "level": "error", "message": "Connection failed"}),
            json.dumps({"timestamp": "2024-01-15T14:01:00Z", "level": "info", "message": "Retry succeeded"}),
        ]
        log_file.write_text("\n".join(lines))

        entries = parse_json_logs(str(log_file))
        assert len(entries) == 2
        assert entries[0].message == "Connection failed"
        assert entries[0].log_level == LogLevel.ERROR
        assert entries[1].log_level == LogLevel.INFO

    def test_parse_json_array_format(self, tmp_path):
        """JSON array format."""
        log_file = tmp_path / "test.json"
        data = [
            {"timestamp": "2024-01-15T14:00:00Z", "level": "warn", "msg": "High CPU"},
            {"timestamp": "2024-01-15T14:01:00Z", "level": "error", "msg": "OOM killed"},
        ]
        log_file.write_text(json.dumps(data))

        entries = parse_json_logs(str(log_file))
        assert len(entries) == 2
        assert entries[0].message == "High CPU"

    def test_parse_bunyan_numeric_levels(self, tmp_path):
        """Bunyan/Pino numeric log levels."""
        log_file = tmp_path / "test.json"
        lines = [
            json.dumps({"time": 1705320000000, "level": 50, "msg": "Error event"}),
            json.dumps({"time": 1705320060000, "level": 30, "msg": "Info event"}),
        ]
        log_file.write_text("\n".join(lines))

        entries = parse_json_logs(str(log_file))
        assert len(entries) == 2
        assert entries[0].log_level == LogLevel.ERROR
        assert entries[1].log_level == LogLevel.INFO

    def test_missing_fields_handled(self, tmp_path):
        """Entries with missing fields should still parse."""
        log_file = tmp_path / "test.json"
        log_file.write_text(json.dumps({"arbitrary_key": "value"}))

        entries = parse_json_logs(str(log_file))
        assert len(entries) == 1
        assert entries[0].log_level == LogLevel.UNKNOWN

    def test_empty_file(self, tmp_path):
        log_file = tmp_path / "test.json"
        log_file.write_text("")
        entries = parse_json_logs(str(log_file))
        assert entries == []

    def test_invalid_json(self, tmp_path):
        log_file = tmp_path / "test.json"
        log_file.write_text("this is not json\nalso not json")
        entries = parse_json_logs(str(log_file))
        assert entries == []


class TestParseLevel:
    def test_common_levels(self):
        assert _parse_level("error") == LogLevel.ERROR
        assert _parse_level("ERROR") == LogLevel.ERROR
        assert _parse_level("warn") == LogLevel.WARNING
        assert _parse_level("info") == LogLevel.INFO
        assert _parse_level("debug") == LogLevel.DEBUG
        assert _parse_level("fatal") == LogLevel.CRITICAL

    def test_numeric_levels(self):
        assert _parse_level(50) == LogLevel.ERROR
        assert _parse_level(30) == LogLevel.INFO
        assert _parse_level(60) == LogLevel.CRITICAL

    def test_unknown_level(self):
        assert _parse_level("nonsense") == LogLevel.UNKNOWN


class TestParseTimestamp:
    def test_iso_formats(self):
        ts = _parse_timestamp("2024-01-15T14:00:00Z")
        assert ts is not None
        assert ts.year == 2024

    def test_unix_timestamp(self):
        ts = _parse_timestamp(1705320000)
        assert ts is not None

    def test_unix_ms_timestamp(self):
        ts = _parse_timestamp(1705320000000)
        assert ts is not None

    def test_invalid(self):
        assert _parse_timestamp("not a date") is None


class TestDirectoryWatcher:
    def test_scan_existing(self, tmp_path):
        (tmp_path / "app.log").write_text("log content")
        (tmp_path / "app2.txt").write_text("text content")
        (tmp_path / "readme.md").write_text("not a log")

        watcher = DirectoryWatcher(str(tmp_path))
        files = watcher.scan_existing()
        assert len(files) == 2
        assert any("app.log" in f for f in files)
        assert any("app2.txt" in f for f in files)

    def test_invalid_path(self):
        with pytest.raises(ValueError, match="not a directory"):
            DirectoryWatcher("/nonexistent/path")

    def test_scan_empty_directory(self, tmp_path):
        watcher = DirectoryWatcher(str(tmp_path))
        files = watcher.scan_existing()
        assert files == []

    def test_custom_extensions(self, tmp_path):
        (tmp_path / "app.log").write_text("log")
        (tmp_path / "data.csv").write_text("csv")

        watcher = DirectoryWatcher(str(tmp_path), extensions={".csv"})
        files = watcher.scan_existing()
        assert len(files) == 1
        assert "data.csv" in files[0]


class TestReadJsonLines:
    def test_yields_lines(self, tmp_path):
        log_file = tmp_path / "test.json"
        log_file.write_text('{"msg":"a"}\n{"msg":"b"}\n')

        lines = list(read_json_lines(str(log_file)))
        assert len(lines) == 2
        assert lines[0][0] == 1  # line number
        assert '"msg"' in lines[0][1]

    def test_nonexistent_file(self, tmp_path):
        lines = list(read_json_lines(str(tmp_path / "missing.json")))
        assert lines == []
