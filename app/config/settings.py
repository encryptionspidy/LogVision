"""
Central configuration for the Intelligent Log Analyzer.

All tunable parameters live here. No module should hardcode thresholds.
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict


@dataclass(frozen=True)
class IngestionConfig:
    """Configuration for the ingestion module."""
    # Maximum file size in bytes (100 MB)
    max_file_size_bytes: int = 100 * 1024 * 1024
    # Number of bytes to sample for encoding detection
    encoding_sample_bytes: int = 10_240
    # Allowed file extensions
    allowed_extensions: tuple[str, ...] = (".log", ".txt", ".json")
    # Read buffer size for streaming
    read_buffer_size: int = 8192


@dataclass(frozen=True)
class ParsingConfig:
    """Configuration for the parsing module."""
    # Number of lines to sample for log type auto-detection
    auto_detect_sample_lines: int = 20
    # Maximum line length before truncation (characters)
    max_line_length: int = 10_000


@dataclass(frozen=True)
class AnomalyConfig:
    """Configuration for anomaly detection."""
    # Rule engine
    frequency_window_seconds: int = 60
    frequency_spike_threshold: int = 10
    critical_keywords: tuple[str, ...] = (
        "fatal", "oom", "out of memory", "segfault", "segmentation fault",
        "kernel panic", "stack overflow", "deadlock", "corruption",
        "permission denied", "unauthorized", "brute force",
    )
    # ML engine
    isolation_forest_contamination: float = 0.1
    isolation_forest_n_estimators: int = 100
    isolation_forest_random_state: int = 42
    # Minimum entries required to run ML engine
    min_entries_for_ml: int = 30
    # Evaluator weights
    rule_weight: float = 0.6
    ml_weight: float = 0.4


@dataclass(frozen=True)
class SeverityConfig:
    """Configuration for severity scoring."""
    # Component weights (must sum to 1.0)
    rule_weight: float = 0.35
    frequency_weight: float = 0.25
    anomaly_weight: float = 0.40
    # Severity thresholds (score → level)
    critical_threshold: float = 0.80
    high_threshold: float = 0.60
    medium_threshold: float = 0.35
    # Log level severity base scores
    level_base_scores: dict = field(default_factory=lambda: {
        "DEBUG": 0.0,
        "INFO": 0.05,
        "WARNING": 0.30,
        "ERROR": 0.60,
        "CRITICAL": 0.90,
        "UNKNOWN": 0.20,
    })


@dataclass(frozen=True)
class ExplanationConfig:
    """Configuration for explanation generation."""
    # Template directory (if we move templates to files)
    template_dir: Optional[str] = None
    # Maximum length of explanation summary
    max_summary_length: int = 200


@dataclass(frozen=True)
class APIConfig:
    """Configuration for the Flask API."""
    host: str = "0.0.0.0"
    port: int = 5000
    debug: bool = False
    max_content_length_mb: int = 16


@dataclass(frozen=True)
class MonitorConfig:
    """Monitoring configuration."""
    log_path: Optional[str] = os.getenv("MONITOR_LOG_PATH", None)
    enabled: bool = os.getenv("MONITOR_ENABLED", "false").lower() == "true"


@dataclass(frozen=True)
class AppConfig:
    """Root configuration aggregating all module configs."""
    ingestion: IngestionConfig = field(default_factory=IngestionConfig)
    parsing: ParsingConfig = field(default_factory=ParsingConfig)
    anomaly: AnomalyConfig = field(default_factory=AnomalyConfig)
    severity: SeverityConfig = field(default_factory=SeverityConfig)
    explanation: ExplanationConfig = field(default_factory=ExplanationConfig)
    api: APIConfig = field(default_factory=APIConfig)
    monitor: MonitorConfig = field(default_factory=MonitorConfig)


# Singleton config instance — import this throughout the project
# ASSUMPTION: Config is immutable at runtime (frozen dataclasses)
DEFAULT_CONFIG = AppConfig()
DEFAULT_CONFIG = AppConfig()
