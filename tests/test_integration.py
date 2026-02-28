"""Integration tests — end-to-end pipeline and edge cases."""

import time
import pytest
from main import run_analysis
from app.ingestion.reader import ReaderError


class TestEndToEndPipeline:
    """Full pipeline integration tests."""

    def test_syslog_full_pipeline(self, sample_log_path):
        reports = run_analysis(sample_log_path)
        assert len(reports) > 0
        # Every report should have all components
        for r in reports:
            assert r.log_entry is not None
            assert r.anomaly is not None
            assert r.severity is not None
            assert r.explanation is not None

    def test_python_log_full_pipeline(self, python_log_path):
        reports = run_analysis(python_log_path)
        assert len(reports) > 0

    def test_serialization(self, sample_log_path):
        """Reports should serialize to valid JSON."""
        reports = run_analysis(sample_log_path)
        for r in reports:
            d = r.to_dict()
            assert isinstance(d, dict)
            assert "log_entry" in d
            json_str = r.to_json()
            assert isinstance(json_str, str)


class TestEdgeCases:
    """Edge case tests required by QA spec."""

    def test_empty_file(self, empty_log_path):
        """Empty file should raise ReaderError."""
        with pytest.raises(ReaderError):
            run_analysis(empty_log_path)

    def test_corrupted_log(self, corrupted_log_path):
        """Corrupted/unknown format should still parse without crashing."""
        reports = run_analysis(corrupted_log_path)
        assert len(reports) > 0
        # All entries should be UNCLASSIFIED (anti-hallucination)
        for r in reports:
            assert r.log_entry.log_type == "UNCLASSIFIED"

    def test_unknown_format(self, tmp_log_file):
        """Completely unknown format should produce UNCLASSIFIED entries."""
        content = "abc\ndef\nghi\njkl\n"
        path = tmp_log_file(content)
        reports = run_analysis(path)
        for r in reports:
            assert r.log_entry.log_type == "UNCLASSIFIED"

    def test_large_file_performance(self, large_log_path):
        """10,000-line file should complete in reasonable time."""
        start = time.time()
        reports = run_analysis(large_log_path)
        elapsed = time.time() - start
        assert len(reports) == 10_000
        # Should complete in under 30s (generous for CI environments)
        assert elapsed < 30, f"Pipeline took too long: {elapsed:.1f}s"

    def test_single_line_file(self, tmp_log_file):
        """Single-line file should work."""
        path = tmp_log_file("Jan 15 10:30:45 host app[1]: INFO: single entry\n")
        reports = run_analysis(path)
        assert len(reports) == 1

    def test_nonexistent_file(self):
        """Non-existent file should raise ReaderError."""
        with pytest.raises(ReaderError):
            run_analysis("/nonexistent/path/file.log")

    def test_wrong_extension(self, tmp_path):
        """Wrong extension should raise ReaderError."""
        f = tmp_path / "data.csv"
        f.write_text("data")
        with pytest.raises(ReaderError):
            run_analysis(str(f))


class TestAnomalyDetectionIntegration:
    """Verify anomalies are detected in sample data."""

    def test_oom_detected(self, sample_log_path):
        """The sample log has an OOM entry — should be flagged."""
        reports = run_analysis(sample_log_path)
        oom_reports = [
            r for r in reports
            if "out of memory" in r.log_entry.message.lower()
            or "oom" in r.log_entry.message.lower()
        ]
        assert len(oom_reports) > 0
        for r in oom_reports:
            assert r.anomaly.is_anomaly

    def test_segfault_detected(self, sample_log_path):
        """The sample log has a segfault — should be flagged."""
        reports = run_analysis(sample_log_path)
        segfault_reports = [
            r for r in reports
            if "segfault" in r.log_entry.message.lower()
        ]
        assert len(segfault_reports) > 0
        for r in segfault_reports:
            assert r.anomaly.is_anomaly
