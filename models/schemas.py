"""
Core data schemas for the Intelligent Log Analyzer.

All inter-module communication uses these dataclasses.
No module may define its own ad-hoc schema for log data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional


class LogLevel(str, Enum):
    """Standardized log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class SeverityLevel(str, Enum):
    """Severity classification for analyzed log entries."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class LogEntry:
    """
    Represents a single parsed log entry.

    This is the primary data unit flowing through the pipeline.
    Fields that cannot be extracted are left as None.
    """
    raw: str
    line_number: int
    timestamp: Optional[datetime] = None
    log_level: LogLevel = LogLevel.UNKNOWN
    message: str = ""
    source: str = ""
    ip_address: Optional[str] = None
    username: Optional[str] = None
    error_code: Optional[str] = None
    log_type: str = "UNCLASSIFIED"
    # Metadata set by downstream modules
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dictionary, converting datetime to ISO string."""
        result = asdict(self)
        if result["timestamp"] is not None:
            result["timestamp"] = result["timestamp"].isoformat()
        result["log_level"] = self.log_level.value
        return result


@dataclass
class AnomalyResult:
    """
    Result of anomaly detection for a single log entry.

    Attributes:
        is_anomaly: Whether this entry is flagged as anomalous.
        confidence: Confidence score between 0.0 and 1.0.
        anomaly_type: Description of the anomaly type detected.
        rule_score: Score from rule-based detection (0.0–1.0).
        ml_score: Score from ML-based detection (0.0–1.0).
        details: Additional context about the anomaly.
    """
    is_anomaly: bool = False
    confidence: float = 0.0
    anomaly_type: str = "none"
    rule_score: float = 0.0
    ml_score: float = 0.0
    statistical_score: float = 0.0
    details: str = ""


@dataclass
class SeverityResult:
    """
    Severity scoring result for a log entry.

    Attributes:
        level: Categorical severity level.
        score: Numeric severity score (0.0–1.0).
        breakdown: Component scores that contributed to the final score.
    """
    level: SeverityLevel = SeverityLevel.LOW
    score: float = 0.0
    breakdown: dict = field(default_factory=dict)


@dataclass
class Explanation:
    """
    Human-readable explanation of a log anomaly.

    Attributes:
        summary: One-line summary of the issue.
        possible_causes: List of potential root causes.
        remediation: Suggested actions to resolve the issue.
        confidence_note: Caveat about the explanation's certainty.
    """
    summary: str = ""
    possible_causes: list[str] = field(default_factory=list)
    remediation: list[str] = field(default_factory=list)
    confidence_note: str = ""


@dataclass
class AnalysisReport:
    """
    Complete analysis result for a single log entry.

    Combines the parsed entry, anomaly result, severity, and explanation
    into a single exportable object.
    """
    log_entry: LogEntry
    anomaly: AnomalyResult
    severity: SeverityResult
    explanation: Explanation

    def to_dict(self) -> dict:
        """Serialize entire report to a JSON-compatible dictionary."""
        return {
            "log_entry": self.log_entry.to_dict(),
            "anomaly": asdict(self.anomaly),
            "severity": {
                "level": self.severity.level.value,
                "score": self.severity.score,
                "breakdown": self.severity.breakdown,
            },
            "explanation": asdict(self.explanation),
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class AlertConfig:
    """Configuration for an alert rule."""
    name: str
    severity_threshold: Optional[str] = None  # e.g., "CRITICAL"
    match_keyword: Optional[str] = None       # e.g., "database"
    cooldown_seconds: int = 300               # 5 minutes default
    enabled: bool = True

@dataclass
class Alert:
    """A triggered alert."""
    rule_name: str
    timestamp: datetime
    message: str
    log_entry: LogEntry
    severity: str
    details: str


# ── Phase 4 Schemas ──────────────────────────────────────────────────


@dataclass
class RootCauseEvent:
    """
    A grouped root cause incident.

    Collapses many related log entries into a single actionable event.
    """
    event_id: int
    title: str
    description: str
    time_window: Optional[tuple[str, str]]  # (ISO start, ISO end)
    confidence: float  # 0.0–1.0
    related_log_ids: list[int] = field(default_factory=list)
    severity: str = "LOW"
    template_pattern: str = ""
    event_count: int = 0

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            "event_id": self.event_id,
            "title": self.title,
            "description": self.description,
            "time_window": self.time_window,
            "confidence": self.confidence,
            "related_log_ids": self.related_log_ids,
            "severity": self.severity,
            "template_pattern": self.template_pattern,
            "event_count": self.event_count,
        }


@dataclass
class TimelineEvent:
    """
    A time-bucketed event cluster for timeline visualization.
    """
    bucket_start: str  # ISO timestamp
    bucket_end: str    # ISO timestamp
    event_count: int = 0
    severity_counts: dict = field(default_factory=dict)
    is_spike: bool = False
    top_events: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "bucket_start": self.bucket_start,
            "bucket_end": self.bucket_end,
            "event_count": self.event_count,
            "severity_counts": self.severity_counts,
            "is_spike": self.is_spike,
            "top_events": self.top_events,
        }


@dataclass
class JobStatus:
    """
    Status of an async analysis job.
    """
    job_id: str
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_entries: int = 0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "total_entries": self.total_entries,
            "error": self.error,
        }

