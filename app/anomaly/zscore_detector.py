"""
Statistical anomaly detector using z-score on feature vectors.

Computes a moving-average baseline from batch statistics and flags
entries whose feature values deviate significantly (|z| > threshold).

This provides a third detection signal that is:
- Independent of ML (no model training)
- Independent of rules (no keyword lists)
- Based purely on statistical deviation from the batch norm
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from app.anomaly.ml_engine import extract_feature_matrix
from app.config.settings import DEFAULT_CONFIG, AnomalyConfig
from app.utils.helpers import clamp
from models.schemas import LogEntry

logger = logging.getLogger(__name__)


def run_zscore_detector(
    entries: list[LogEntry],
    z_threshold: float = 2.0,
    config: Optional[AnomalyConfig] = None,
) -> dict[int, float]:
    """
    Detect statistical outliers via z-score analysis.

    Uses the same feature extraction as the ML engine, then computes
    per-feature z-scores. The maximum absolute z-score across features
    is used as the anomaly signal.

    Args:
        entries: All parsed log entries.
        z_threshold: Z-score threshold above which an entry is anomalous.
        config: Optional config override.

    Returns:
        Dict mapping line_number → anomaly score (0.0–1.0).
    """
    if len(entries) < 3:
        return {e.line_number: 0.0 for e in entries}

    # Reuse the same features as the ML engine for consistency
    feature_matrix = extract_feature_matrix(entries)

    # Compute per-feature mean and std
    means = np.mean(feature_matrix, axis=0)
    stds = np.std(feature_matrix, axis=0)

    # Avoid division by zero — set std=1 for constant features
    stds[stds < 1e-10] = 1.0

    # Z-scores: (value - mean) / std
    z_scores = np.abs((feature_matrix - means) / stds)

    # Maximum z-score across all features for each entry
    max_z = np.max(z_scores, axis=1)

    # Normalize to [0, 1]: z_threshold maps to ~0.5, 2*z_threshold maps to ~1.0
    results: dict[int, float] = {}
    for i, entry in enumerate(entries):
        z = float(max_z[i])
        if z < z_threshold:
            score = 0.0
        else:
            # Sigmoid-like scaling: higher z → closer to 1.0
            score = clamp(1.0 - 1.0 / (1.0 + (z - z_threshold)))
        results[entry.line_number] = score

    n_flagged = sum(1 for s in results.values() if s > 0)
    logger.info(
        "Z-score detector: %d/%d entries flagged (threshold=%.1f)",
        n_flagged,
        len(entries),
        z_threshold,
    )

    return results
