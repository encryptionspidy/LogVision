"""
Deep log explainer — upgrades per-log explanations with batch context.

This module does not use an LLM; it combines existing template explanations
with deterministic cluster/pattern/root-cause signals to provide a clearer
system-behavior narrative.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.analysis.pattern_analyzer import PatternInsight, detect_patterns
from app.analysis.root_cause_engine import RootCause, build_root_causes
from app.clustering.cluster_engine import ClusterSummary, cluster_logs
from app.clustering.template_miner import extract_template
from app.explanation.generator import generate_explanation
from models.schemas import AnalysisReport, AnomalyResult, Explanation, LogEntry, SeverityResult


@dataclass
class DeepContext:
    root_causes: list[RootCause]
    patterns: list[PatternInsight]
    cluster_summary: ClusterSummary | None
    cluster_assignments: dict[int, int]

    def template_to_root_causes(self) -> dict[str, list[RootCause]]:
        mapping: dict[str, list[RootCause]] = {}
        for rc in self.root_causes:
            tmpl = rc.evidence.get("template_pattern") if rc.evidence else None
            if tmpl:
                mapping.setdefault(str(tmpl), []).append(rc)
        return mapping


def _confidence_label(confidence_score: float) -> str:
    if confidence_score >= 0.8:
        return "High"
    if confidence_score >= 0.5:
        return "Medium"
    return "Low"


def build_deep_context(
    base_reports: list[AnalysisReport],
    *,
    root_cause_time_window_seconds: int = 300,
    max_anomalies_for_context: int = 5000,
) -> DeepContext:
    anomalous = [r for r in base_reports if r.anomaly.is_anomaly]
    if max_anomalies_for_context and len(anomalous) > max_anomalies_for_context:
        anomalous = sorted(
            anomalous,
            key=lambda r: r.anomaly.confidence,
            reverse=True,
        )[:max_anomalies_for_context]
    patterns = detect_patterns(anomalous) if anomalous else []
    root_causes = build_root_causes(
        anomalous,
        time_window_seconds=root_cause_time_window_seconds,
        min_group_size=2,
    )

    # Cluster on anomalous messages only, capped for performance.
    cluster_summary = None
    cluster_assignments: dict[int, int] = {}
    if anomalous and len(anomalous) >= 3:
        cluster_entries = [r.log_entry for r in anomalous]
        # cluster_logs is already capped by downstream callers in insight engine,
        # so we keep a small cap here as well.
        if len(cluster_entries) > 2000:
            cluster_entries = cluster_entries[:2000]
        cluster_summary = cluster_logs(cluster_entries, max_clusters=12, min_cluster_size=2)
        if cluster_summary:
            cluster_assignments = dict(cluster_summary.assignments)

    return DeepContext(
        root_causes=root_causes,
        patterns=patterns,
        cluster_summary=cluster_summary,
        cluster_assignments=cluster_assignments,
    )


def upgrade_explanation(
    report: AnalysisReport,
    context: DeepContext,
    *,
    template_root_causes: dict[str, list[RootCause]] | None = None,
    pattern_bits: list[str] | None = None,
) -> Explanation:
    """
    Produce a richer Explanation while preserving anti-hallucination behavior.
    """
    base = report.explanation
    anomaly = report.anomaly
    severity = report.severity
    entry: LogEntry = report.log_entry

    template = extract_template(entry.message)
    if template_root_causes is not None:
        relevant_root_causes = template_root_causes.get(str(template), [])
    else:
        relevant_root_causes = [
            rc for rc in context.root_causes
            if str(rc.evidence.get("template_pattern", "")) == template
        ]

    relevant_root_causes = sorted(relevant_root_causes, key=lambda rc: rc.confidence, reverse=True)[:1]
    rc = relevant_root_causes[0] if relevant_root_causes else None

    cluster_id = context.cluster_assignments.get(entry.line_number)
    cluster_rep = ""
    if context.cluster_summary and cluster_id is not None and cluster_id in context.cluster_summary.clusters:
        cluster_rep = context.cluster_summary.clusters[cluster_id].representative

    # Start from the base generator output (already hedged and structured).
    confidence_score = float(getattr(base, "confidence_score", 0.0) or 0.0)
    confidence_label = base.confidence_label or _confidence_label(confidence_score)

    # If we have a strong root-cause match, gently increase confidence.
    if rc and rc.confidence >= 0.6:
        confidence_score = min(1.0, confidence_score + 0.08)
        confidence_label = _confidence_label(confidence_score)

    # Suggested fixes: base remediation + root cause recommended actions (if relevant).
    possible_causes = list(base.possible_causes)
    remediation = list(base.remediation)

    if rc:
        remediation.extend(rc.recommended_action[:2])
        # Mention entities only if they exist in evidence.
        ips = rc.evidence.get("ips", []) if rc.evidence else []
        if ips:
            possible_causes.append(f"Potentially influenced by repeated activity from {len(ips)} distinct IP(s) (evidence-based).")
        source = rc.evidence.get("dominant_source") if rc.evidence else None
        if source:
            possible_causes.append(f"May be tied to the dominant source/module observed in the incident: {source}.")

    # Pattern references: use only titles/summaries already computed.
    pattern_bits = pattern_bits if pattern_bits is not None else [p.summary for p in context.patterns[:2]]

    if not rc and confidence_score < 0.5:
        technical_explanation = (
            "Insufficient evidence to connect this log entry to a specific grouped incident. "
            "Possible causes include: "
            + (", ".join(possible_causes[:3]) if possible_causes else "unverified contributing factors")
            + ". "
            + (base.technical_explanation or "")
        )
        why_it_matters = (
            "While this entry looks anomalous, confidence is low; treat remediation as investigation guidance "
            "until correlated indicators confirm impact."
        )
    else:
        technical_explanation = (
            (base.technical_explanation or "")
            + (" " if base.technical_explanation else "")
            + (
                f"Matched template cluster similarity. Representative: {cluster_rep}."
                if cluster_rep
                else "Template clustering did not provide a stable representative in this batch."
            )
            + (" " if pattern_bits else "")
            + (f"Recent behavioral signals: {pattern_bits[0]}" if pattern_bits else "")
        )

        why_it_matters = (
            "This anomaly is part of a broader behavioral pattern; understanding the correlated group helps "
            "prioritize fixes and reduce time-to-mitigation."
        )

    what_happened = (
        base.what_happened
        or base.summary
        or f"{severity.level.value} severity anomaly detected"
    )

    # Keep confidence note anti-hallucination as-is from the base generator.
    # Update label/score fields for accurate UI rendering.
    confidence_note = base.confidence_note

    return Explanation(
        summary=base.summary,
        possible_causes=possible_causes[:8],
        remediation=remediation[:8],
        confidence_note=confidence_note,
        confidence_score=round(confidence_score, 3),
        confidence_label=confidence_label,
        what_happened=what_happened,
        why_it_matters=why_it_matters,
        technical_explanation=technical_explanation.strip(),
    )


def upgrade_explanations(
    base_reports: list[AnalysisReport],
    *,
    context: DeepContext | None = None,
) -> dict[int, Explanation]:
    """
    Upgrade explanations for all reports in the batch.
    """
    if context is None:
        context = build_deep_context(base_reports)

    template_map = context.template_to_root_causes()
    cached_pattern_bits = [p.summary for p in context.patterns[:2]]
    upgraded: dict[int, Explanation] = {}
    for r in base_reports:
        upgraded[r.log_entry.line_number] = upgrade_explanation(
            r,
            context,
            template_root_causes=template_map,
            pattern_bits=cached_pattern_bits,
        )
    return upgraded

