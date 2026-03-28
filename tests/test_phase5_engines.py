from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.analysis.root_cause_engine import build_root_causes
from app.analysis.pattern_analyzer import detect_patterns
from app.analysis.summary_builder import build_summary_report
from app.explanation.deep_explainer import upgrade_explanations
from models.schemas import (
    AnalysisReport,
    LogEntry,
    LogLevel,
    AnomalyResult,
    SeverityResult,
    SeverityLevel,
    Explanation,
)


def _make_entry(line_number: int, *, message: str, ts: datetime) -> LogEntry:
    return LogEntry(
        raw=message,
        line_number=line_number,
        message=message,
        timestamp=ts,
        log_level=LogLevel.ERROR,
        source="app/auth",
    )


def _make_report(
    line_number: int,
    *,
    message: str,
    ts: datetime,
    severity: SeverityLevel = SeverityLevel.HIGH,
    confidence: float = 0.85,
) -> AnalysisReport:
    explanation = Explanation(
        summary="Test explanation",
        possible_causes=["possible issue"],
        remediation=["restart service"],
        confidence_note="Moderate confidence detection.",
        confidence_score=confidence,
        confidence_label="High" if confidence >= 0.8 else "Medium",
        what_happened="A behavior anomaly was detected.",
        why_it_matters="This anomaly should be reviewed with correlated indicators.",
        technical_explanation="Anomaly type and evidence are derived from deterministic heuristics.",
    )

    return AnalysisReport(
        log_entry=_make_entry(line_number, message=message, ts=ts),
        anomaly=AnomalyResult(is_anomaly=True, confidence=confidence, anomaly_type="repeated_error", details="details"),
        severity=SeverityResult(level=severity, score=0.9),
        explanation=explanation,
    )


class TestRootCauseEngine:
    def test_groups_and_recommends_timeout_actions(self):
        base = datetime(2024, 1, 15, 14, 0, 0)
        # Same template within time window.
        msg1 = "ERROR CODE: ERR_TIMEOUT_001 connection timed out from 192.168.1.10"
        msg2 = "ERROR CODE: ERR_TIMEOUT_001 connection timed out from 192.168.1.20"
        msg3 = "ERROR CODE: ERR_TIMEOUT_001 connection timed out from 192.168.1.30"

        reports = [
            _make_report(1, message=msg1, ts=base),
            _make_report(2, message=msg2, ts=base + timedelta(seconds=20)),
            _make_report(3, message=msg3, ts=base + timedelta(seconds=40), severity=SeverityLevel.CRITICAL),
        ]

        root_causes = build_root_causes(reports, time_window_seconds=300, min_group_size=2)
        assert len(root_causes) >= 1

        top = root_causes[0]
        assert "timeout" in (top.summary + " " + top.title).lower() or "timed" in top.title.lower()
        assert top.recommended_action, "Expected non-empty remediation guidance"
        assert any("downstream dependency health" in a.lower() for a in top.recommended_action)
        assert top.confidence > 0.0


class TestPatternAnalyzer:
    def test_detects_frequency_spike_and_repeating_sequence(self):
        # 9 buckets with bucket_minutes=15 -> 2h window.
        bucket_minutes = 15
        start = datetime(2024, 1, 15, 10, 0, 0)

        template = "ERROR: authentication failed for user from 10.0.0.1"

        reports = []
        # Spike bucket (bucket 0): many events tightly packed.
        for i in range(40):
            reports.append(
                _make_report(
                    i + 1,
                    message=template,
                    ts=start + timedelta(seconds=i),  # gaps <= sequence_gap_seconds
                    severity=SeverityLevel.HIGH,
                    confidence=0.9,
                )
            )
        # End bucket (bucket 8): a single event.
        end_ts = start + timedelta(minutes=bucket_minutes * 8)
        reports.append(
            _make_report(
                999,
                message=template,
                ts=end_ts,
                severity=SeverityLevel.HIGH,
                confidence=0.7,
            )
        )

        patterns = detect_patterns(reports, bucket_minutes=bucket_minutes, spike_zscore=2.0)
        insight_types = {p.insight_type for p in patterns}
        assert "frequency_spike" in insight_types
        assert "repeating_sequence" in insight_types


class TestSummaryBuilder:
    def test_build_summary_report_has_expected_fields(self):
        root_causes = [
            type(
                "RC",
                (),
                {
                    "title": "Incident A",
                    "summary": "Summary A",
                    "related_logs": [1, 2],
                    "confidence": 0.7,
                    "severity": "HIGH",
                    "recommended_action": ["Check dependency health"],
                    "evidence": {},
                    "to_dict": lambda self: {
                        "title": "Incident A",
                        "summary": "Summary A",
                        "related_logs": [1, 2],
                        "confidence": 0.7,
                        "severity": "HIGH",
                        "recommended_action": ["Check dependency health"],
                        "evidence": {},
                    },
                },
            )()
        ]
        patterns = [
            type(
                "PI",
                (),
                {
                    "insight_type": "frequency_spike",
                    "title": "Spike",
                    "summary": "Volume spiked",
                    "confidence": 0.6,
                    "evidence": {},
                    "to_dict": lambda self: {
                        "insight_type": "frequency_spike",
                        "title": "Spike",
                        "summary": "Volume spiked",
                        "confidence": 0.6,
                        "evidence": {},
                    },
                },
            )()
        ]
        severity_distribution = {"LOW": 0, "MEDIUM": 0, "HIGH": 10, "CRITICAL": 2}

        report = build_summary_report(
            period_hours=2,
            total_entries=12,
            anomaly_count=8,
            severity_distribution=severity_distribution,
            root_causes=root_causes,
            patterns=patterns,
            cluster_distribution=[{"cluster_id": 1, "cluster_size": 6, "representative": "rep"}],
            charts={"dummy": True},
        )

        assert report["executive_summary"]
        assert report["risk_assessment"]["risk_level"] in ("HIGH", "CRITICAL")
        assert isinstance(report["recommended_actions"], list)
        assert report["key_anomalies"]["root_causes"][0]["title"] == "Incident A"


class TestDeepExplainer:
    def test_upgrades_explanations_structure(self):
        base = datetime(2024, 1, 15, 14, 0, 0)
        msg = "ERROR CODE: ERR_TIMEOUT_001 connection timed out from 192.168.1.10"

        reports = [
            _make_report(1, message=msg, ts=base, severity=SeverityLevel.HIGH, confidence=0.9),
            _make_report(2, message=msg, ts=base + timedelta(seconds=30), severity=SeverityLevel.HIGH, confidence=0.85),
            _make_report(3, message=msg, ts=base + timedelta(seconds=60), severity=SeverityLevel.CRITICAL, confidence=0.92),
        ]

        upgraded = upgrade_explanations(reports)
        assert set(upgraded.keys()) == {1, 2, 3}

        exp = upgraded[1]
        assert exp.summary
        assert exp.what_happened
        assert exp.why_it_matters
        assert exp.technical_explanation
        assert exp.possible_causes
        assert exp.remediation
        assert 0.0 <= exp.confidence_score <= 1.0

