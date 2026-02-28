"""Tests for the timeline builder."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.timeline.timeline_builder import build_timeline, _mean_std, _bucket_key
from models.schemas import (
    AnalysisReport, LogEntry, AnomalyResult, SeverityResult,
    Explanation, SeverityLevel, LogLevel,
)


def _make_report(
    line: int,
    message: str = "Test message",
    severity: SeverityLevel = SeverityLevel.MEDIUM,
    timestamp: datetime | None = None,
) -> AnalysisReport:
    return AnalysisReport(
        log_entry=LogEntry(
            raw=message,
            line_number=line,
            message=message,
            timestamp=timestamp,
            log_level=LogLevel.ERROR,
        ),
        anomaly=AnomalyResult(is_anomaly=True, confidence=0.8),
        severity=SeverityResult(level=severity, score=0.7),
        explanation=Explanation(summary="Test"),
    )


class TestBuildTimeline:
    def test_empty_input(self):
        result = build_timeline([])
        assert result == []

    def test_no_timestamped_reports(self):
        reports = [_make_report(1, timestamp=None)]
        result = build_timeline(reports)
        assert result == []

    def test_produces_buckets(self):
        ref = datetime(2024, 1, 15, 15, 0, 0)
        reports = [
            _make_report(i, timestamp=ref - timedelta(minutes=i * 10))
            for i in range(1, 7)
        ]
        result = build_timeline(reports, hours=2, bucket_minutes=15, reference_time=ref)
        assert len(result) > 0
        # All buckets should have the correct structure
        for event in result:
            assert event.bucket_start is not None
            assert event.bucket_end is not None
            assert isinstance(event.event_count, int)

    def test_spike_detection(self):
        """A bucket with many more events than average should be marked as spike."""
        ref = datetime(2024, 1, 15, 15, 0, 0)
        # Many events in one bucket, few in others
        big_cluster = [
            _make_report(i, timestamp=ref - timedelta(minutes=5))
            for i in range(20)
        ]
        sparse = [
            _make_report(100 + i, timestamp=ref - timedelta(hours=1, minutes=i * 10))
            for i in range(3)
        ]
        result = build_timeline(
            big_cluster + sparse,
            hours=3, bucket_minutes=15, reference_time=ref,
        )
        spikes = [e for e in result if e.is_spike]
        assert len(spikes) >= 1

    def test_severity_counts(self):
        ref = datetime(2024, 1, 15, 15, 0, 0)
        reports = [
            _make_report(1, severity=SeverityLevel.HIGH, timestamp=ref - timedelta(minutes=5)),
            _make_report(2, severity=SeverityLevel.HIGH, timestamp=ref - timedelta(minutes=5)),
            _make_report(3, severity=SeverityLevel.LOW, timestamp=ref - timedelta(minutes=5)),
        ]
        result = build_timeline(reports, hours=1, bucket_minutes=15, reference_time=ref)
        # Find bucket with events
        filled = [e for e in result if e.event_count > 0]
        assert len(filled) >= 1
        assert "HIGH" in filled[0].severity_counts

    def test_to_dict(self):
        ref = datetime(2024, 1, 15, 15, 0, 0)
        reports = [_make_report(1, timestamp=ref - timedelta(minutes=5))]
        result = build_timeline(reports, hours=1, bucket_minutes=15, reference_time=ref)
        for event in result:
            d = event.to_dict()
            assert "bucket_start" in d
            assert "is_spike" in d


class TestMeanStd:
    def test_empty(self):
        mean, std = _mean_std([])
        assert mean == 0.0
        assert std == 0.0

    def test_single_value(self):
        mean, std = _mean_std([5])
        assert mean == 5.0
        assert std == 0.0

    def test_known_values(self):
        mean, std = _mean_std([2, 4, 4, 4, 5, 5, 7, 9])
        assert abs(mean - 5.0) < 0.01
        assert std > 0


class TestBucketKey:
    def test_rounds_down(self):
        dt = datetime(2024, 1, 15, 14, 23, 45)
        result = _bucket_key(dt, 15)
        assert result == datetime(2024, 1, 15, 14, 15, 0)

    def test_already_on_boundary(self):
        dt = datetime(2024, 1, 15, 14, 30, 0)
        result = _bucket_key(dt, 15)
        assert result == datetime(2024, 1, 15, 14, 30, 0)
