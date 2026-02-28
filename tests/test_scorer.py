"""Tests for app.severity.scorer — deterministic severity scoring."""

import pytest
from models.schemas import LogEntry, LogLevel, AnomalyResult, SeverityLevel
from app.severity.scorer import score_entry, score_entries, compute_frequency_score
from datetime import datetime


def _make_entry(level: LogLevel = LogLevel.INFO) -> LogEntry:
    return LogEntry(
        raw="test", line_number=1,
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        log_level=level, message="test", source="test", log_type="test",
    )


class TestComputeFrequencyScore:
    def test_zero_total_returns_zero(self):
        entry = _make_entry()
        assert compute_frequency_score(entry, 0, 0) == 0.0

    def test_high_error_ratio(self):
        entry = _make_entry(LogLevel.ERROR)
        score = compute_frequency_score(entry, 10, 8)
        assert score > 0.5

    def test_low_error_ratio(self):
        entry = _make_entry()
        score = compute_frequency_score(entry, 100, 2)
        assert score < 0.5


class TestScoreEntry:
    def test_deterministic(self):
        """Same inputs must produce same outputs."""
        entry = _make_entry(LogLevel.ERROR)
        anomaly = AnomalyResult(is_anomaly=True, confidence=0.7)
        r1 = score_entry(entry, anomaly, 100, 10)
        r2 = score_entry(entry, anomaly, 100, 10)
        assert r1.score == r2.score
        assert r1.level == r2.level

    def test_critical_entry_high_severity(self):
        entry = _make_entry(LogLevel.CRITICAL)
        anomaly = AnomalyResult(is_anomaly=True, confidence=0.9)
        result = score_entry(entry, anomaly, 10, 5)
        assert result.level in (SeverityLevel.HIGH, SeverityLevel.CRITICAL)
        assert result.score > 0.5

    def test_info_no_anomaly_low_severity(self):
        entry = _make_entry(LogLevel.INFO)
        anomaly = AnomalyResult(is_anomaly=False, confidence=0.0)
        result = score_entry(entry, anomaly, 100, 2)
        assert result.level == SeverityLevel.LOW
        assert result.score < 0.35

    def test_score_has_breakdown(self):
        entry = _make_entry(LogLevel.ERROR)
        anomaly = AnomalyResult(confidence=0.5)
        result = score_entry(entry, anomaly, 50, 10)
        assert "level_base" in result.breakdown
        assert "frequency_score" in result.breakdown
        assert "anomaly_score" in result.breakdown

    def test_score_clamped_0_to_1(self):
        entry = _make_entry(LogLevel.CRITICAL)
        anomaly = AnomalyResult(confidence=1.0)
        result = score_entry(entry, anomaly, 1, 1)
        assert 0.0 <= result.score <= 1.0

    def test_severity_levels_ordered(self):
        """Higher scores → more severe levels."""
        low_entry = _make_entry(LogLevel.DEBUG)
        low_result = score_entry(low_entry, AnomalyResult(confidence=0.0), 100, 0)

        high_entry = _make_entry(LogLevel.CRITICAL)
        high_result = score_entry(high_entry, AnomalyResult(confidence=0.95), 10, 10)

        assert high_result.score > low_result.score


class TestScoreEntries:
    def test_scores_all_entries(self):
        entries = [
            LogEntry(raw="a", line_number=1, log_level=LogLevel.INFO, message="ok", log_type="t"),
            LogEntry(raw="b", line_number=2, log_level=LogLevel.ERROR, message="fail", log_type="t"),
        ]
        anomalies = {
            1: AnomalyResult(confidence=0.0),
            2: AnomalyResult(confidence=0.6, is_anomaly=True),
        }
        results = score_entries(entries, anomalies)
        assert len(results) == 2
        assert results[2].score > results[1].score
