"""
Summary builder — converts computed insights into a readable executive report.

This is narrative-only (no visualization). Visualization payloads are produced
by app.analytics.insight_engine.InsightEngine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.analysis.pattern_analyzer import PatternInsight
from app.analysis.root_cause_engine import RootCause


def _risk_from_severity_distribution(sev_counts: dict[str, int]) -> tuple[str, float]:
    weights = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    total = sum(sev_counts.values()) or 0
    if total <= 0:
        return "LOW", 0.0

    weighted = sum(sev_counts.get(k, 0) * weights.get(k, 1) for k in weights.keys())
    score = weighted / (total * 4)  # normalize to 0..1

    if sev_counts.get("CRITICAL", 0) > 0 and score >= 0.55:
        return "CRITICAL", score
    if score >= 0.45:
        return "HIGH", score
    if score >= 0.25:
        return "MEDIUM", score
    return "LOW", score


def _avg_confidence(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 3)


def build_summary_report(
    *,
    period_hours: int,
    total_entries: int,
    anomaly_count: int,
    severity_distribution: dict[str, int],
    root_causes: list[RootCause],
    patterns: list[PatternInsight],
    cluster_distribution: list[dict[str, Any]] | None = None,
    charts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Return a JSON-serializable summary report payload.
    """
    anomaly_rate = (anomaly_count / total_entries * 100.0) if total_entries > 0 else 0.0

    risk_level, risk_score = _risk_from_severity_distribution(severity_distribution)

    top_causes = root_causes[:3]
    top_patterns = patterns[:3]

    # Confidence: root-cause confidence tends to be more actionable than
    # pattern heuristics, but both are included.
    root_conf = _avg_confidence([c.confidence for c in root_causes[:5]])
    pattern_conf = _avg_confidence([p.confidence for p in patterns[:5]])
    overall_conf = round(root_conf * 0.65 + pattern_conf * 0.35, 3)

    evidence_note = (
        "insufficient evidence, possible causes include..." if anomaly_count < 5 or overall_conf < 0.4
        else "multiple indicators align with the grouped anomalies."
    )

    # Executive narrative
    key_lines: list[str] = []
    if top_patterns:
        for p in top_patterns[:2]:
            key_lines.append(f"- {p.title}: {p.summary}")
    if top_causes:
        key_lines.append(f"- Top incident group(s): {top_causes[0].title}")
        if len(top_causes) > 1:
            key_lines.append(f"- Next group: {top_causes[1].title}")

    recommended_actions: list[str] = []
    for c in top_causes:
        recommended_actions.extend(c.recommended_action)
    # Deduplicate while preserving order.
    deduped: list[str] = []
    seen: set[str] = set()
    for a in recommended_actions:
        if a not in seen:
            seen.add(a)
            deduped.append(a)
    recommended_actions = deduped[:6]

    cluster_hint = ""
    if cluster_distribution:
        top_cluster = max(cluster_distribution, key=lambda c: c.get("cluster_size", 0), default=None)
        if top_cluster:
            cluster_hint = (
                f" The dominant similarity cluster is `{top_cluster.get('representative', 'n/a')}` "
                f"with {top_cluster.get('cluster_size', 0)} events."
            )

    system_summary = (
        f"Across the last {period_hours}h, {anomaly_count} anomaly events were detected "
        f"out of {total_entries} total log entries (anomaly rate {anomaly_rate:.2f}%). "
        f"Overall risk is assessed as {risk_level} (confidence {overall_conf:.0%}). {evidence_note}{cluster_hint}"
    )

    technical_summary = (
        "Key grouped behaviors and contributing indicators:\\n"
        + "\\n".join(key_lines if key_lines else ["- No significant behavioral patterns detected in the window."])
        + "\\n"
        + "Root-cause groups provide the most actionable remediation hints; pattern insights help explain "
          "why the anomalies may be correlated over time."
    )

    return {
        "executive_summary": system_summary,
        "technical_summary": technical_summary,
        "risk_assessment": {
            "risk_level": risk_level,
            "risk_score": risk_score,
            "overall_confidence": overall_conf,
            "confidence_note": (
                "Confidence is heuristic and based on the density of grouped events; "
                "treat it as a guide rather than certainty."
            ),
        },
        "key_anomalies": {
            "patterns": [p.to_dict() for p in top_patterns],
            "root_causes": [c.to_dict() for c in top_causes],
        },
        "recommended_actions": recommended_actions,
        # Optional: include chart payload for the dashboard overview page.
        "charts": charts or {},
    }

