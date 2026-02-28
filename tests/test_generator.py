"""Tests for app.explanation — template-based explanation generator."""

import pytest
from models.schemas import LogEntry, LogLevel, AnomalyResult, SeverityResult, SeverityLevel
from app.explanation.generator import generate_explanation, generate_explanations
from app.explanation.templates import get_template, TEMPLATE_MAP
from datetime import datetime


def _make_entry(
    message: str = "Test error",
    level: LogLevel = LogLevel.ERROR,
) -> LogEntry:
    return LogEntry(
        raw=message, line_number=1,
        timestamp=datetime(2024, 1, 15, 10, 30, 0),
        log_level=level, message=message, source="test", log_type="test",
    )


class TestGetTemplate:
    def test_known_types_return_template(self):
        for atype in ("critical_keyword", "frequency_spike", "repeated_error", "ml_detected", "none"):
            tmpl = get_template(atype)
            assert tmpl is not None
            assert tmpl.summary_template

    def test_unknown_type_returns_default(self):
        tmpl = get_template("nonexistent_type")
        assert tmpl is not None
        assert "flagged for review" in tmpl.summary_template


class TestGenerateExplanation:
    def test_generates_summary(self):
        entry = _make_entry("Fatal system crash")
        anomaly = AnomalyResult(is_anomaly=True, confidence=0.8, anomaly_type="critical_keyword", details="Critical keywords found: fatal")
        severity = SeverityResult(level=SeverityLevel.CRITICAL, score=0.9)
        explanation = generate_explanation(entry, anomaly, severity)
        assert explanation.summary
        assert "CRITICAL" in explanation.summary

    def test_generates_causes(self):
        entry = _make_entry("Out of memory error")
        anomaly = AnomalyResult(is_anomaly=True, confidence=0.7, anomaly_type="critical_keyword", details="Keywords: out of memory")
        severity = SeverityResult(level=SeverityLevel.HIGH, score=0.7)
        explanation = generate_explanation(entry, anomaly, severity)
        assert len(explanation.possible_causes) > 0

    def test_generates_remediation(self):
        entry = _make_entry("Repeated DB failure")
        anomaly = AnomalyResult(is_anomaly=True, confidence=0.6, anomaly_type="repeated_error", details="Repeated 5 times")
        severity = SeverityResult(level=SeverityLevel.MEDIUM, score=0.5)
        explanation = generate_explanation(entry, anomaly, severity)
        assert len(explanation.remediation) > 0

    def test_low_confidence_note(self):
        entry = _make_entry("Minor issue")
        anomaly = AnomalyResult(is_anomaly=True, confidence=0.3, anomaly_type="ml_detected")
        severity = SeverityResult(level=SeverityLevel.LOW, score=0.3)
        explanation = generate_explanation(entry, anomaly, severity)
        assert "false positive" in explanation.confidence_note.lower()

    def test_high_confidence_note(self):
        entry = _make_entry("Critical failure")
        anomaly = AnomalyResult(is_anomaly=True, confidence=0.9, anomaly_type="critical_keyword")
        severity = SeverityResult(level=SeverityLevel.CRITICAL, score=0.9)
        explanation = generate_explanation(entry, anomaly, severity)
        assert "high confidence" in explanation.confidence_note.lower()

    def test_no_anomaly_normal_note(self):
        entry = _make_entry("All systems normal")
        anomaly = AnomalyResult(is_anomaly=False)
        severity = SeverityResult(level=SeverityLevel.LOW, score=0.1)
        explanation = generate_explanation(entry, anomaly, severity)
        assert "no anomaly" in explanation.confidence_note.lower()

    def test_never_fabricates_unknown_causes(self):
        """Anti-hallucination: explanations should use 'possible' language."""
        entry = _make_entry("Unknown error XYZ123")
        anomaly = AnomalyResult(is_anomaly=True, confidence=0.5, anomaly_type="ml_detected")
        severity = SeverityResult(level=SeverityLevel.MEDIUM, score=0.5)
        explanation = generate_explanation(entry, anomaly, severity)
        # Should have hedging language
        has_hedging = any(
            word in cause.lower()
            for cause in explanation.possible_causes
            for word in ("possible", "may", "could", "might", "unusual")
        )
        assert has_hedging


class TestGenerateExplanations:
    def test_batch_generation(self):
        entries = [_make_entry(f"Error {i}") for i in range(3)]
        for e in entries:
            e.line_number = entries.index(e) + 1

        anomalies = {e.line_number: AnomalyResult(confidence=0.5) for e in entries}
        severities = {e.line_number: SeverityResult(score=0.4) for e in entries}

        results = generate_explanations(entries, anomalies, severities)
        assert len(results) == 3
