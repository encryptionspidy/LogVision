"""
Log clustering engine using TF-IDF + MiniBatchKMeans.

Groups structurally similar log messages to:
- Reduce noise by collapsing repeated patterns
- Improve anomaly confidence by identifying outlier clusters
- Provide cluster-level summaries for analytics

No pre-trained models. Clustering is performed per-batch.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from models.schemas import LogEntry

logger = logging.getLogger(__name__)

# Regex to normalize variable parts before vectorization
_VAR_PATTERNS = [
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "<IP>"),
    (re.compile(r"\b[0-9a-fA-F]{8,}\b"), "<HEX>"),
    (re.compile(r"/[^\s]+"), "<PATH>"),
    (re.compile(r"\d+"), "<NUM>"),
]


@dataclass
class ClusterResult:
    """Result of clustering a batch of log entries."""

    cluster_id: int
    cluster_size: int
    representative: str  # Most central message in the cluster
    is_outlier: bool  # True if cluster_size == 1 or very small


@dataclass
class ClusterSummary:
    """Summary of all clusters in a batch."""

    n_clusters: int
    assignments: dict[int, int]  # line_number -> cluster_id
    clusters: dict[int, ClusterResult]  # cluster_id -> result
    outlier_line_numbers: list[int]


def _normalize_message(message: str) -> str:
    """Replace variable tokens with placeholders for better vectorization."""
    text = message.lower().strip()
    for pattern, replacement in _VAR_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def cluster_logs(
    entries: list[LogEntry],
    max_clusters: int = 20,
    min_cluster_size: int = 2,
) -> Optional[ClusterSummary]:
    """
    Cluster log entries by message similarity.

    Uses TF-IDF to vectorize normalized messages, then MiniBatchKMeans
    to group them. Clusters with size < min_cluster_size are marked
    as outliers.

    Args:
        entries: Parsed log entries.
        max_clusters: Maximum clusters to create. Actual count is
                      min(max_clusters, n_entries // 2).
        min_cluster_size: Clusters smaller than this are outliers.

    Returns:
        ClusterSummary, or None if fewer than 3 entries.
    """
    if len(entries) < 3:
        logger.info("Too few entries for clustering (%d)", len(entries))
        return None

    # Normalize messages
    normalized = [_normalize_message(e.message) for e in entries]

    # TF-IDF vectorization
    vectorizer = TfidfVectorizer(
        max_features=500,
        stop_words="english",
        max_df=0.95,
        min_df=1,
        ngram_range=(1, 2),
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(normalized)
    except ValueError as e:
        logger.warning("TF-IDF failed: %s", e)
        return None

    # Determine cluster count
    n_clusters = min(max_clusters, max(2, len(entries) // 3))

    # Cluster
    kmeans = MiniBatchKMeans(
        n_clusters=n_clusters,
        random_state=42,
        batch_size=min(256, len(entries)),
        n_init=3,
    )
    labels = kmeans.fit_predict(tfidf_matrix)

    # Build results
    from collections import Counter

    label_counts = Counter(labels)
    assignments: dict[int, int] = {}
    clusters: dict[int, ClusterResult] = {}
    outlier_lines: list[int] = []

    # Find representative message per cluster (closest to centroid)
    for cluster_id in range(n_clusters):
        mask = labels == cluster_id
        if not mask.any():
            continue

        cluster_indices = np.where(mask)[0]
        cluster_size = len(cluster_indices)

        # Find representative: closest to centroid
        centroid = kmeans.cluster_centers_[cluster_id]
        cluster_vectors = tfidf_matrix[cluster_indices]
        # sparse - dense may return np.matrix; convert to ndarray
        diff = np.asarray(cluster_vectors.toarray()) - centroid
        distances = np.sum(diff ** 2, axis=1)
        rep_idx = cluster_indices[distances.argmin()]

        is_outlier = cluster_size < min_cluster_size

        clusters[int(cluster_id)] = ClusterResult(
            cluster_id=int(cluster_id),
            cluster_size=cluster_size,
            representative=entries[rep_idx].message[:200],
            is_outlier=is_outlier,
        )

        for idx in cluster_indices:
            line_num = entries[idx].line_number
            assignments[line_num] = int(cluster_id)
            if is_outlier:
                outlier_lines.append(line_num)

    return ClusterSummary(
        n_clusters=len(clusters),
        assignments=assignments,
        clusters=clusters,
        outlier_line_numbers=outlier_lines,
    )
