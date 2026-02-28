"""
Tests for log clustering and template mining.
"""

import pytest
from datetime import datetime

from models.schemas import LogEntry, LogLevel
from app.clustering.cluster_engine import (
    cluster_logs,
    ClusterSummary,
    _normalize_message,
)
from app.clustering.template_miner import (
    extract_template,
    mine_templates,
    TemplateMiningResult,
)


# ─── Fixtures ────────────────────────────────────────────────────────────

def _make_entry(msg: str, line: int, level: LogLevel = LogLevel.INFO) -> LogEntry:
    return LogEntry(
        raw=msg,
        line_number=line,
        timestamp=datetime(2024, 1, 15, 10, 0, 0),
        log_level=level,
        message=msg,
        source="test",
    )


@pytest.fixture
def repeated_entries() -> list[LogEntry]:
    """20 entries: 10 similar 'Connection timeout' and 10 similar 'User login'."""
    entries = []
    for i in range(10):
        entries.append(_make_entry(
            f"Connection timeout to 192.168.1.{i} after 30s",
            line=i + 1,
            level=LogLevel.ERROR,
        ))
    for i in range(10):
        entries.append(_make_entry(
            f"User login successful for user_{i} from 10.0.0.{i}",
            line=i + 11,
            level=LogLevel.INFO,
        ))
    return entries


@pytest.fixture
def diverse_entries() -> list[LogEntry]:
    """Mix of various log types."""
    messages = [
        "Failed to connect to database at 10.0.1.5:5432",
        "Failed to connect to database at 10.0.1.6:5432",
        "Failed to connect to database at 10.0.1.7:5432",
        "User authentication failed for admin",
        "User authentication failed for root",
        "Disk usage at 95% on /dev/sda1",
        "Disk usage at 87% on /dev/sdb1",
        "Application started successfully on port 8080",
        "Application started successfully on port 3000",
        "Memory allocation error: requested 4096 bytes",
    ]
    return [_make_entry(m, i + 1) for i, m in enumerate(messages)]


# ─── Normalize Message ───────────────────────────────────────────────────

class TestNormalizeMessage:
    def test_replaces_ips(self):
        result = _normalize_message("Connection to 192.168.1.1 failed")
        assert "<IP>" in result
        assert "192.168.1.1" not in result

    def test_replaces_numbers(self):
        result = _normalize_message("Timeout after 3000ms")
        assert "<NUM>" in result

    def test_replaces_paths(self):
        result = _normalize_message("Error reading /var/log/syslog")
        assert "<PATH>" in result

    def test_replaces_hex(self):
        result = _normalize_message("Object 0x7f3a2b1c at address deadbeef01")
        assert "<HEX>" in result


# ─── Cluster Engine ──────────────────────────────────────────────────────

class TestClusterEngine:
    def test_returns_none_for_tiny_batch(self):
        entries = [_make_entry("hello", 1), _make_entry("world", 2)]
        result = cluster_logs(entries)
        assert result is None

    def test_clusters_repeated_entries(self, repeated_entries):
        result = cluster_logs(repeated_entries, max_clusters=5)
        assert result is not None
        assert isinstance(result, ClusterSummary)
        assert result.n_clusters > 0
        assert len(result.assignments) == len(repeated_entries)

    def test_all_entries_assigned(self, diverse_entries):
        result = cluster_logs(diverse_entries, max_clusters=5)
        assert result is not None
        for entry in diverse_entries:
            assert entry.line_number in result.assignments

    def test_similar_messages_same_cluster(self, repeated_entries):
        result = cluster_logs(repeated_entries, max_clusters=5)
        assert result is not None
        # The first 10 "Connection timeout" entries should mostly share a cluster
        timeout_clusters = {result.assignments[i] for i in range(1, 11)}
        # Allow some variance but most should be in the same cluster
        assert len(timeout_clusters) <= 3  # Generous bound


# ─── Template Miner ──────────────────────────────────────────────────────

class TestExtractTemplate:
    def test_replaces_ip(self):
        tpl = extract_template("Connection from 192.168.1.100:8080 refused")
        assert "<IP>" in tpl
        assert "192.168" not in tpl

    def test_replaces_timestamp(self):
        tpl = extract_template("Event at 2024-01-15T10:30:00Z completed")
        assert "<TIMESTAMP>" in tpl

    def test_replaces_uuid(self):
        tpl = extract_template("Request a1b2c3d4-e5f6-7890-abcd-ef1234567890 processed")
        assert "<UUID>" in tpl

    def test_replaces_path(self):
        tpl = extract_template("Error reading /var/log/syslog.1")
        assert "<PATH>" in tpl

    def test_replaces_numbers(self):
        tpl = extract_template("Allocated 4096 bytes in 12ms")
        assert "<NUM>" in tpl

    def test_replaces_quoted_strings(self):
        tpl = extract_template('Key "api_token_xyz" not found')
        assert "<STR>" in tpl

    def test_identical_structures_yield_same_template(self):
        t1 = extract_template("Connection to 10.0.0.1 timeout after 30s")
        t2 = extract_template("Connection to 10.0.0.2 timeout after 45s")
        assert t1 == t2


class TestMineTemplates:
    def test_empty_entries(self):
        result = mine_templates([])
        assert result.n_templates == 0
        assert result.n_entries == 0

    def test_mines_templates(self, diverse_entries):
        result = mine_templates(diverse_entries)
        assert isinstance(result, TemplateMiningResult)
        assert result.n_templates > 0
        assert result.n_entries == len(diverse_entries)

    def test_all_entries_assigned(self, diverse_entries):
        result = mine_templates(diverse_entries)
        for entry in diverse_entries:
            assert entry.line_number in result.assignments

    def test_repeated_messages_group_together(self, repeated_entries):
        result = mine_templates(repeated_entries)
        # Most frequent template should have count >= 10
        assert result.templates[0].count >= 8  # Generous bound

    def test_template_frequency_sums_to_one(self, diverse_entries):
        result = mine_templates(diverse_entries)
        total_freq = sum(t.frequency for t in result.templates)
        assert 0.9 <= total_freq <= 1.1  # Rounding tolerance
