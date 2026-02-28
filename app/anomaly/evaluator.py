"""
Anomaly evaluator — combines rule-based, ML-based, and statistical detection.

Produces a unified AnomalyResult per entry using a 3-way weighted
combination:
    combined = rule_weight * rule_score
             + ml_weight * ml_score
             + stat_weight * statistical_score

Default weights: rule=0.4, ml=0.3, statistical=0.3
"""

from __future__ import annotations

from typing import Optional

from app.anomaly.rule_engine import run_rule_engine
from app.anomaly.ml_engine import run_ml_engine
from app.anomaly.zscore_detector import run_zscore_detector
from app.config.settings import DEFAULT_CONFIG, AnomalyConfig
from app.utils.helpers import clamp
from models.schemas import LogEntry, AnomalyResult


# Default weights for the 3-way combination
_RULE_WEIGHT = 0.4
_ML_WEIGHT = 0.3
_STAT_WEIGHT = 0.3


def evaluate_anomalies(
    entries: list[LogEntry],
    config: Optional[AnomalyConfig] = None,
) -> dict[int, AnomalyResult]:
    """
    Run all three anomaly detection engines and combine their results.

    The combined score is:
        combined = 0.4 * rule_score + 0.3 * ml_score + 0.3 * stat_score

    An entry is flagged as anomalous if:
        - Any engine flags it strongly (rule_score > 0.5, ml > 0.7, stat > 0.5)
        - Combined score exceeds 0.45

    Args:
        entries: All parsed log entries.
        config: Anomaly config override.

    Returns:
        Dict mapping line_number → AnomalyResult.
    """
    cfg = config or DEFAULT_CONFIG.anomaly

    # Run all three engines
    rule_results = run_rule_engine(entries, cfg)
    ml_scores = run_ml_engine(entries, cfg)
    stat_scores = run_zscore_detector(entries, config=cfg)

    combined_results: dict[int, AnomalyResult] = {}

    for entry in entries:
        rule_result = rule_results.get(entry.line_number, AnomalyResult())
        ml_score = ml_scores.get(entry.line_number, 0.0)
        stat_score = stat_scores.get(entry.line_number, 0.0)

        # 3-way weighted combination
        combined_score = clamp(
            _RULE_WEIGHT * rule_result.rule_score
            + _ML_WEIGHT * ml_score
            + _STAT_WEIGHT * stat_score
        )

        # Determine if anomalous
        is_anomaly = (
            rule_result.is_anomaly
            or ml_score > 0.7
            or stat_score > 0.5
            or combined_score > 0.45
        )

        # Build details string
        details_parts = []
        if rule_result.details:
            details_parts.append(f"Rule: {rule_result.details}")
        if ml_score > 0.3:
            details_parts.append(f"ML score: {ml_score:.2f}")
        if stat_score > 0.2:
            details_parts.append(f"Z-score deviation: {stat_score:.2f}")

        # Determine anomaly type from highest contributing signal
        if rule_result.is_anomaly and rule_result.rule_score >= max(ml_score, stat_score):
            anomaly_type = rule_result.anomaly_type
        elif ml_score >= stat_score and ml_score > 0.5:
            anomaly_type = "ml_detected"
        elif stat_score > 0.3:
            anomaly_type = "statistical_outlier"
        else:
            anomaly_type = rule_result.anomaly_type if rule_result.is_anomaly else "none"

        combined_results[entry.line_number] = AnomalyResult(
            is_anomaly=is_anomaly,
            confidence=combined_score,
            anomaly_type=anomaly_type,
            rule_score=rule_result.rule_score,
            ml_score=ml_score,
            statistical_score=stat_score,
            details="; ".join(details_parts) if details_parts else "",
        )

    return combined_results
