"""Tests for app.anomaly — rule engine, ML engine, and evaluator."""

import pytest
from models.schemas import LogEntry, LogLevel, AnomalyResult
from app.anomaly.rule_engine import (
    detect_critical_keywords,
    detect_frequency_spikes,
    detect_repeated_errors,
    run_rule_engine,
)
from app.anomaly.ml_engine import extract_features, extract_feature_matrix, run_ml_engine
from app.anomaly.evaluator import evaluate_anomalies
from datetime import datetime


def _make_entry(
    line: int = 1,
    message: str = "Test message",
    level: LogLevel = LogLevel.INFO,
    timestamp: datetime = None,
) -> LogEntry:
    """Helper to create test LogEntry objects."""
    return LogEntry(
        raw=message,
        line_number=line,
        timestamp=timestamp or datetime(2024, 1, 15, 10, 30, 0),
        log_level=level,
        message=message,
        source="test",
        log_type="test",
    )


# ── Rule Engine Tests ───────────────────────────────────────────────

class TestCriticalKeywords:
    def test_detects_oom(self):
        entry = _make_entry(message="Out of memory: Kill process 1234")
        is_match, conf, detail = detect_critical_keywords(entry)
        assert is_match
        assert conf > 0
        assert "out of memory" in detail.lower()

    def test_detects_segfault(self):
        entry = _make_entry(message="segfault at 0x0000 in libfoo.so")
        is_match, _, _ = detect_critical_keywords(entry)
        assert is_match

    def test_normal_message_no_match(self):
        entry = _make_entry(message="User login successful")
        is_match, conf, _ = detect_critical_keywords(entry)
        assert not is_match
        assert conf == 0.0

    def test_multiple_keywords_higher_confidence(self):
        entry = _make_entry(message="fatal segfault causing corruption")
        _, conf, _ = detect_critical_keywords(entry)
        assert conf > 0.6  # Multiple keywords → higher confidence


class TestFrequencySpikes:
    def test_detects_spike(self):
        """11 entries in same second should trigger spike (threshold=10)."""
        entries = [
            _make_entry(line=i, timestamp=datetime(2024, 1, 15, 10, 30, 0))
            for i in range(11)
        ]
        results = detect_frequency_spikes(entries)
        assert len(results) > 0

    def test_no_spike_below_threshold(self):
        entries = [
            _make_entry(line=i, timestamp=datetime(2024, 1, 15, 10, 30+i, 0))
            for i in range(5)
        ]
        results = detect_frequency_spikes(entries)
        assert len(results) == 0


class TestRepeatedErrors:
    def test_detects_repetition(self):
        entries = [
            _make_entry(line=i, message="Connection refused", level=LogLevel.ERROR)
            for i in range(5)
        ]
        results = detect_repeated_errors(entries)
        assert len(results) == 5

    def test_no_repetition_for_unique(self):
        entries = [
            _make_entry(line=i, message=f"Unique error {i}", level=LogLevel.ERROR)
            for i in range(3)
        ]
        results = detect_repeated_errors(entries)
        assert len(results) == 0


class TestRunRuleEngine:
    def test_returns_results_for_all_entries(self):
        entries = [_make_entry(line=i) for i in range(5)]
        results = run_rule_engine(entries)
        assert len(results) == 5

    def test_critical_level_flagged(self):
        entry = _make_entry(level=LogLevel.CRITICAL, message="System shutdown")
        results = run_rule_engine([entry])
        assert results[entry.line_number].is_anomaly


# ── ML Engine Tests ─────────────────────────────────────────────────

class TestFeatureExtraction:
    def test_feature_vector_length(self):
        entry = _make_entry()
        features = extract_features(entry)
        assert len(features) == 7

    def test_features_in_range(self):
        entry = _make_entry(message="ERROR: fatal crash")
        features = extract_features(entry)
        for f in features:
            assert 0.0 <= f <= 1.0

    def test_feature_matrix_shape(self):
        entries = [_make_entry(line=i) for i in range(10)]
        matrix = extract_feature_matrix(entries)
        assert matrix.shape == (10, 7)

    def test_empty_entries_matrix(self):
        matrix = extract_feature_matrix([])
        assert matrix.shape == (0, 7)


class TestMLEngine:
    def test_skips_below_minimum(self):
        """Should return 0.0 for all entries when batch is too small."""
        entries = [_make_entry(line=i) for i in range(5)]
        results = run_ml_engine(entries)
        assert all(v == 0.0 for v in results.values())

    def test_runs_with_enough_data(self):
        """Should produce scores for a batch of 50+ entries."""
        entries = []
        for i in range(50):
            if i < 45:
                entries.append(_make_entry(line=i, message=f"Normal operation {i}"))
            else:
                entries.append(_make_entry(
                    line=i,
                    message="FATAL ERROR: segfault crash corruption",
                    level=LogLevel.CRITICAL,
                ))
        results = run_ml_engine(entries)
        assert len(results) == 50
        # All scores should be in [0, 1]
        for score in results.values():
            assert 0.0 <= score <= 1.0


# ── Evaluator Tests ────────────────────────────────────────────────

class TestEvaluator:
    def test_combines_results(self):
        entries = [
            _make_entry(line=1, message="Normal info message"),
            _make_entry(line=2, message="Out of memory: fatal error", level=LogLevel.CRITICAL),
        ]
        results = evaluate_anomalies(entries)
        assert len(results) == 2
        # The OOM entry should be flagged
        assert results[2].is_anomaly
        assert results[2].confidence > 0

    def test_all_entries_have_result(self):
        entries = [_make_entry(line=i) for i in range(10)]
        results = evaluate_anomalies(entries)
        assert len(results) == 10
