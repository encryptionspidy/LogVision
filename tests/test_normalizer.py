"""Tests for app.ingestion.normalizer — log normalization."""

import pytest
from app.ingestion.normalizer import normalize_line, is_continuation_line, normalize_entries


class TestNormalizeLine:
    """Tests for single-line normalization."""

    def test_strips_ansi_codes(self):
        line = "\x1b[31mERROR\x1b[0m: something failed"
        assert normalize_line(line) == "ERROR: something failed"

    def test_collapses_whitespace(self):
        line = "ERROR:   multiple   spaces   here"
        assert normalize_line(line) == "ERROR: multiple spaces here"

    def test_replaces_tabs(self):
        line = "ERROR:\ttab\there"
        assert normalize_line(line) == "ERROR: tab here"

    def test_strips_leading_trailing(self):
        line = "  ERROR: message  "
        assert normalize_line(line) == "ERROR: message"

    def test_empty_string(self):
        assert normalize_line("") == ""


class TestIsContinuationLine:
    """Tests for continuation line detection."""

    def test_indented_line_is_continuation(self):
        assert is_continuation_line("    at com.example.Main.run(Main.java:10)")

    def test_tab_indented_is_continuation(self):
        assert is_continuation_line("\tat com.example.Main.run(Main.java:10)")

    def test_timestamp_line_not_continuation(self):
        assert not is_continuation_line("Jan 15 10:30:45 host app: message")

    def test_indented_timestamp_not_continuation(self):
        assert not is_continuation_line("  2024-01-15 10:30:45 ERROR: message")

    def test_non_indented_not_continuation(self):
        assert not is_continuation_line("ERROR: not a continuation")

    def test_empty_not_continuation(self):
        assert not is_continuation_line("")


class TestNormalizeEntries:
    """Tests for multiline entry merging."""

    def test_merges_continuation_lines(self):
        lines = [
            (1, "Jan 15 10:30:45 host app: Error occurred"),
            (2, "    at com.example.Main.run(Main.java:10)"),
            (3, "    at com.example.App.start(App.java:5)"),
            (4, "Jan 15 10:31:00 host app: Info message"),
        ]
        result = list(normalize_entries(iter(lines)))
        assert len(result) == 2
        assert result[0][0] == 1  # Line number of first entry
        assert "com.example.Main" in result[0][1]
        assert result[1][0] == 4

    def test_single_lines_pass_through(self):
        lines = [
            (1, "line one"),
            (2, "line two"),
            (3, "line three"),
        ]
        result = list(normalize_entries(iter(lines)))
        assert len(result) == 3

    def test_empty_input(self):
        result = list(normalize_entries(iter([])))
        assert result == []

    def test_continuation_at_start(self):
        """Continuation line with no preceding entry is treated as new."""
        lines = [
            (1, "    orphaned continuation"),
            (2, "normal line"),
        ]
        result = list(normalize_entries(iter(lines)))
        assert len(result) == 2
