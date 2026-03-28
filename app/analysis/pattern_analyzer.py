"""
Pattern analyzer — extracts higher-level behavioral signals.

This is intentionally deterministic and non-LLM: it derives insights from
time-bucketed counts, template repetition, and simple co-occurrence stats.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from app.clustering.template_miner import extract_template
from models.schemas import AnalysisReport


@dataclass
class PatternInsight:
    insight_type: str
    title: str
    summary: str
    confidence: float
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "insight_type": self.insight_type,
            "title": self.title,
            "summary": self.summary,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


_IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


def _bucket_key(dt: datetime, bucket_minutes: int) -> datetime:
    minute = (dt.minute // bucket_minutes) * bucket_minutes
    return dt.replace(minute=minute, second=0, microsecond=0)


def _mean_std(values: list[int]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, 0.0
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return mean, math.sqrt(variance)


def _z_score(value: int, mean: float, std: float) -> float:
    if std <= 0.0:
        return 0.0
    return (value - mean) / std


def detect_patterns(
    reports: list[AnalysisReport],
    *,
    bucket_minutes: int = 15,
    spike_zscore: float = 2.0,
    sequence_gap_seconds: int = 120,
) -> list[PatternInsight]:
    """
    Detect:
    - frequency spikes (z-score over time buckets)
    - repeating sequences (same template runs within short gaps)
    - correlated anomalies (template co-occurrence within windows)
    - unusual time gaps (outlier gaps between anomaly timestamps)
    - rare templates (low-frequency templates among anomalies)
    """
    if not reports:
        return []

    # We only reason about timestamps and messages; reports should already
    # be filtered to anomalies for the intended use-cases.
    timed = [r for r in reports if r.log_entry.timestamp is not None]
    if not timed:
        return []

    timed.sort(key=lambda r: r.log_entry.timestamp)  # type: ignore[arg-type]

    templates = [extract_template(r.log_entry.message) for r in timed]
    template_counts = Counter(templates)

    # --- Frequency spikes ---
    bucketed: dict[datetime, list[AnalysisReport]] = defaultdict(list)
    for r in timed:
        ts = r.log_entry.timestamp  # type: ignore[assignment]
        bucketed[_bucket_key(ts, bucket_minutes)].append(r)

    slots = sorted(bucketed.keys())
    # Fill intermediate empty buckets for a stable baseline.
    if slots:
        start = slots[0]
        end = slots[-1]
        current = _bucket_key(start, bucket_minutes)
        all_slots: list[datetime] = []
        while current <= end:
            all_slots.append(current)
            current += timedelta(minutes=bucket_minutes)
    else:
        all_slots = []

    counts = [len(bucketed.get(s, [])) for s in all_slots]
    mean, std = _mean_std(counts)

    spikes: list[PatternInsight] = []
    for s, c in zip(all_slots, counts):
        z = _z_score(c, mean, std)
        if c > 0 and z >= spike_zscore:
            spikes.append(
                PatternInsight(
                    insight_type="frequency_spike",
                    title=f"Anomaly spike at {s.isoformat(timespec='minutes')}",
                    summary=(
                        f"Anomaly volume reached {c} events within the {bucket_minutes}m bucket; "
                        f"this is {z:.1f}σ above the local average ({mean:.1f})."
                    ),
                    confidence=min(1.0, 0.45 + (z * 0.1)),
                    evidence={"bucket_start": s.isoformat(), "event_count": c, "z_score": round(z, 3)},
                )
            )

    # Keep only the most prominent spike (for calm UI).
    spikes = sorted(spikes, key=lambda p: p.confidence, reverse=True)[:1]

    # --- Repeating sequences ---
    sequences: list[PatternInsight] = []
    current_template = templates[0]
    run_len = 1
    run_start_ts = timed[0].log_entry.timestamp

    def _emit_run(tmpl: str, length: int, start_ts: datetime | None, end_ts: datetime | None) -> None:
        if length < 3 or start_ts is None or end_ts is None:
            return
        duration_s = max(0, int((end_ts - start_ts).total_seconds()))
        sequences.append(
            PatternInsight(
                insight_type="repeating_sequence",
                title="Repeating error sequence detected",
                summary=(
                    f"A template recurred {length} times within ~{duration_s}s. "
                    "This suggests a systematic trigger rather than a single transient fault."
                ),
                confidence=min(1.0, 0.35 + (length * 0.08)),
                evidence={
                    "template": tmpl,
                    "count": length,
                    "start": start_ts.isoformat(),
                    "end": end_ts.isoformat(),
                },
            )
        )

    for i in range(1, len(timed)):
        prev_ts = timed[i - 1].log_entry.timestamp  # type: ignore[assignment]
        curr_ts = timed[i].log_entry.timestamp  # type: ignore[assignment]
        gap_s = (curr_ts - prev_ts).total_seconds()
        tmpl = templates[i]
        if tmpl == current_template and gap_s <= sequence_gap_seconds:
            run_len += 1
        else:
            _emit_run(current_template, run_len, run_start_ts, timed[i - 1].log_entry.timestamp)
            current_template = tmpl
            run_len = 1
            run_start_ts = curr_ts

    _emit_run(current_template, run_len, run_start_ts, timed[-1].log_entry.timestamp)

    sequences = sorted(sequences, key=lambda p: p.confidence, reverse=True)[:2]

    # --- Correlated anomalies ---
    # Co-occurrence of templates in the same (larger) window.
    correlation_window = max(bucket_minutes * 2, 30)  # minutes
    buckets: dict[datetime, set[str]] = defaultdict(set)
    for r in timed:
        ts = r.log_entry.timestamp  # type: ignore[assignment]
        buckets[_bucket_key(ts, correlation_window)].add(extract_template(r.log_entry.message))

    pair_counts: Counter[tuple[str, str]] = Counter()
    for tmpl_set in buckets.values():
        t = sorted(tmpl_set)
        for i in range(len(t)):
            for j in range(i + 1, len(t)):
                pair_counts[(t[i], t[j])] += 1

    correlations: list[PatternInsight] = []
    if pair_counts:
        top_pair, top_n = pair_counts.most_common(1)[0]
        a, b = top_pair
        if top_n >= 2:
            correlations.append(
                PatternInsight(
                    insight_type="correlated_anomalies",
                    title="Correlated anomaly templates",
                    summary=(
                        f"Templates co-occurred in the same time windows {top_n} times. "
                        "This may indicate a shared underlying failure mode."
                    ),
                    confidence=min(1.0, 0.3 + (top_n * 0.15)),
                    evidence={"template_pair": [a, b], "cooccurrence_windows": top_n},
                )
            )

    correlations = correlations[:1]

    # --- Unusual time gaps ---
    gaps: list[int] = []
    for i in range(1, len(timed)):
        prev_ts = timed[i - 1].log_entry.timestamp  # type: ignore[assignment]
        curr_ts = timed[i].log_entry.timestamp  # type: ignore[assignment]
        gaps.append(int((curr_ts - prev_ts).total_seconds()))

    time_gap_insights: list[PatternInsight] = []
    if gaps:
        mean_g, std_g = _mean_std(gaps)
        if std_g > 0:
            # Take the most extreme gap.
            max_gap_idx = max(range(len(gaps)), key=lambda k: gaps[k])
            extreme_gap = gaps[max_gap_idx]
            z = _z_score(extreme_gap, mean_g, std_g)
            if z >= 2.0:
                start_ts = timed[max_gap_idx].log_entry.timestamp
                end_ts = timed[max_gap_idx + 1].log_entry.timestamp
                time_gap_insights.append(
                    PatternInsight(
                        insight_type="unusual_time_gap",
                        title="Unusual pause between anomalies",
                        summary=(
                            f"Consecutive anomalies are separated by {extreme_gap}s, "
                            f"which is {z:.1f}σ above the typical gap ({mean_g:.1f}s)."
                        ),
                        confidence=min(1.0, 0.35 + (z * 0.1)),
                        evidence={
                            "gap_seconds": extreme_gap,
                            "z_score": round(z, 3),
                            "start": start_ts.isoformat() if start_ts else None,
                            "end": end_ts.isoformat() if end_ts else None,
                        },
                    )
                )

    time_gap_insights = time_gap_insights[:1]

    # --- Rare templates ---
    rare_insights: list[PatternInsight] = []
    n = len(timed)
    if n > 0 and template_counts:
        # Select templates that appear rarely, but still have at least 2 occurrences
        # to avoid overreacting to a single event.
        rare = [
            (tmpl, c)
            for tmpl, c in template_counts.items()
            if c >= 2 and (c / n) <= 0.02
        ]
        rare.sort(key=lambda x: x[1])  # rarer first
        rare = rare[:3]
        if rare:
            rare_insights.append(
                PatternInsight(
                    insight_type="rare_templates",
                    title="Rare log template activity",
                    summary="A small number of templates appear infrequently, which may indicate a secondary or edge-case failure mode.",
                    confidence=0.4,
                    evidence={"rare_templates": [{"template": t, "count": c} for t, c in rare]},
                )
            )

    rare_insights = rare_insights[:1]

    # Order for UX: spike > repeating > correlation > gap > rare
    ordered = []
    for group in (spikes, sequences, correlations, time_gap_insights, rare_insights):
        ordered.extend(group)

    return ordered

