"""
Database persistence layer using SQLAlchemy Core.

Handles SQLite connection, schema definition, and high-performance insertions.
Avoids ORM overhead for maximum ingestion throughput.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    Index,
    inspect,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from models.schemas import AnalysisReport

logger = logging.getLogger(__name__)

# Default DB path relative to project root
DEFAULT_DB_PATH = Path("logs.db")

# ─── Schema Definition ────────────────────────────────────────────────

metadata = MetaData()

logs_table = Table(
    "logs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("timestamp", DateTime, nullable=True, index=True),
    Column("log_level", String(20), nullable=True),
    Column("message", Text, nullable=False),
    Column("source", String(255), nullable=True),
    Column("line_number", Integer, nullable=False),
    Column("anomaly_score", Float, nullable=False, default=0.0),
    Column("severity", String(20), nullable=False, index=True),
    Column("explanation", Text, nullable=True),  # JSON-serialized explanation
    Column("created_at", DateTime, default=datetime.utcnow),
    # Indexes for common queries
    Index("idx_logs_severity_timestamp", "severity", "timestamp"),
)


class Database:
    """
    Manages SQLite database connection and operations.
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = str(db_path)
        self.engine: Engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False,
            future=True,
            connect_args={"check_same_thread": False},  # Allow multithreaded access
        )
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema if not exists."""
        try:
            metadata.create_all(self.engine)
            logger.info("Database initialized at %s", self.db_path)
        except SQLAlchemyError as e:
            logger.error("Failed to initialize database schema: %s", e)
            raise

    def get_connection(self):
        """Get a raw connection for direct execution."""
        return self.engine.connect()

    def insert_reports(self, reports: list[AnalysisReport]):
        """
        Bulk insert analysis reports.

        Args:
            reports: List of AnalysisReport objects.
        """
        if not reports:
            return

        import json
        from dataclasses import asdict

        data = []
        for r in reports:
            # Serialize explanation to JSON string
            explanation_json = json.dumps(asdict(r.explanation)) if r.explanation else "{}"

            row = {
                "timestamp": r.log_entry.timestamp,
                "log_level": r.log_entry.log_level.value,
                "message": r.log_entry.message,
                "source": r.log_entry.source,
                "line_number": r.log_entry.line_number,
                "anomaly_score": r.anomaly.confidence,
                "severity": r.severity.level.value,
                "explanation": explanation_json,
                "created_at": datetime.utcnow(),
            }
            data.append(row)

        try:
            with self.engine.begin() as conn:
                conn.execute(logs_table.insert(), data)
            logger.debug("Persisted %d log entries", len(data))
        except SQLAlchemyError as e:
            logger.error("Database insert failed: %s", e)
            raise

    def get_recent_reports(self, hours: int = 24) -> list[AnalysisReport]:
        """
        Retrieve recent reports from the database.

        Args:
            hours: Number of hours to look back.

        Returns:
            List of AnalysisReport objects reconstructed from DB rows.
        """
        import json
        from models.schemas import (
            LogEntry, AnomalyResult, SeverityResult, Explanation,
            LogLevel, SeverityLevel,
        )

        cutoff = datetime.utcnow() - timedelta(hours=hours)

        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    logs_table.select()
                    .where(logs_table.c.created_at >= cutoff)
                    .order_by(logs_table.c.timestamp.asc())
                )
                rows = result.fetchall()
        except SQLAlchemyError as e:
            logger.error("Failed to fetch recent reports: %s", e)
            return []

        reports = []
        for row in rows:
            # Parse explanation JSON
            explanation = Explanation()
            if row.explanation:
                try:
                    exp_data = json.loads(row.explanation)
                    explanation = Explanation(
                        summary=exp_data.get("summary", ""),
                        possible_causes=exp_data.get("possible_causes", []),
                        remediation=exp_data.get("remediation", []),
                        confidence_note=exp_data.get("confidence_note", ""),
                    )
                except (json.JSONDecodeError, TypeError):
                    pass

            # Map log level
            try:
                log_level = LogLevel(row.log_level)
            except (ValueError, KeyError):
                log_level = LogLevel.UNKNOWN

            # Map severity
            try:
                severity_level = SeverityLevel(row.severity)
            except (ValueError, KeyError):
                severity_level = SeverityLevel.LOW

            entry = LogEntry(
                raw=row.message,
                line_number=row.line_number,
                timestamp=row.timestamp,
                log_level=log_level,
                message=row.message,
                source=row.source or "",
            )

            report = AnalysisReport(
                log_entry=entry,
                anomaly=AnomalyResult(
                    is_anomaly=row.anomaly_score > 0.5,
                    confidence=row.anomaly_score,
                ),
                severity=SeverityResult(
                    level=severity_level,
                    score=row.anomaly_score,
                ),
                explanation=explanation,
            )
            reports.append(report)

        logger.debug("Retrieved %d reports from last %d hours", len(reports), hours)
        return reports

    def close(self):
        """Dispose of the engine connection pool."""
        self.engine.dispose()


# Global Singleton
_db_instance: Optional[Database] = None

def get_db(path: Optional[str] = None) -> Database:
    """Get or create regular database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(path or DEFAULT_DB_PATH)
    return _db_instance


def init_db(path: Optional[str] = None, force: bool = False):
    """Explicitly initialize the database."""
    global _db_instance
    if force and _db_instance:
        _db_instance.close()
        _db_instance = None
        
    get_db(path)

def close_db():
    """Close the database connection."""
    global _db_instance
    if _db_instance:
        _db_instance.close()
        _db_instance = None
