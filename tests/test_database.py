"""Tests for app.storage.database."""

import pytest
import datetime
from sqlalchemy import text
from app.storage.database import Database, logs_table, get_db
from models.schemas import AnalysisReport, LogEntry, LogLevel, AnomalyResult, SeverityResult, SeverityLevel, Explanation

@pytest.fixture
def test_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test_logs.db"
    db = Database(db_path)
    yield db
    db.close()

def test_init_schema(test_db):
    """Verify tables are created."""
    with test_db.get_connection() as conn:
        tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';")).fetchall()
        table_names = [t[0] for t in tables]
        assert "logs" in table_names

def test_insert_reports(test_db):
    """Verify insertion of reports."""
    entry = LogEntry(
        raw="test",
        line_number=1,
        timestamp=datetime.datetime.utcnow(),
        log_level=LogLevel.ERROR,
        message="Test Message",
        source="test_src",
        log_type="test"
    )
    report = AnalysisReport(
        log_entry=entry,
        anomaly=AnomalyResult(confidence=0.5),
        severity=SeverityResult(level=SeverityLevel.HIGH, score=0.8),
        explanation=Explanation(summary="test explanation")
    )
    
    test_db.insert_reports([report])
    
    with test_db.get_connection() as conn:
        result = conn.execute(text("SELECT * FROM logs")).fetchone()
        assert result is not None
        assert result.message == "Test Message"
        assert result.severity == "HIGH"
        assert result.anomaly_score == 0.5
