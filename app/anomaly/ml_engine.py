"""
ML-based anomaly detection using Isolation Forest.

Extracts numerical features from log entries and trains an
Isolation Forest model on the batch to detect outliers.

IMPORTANT: The model is trained fresh on each batch — there is
no pre-trained model. This is intentional to avoid hallucinating
performance metrics from non-existent training data.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from app.config.settings import DEFAULT_CONFIG, AnomalyConfig
from app.utils.helpers import clamp
from models.schemas import LogEntry, LogLevel

logger = logging.getLogger(__name__)


# ─── Feature Extraction ─────────────────────────────────────────────────

# Keywords that suggest problems — used as a feature dimension
_ERROR_KEYWORDS = (
    "error", "fail", "exception", "timeout", "refused",
    "denied", "crash", "abort", "fatal", "panic",
)

# Log level to numeric severity for feature encoding
_LEVEL_TO_NUMERIC: dict[LogLevel, float] = {
    LogLevel.DEBUG: 0.0,
    LogLevel.INFO: 0.2,
    LogLevel.WARNING: 0.5,
    LogLevel.ERROR: 0.8,
    LogLevel.CRITICAL: 1.0,
    LogLevel.UNKNOWN: 0.3,
}


def extract_features(entry: LogEntry) -> list[float]:
    """
    Extract numerical features from a single log entry.

    Features:
    1. Hour of day (0–23 normalized to 0–1), or 0.5 if no timestamp.
    2. Log level severity (0–1).
    3. Message length (log-scaled, normalized).
    4. Word count (normalized).
    5. Error keyword count.
    6. Has IP address (0 or 1).
    7. Has error code (0 or 1).

    Args:
        entry: Parsed log entry.

    Returns:
        List of 7 float features.
    """
    # Feature 1: Hour of day
    if entry.timestamp is not None:
        hour = entry.timestamp.hour / 23.0
    else:
        hour = 0.5  # Neutral value when timestamp is missing

    # Feature 2: Log level severity
    level_score = _LEVEL_TO_NUMERIC.get(entry.log_level, 0.3)

    # Feature 3: Message length (log-normalized)
    msg_len = len(entry.message)
    msg_len_normalized = min(np.log1p(msg_len) / 10.0, 1.0)

    # Feature 4: Word count (normalized)
    word_count = len(entry.message.split())
    word_count_normalized = min(word_count / 50.0, 1.0)

    # Feature 5: Error keyword count
    msg_lower = entry.message.lower()
    keyword_count = sum(1 for kw in _ERROR_KEYWORDS if kw in msg_lower)
    keyword_score = min(keyword_count / 5.0, 1.0)

    # Feature 6: Has IP
    has_ip = 1.0 if entry.ip_address else 0.0

    # Feature 7: Has error code
    has_error_code = 1.0 if entry.error_code else 0.0

    return [
        hour,
        level_score,
        msg_len_normalized,
        word_count_normalized,
        keyword_score,
        has_ip,
        has_error_code,
    ]


def extract_feature_matrix(entries: list[LogEntry]) -> np.ndarray:
    """
    Build a feature matrix from a list of log entries.

    Args:
        entries: List of parsed log entries.

    Returns:
        numpy array of shape (n_entries, 7).
    """
    if not entries:
        return np.empty((0, 7))

    features = [extract_features(e) for e in entries]
    return np.array(features, dtype=np.float64)


# ─── Isolation Forest ────────────────────────────────────────────────────

def run_ml_engine(
    entries: list[LogEntry],
    config: Optional[AnomalyConfig] = None,
) -> dict[int, float]:
    """
    Run Isolation Forest anomaly detection on log entries.

    The model is trained on the provided batch and used to score each entry.
    Scores are normalized to [0, 1] where higher = more anomalous.

    If there are fewer entries than the configured minimum, returns
    0.0 for all entries (not enough data for meaningful ML detection).

    Args:
        entries: All parsed log entries.
        config: Anomaly config override.

    Returns:
        Dict mapping line_number → anomaly score (0.0–1.0).
    """
    cfg = config or DEFAULT_CONFIG.anomaly

    # Not enough data for ML — return neutral scores
    if len(entries) < cfg.min_entries_for_ml:
        logger.info(
            "Skipping ML engine: only %d entries (minimum: %d)",
            len(entries),
            cfg.min_entries_for_ml,
        )
        return {e.line_number: 0.0 for e in entries}

    # Extract features
    feature_matrix = extract_feature_matrix(entries)

    # Lazy import to avoid paying sklearn import cost when not needed
    from sklearn.ensemble import IsolationForest

    # Train on this batch
    # ASSUMPTION: No pre-trained model exists. We train fresh each time.
    model = IsolationForest(
        n_estimators=cfg.isolation_forest_n_estimators,
        contamination=cfg.isolation_forest_contamination,
        random_state=cfg.isolation_forest_random_state,
        n_jobs=-1,
    )

    try:
        model.fit(feature_matrix)
    except Exception as e:
        logger.warning("ML engine training failed: %s", e)
        return {entry.line_number: 0.0 for entry in entries}

    # Score entries
    # decision_function returns: negative = anomaly, positive = normal
    raw_scores = model.decision_function(feature_matrix)

    # Normalize to [0, 1] where 1 = most anomalous
    min_score = raw_scores.min()
    max_score = raw_scores.max()

    if max_score - min_score < 1e-10:
        # All entries scored the same — no meaningful differentiation
        return {entry.line_number: 0.0 for entry in entries}

    normalized = 1.0 - (raw_scores - min_score) / (max_score - min_score)

    results: dict[int, float] = {}
    for i, entry in enumerate(entries):
        results[entry.line_number] = float(clamp(normalized[i]))

    return results
