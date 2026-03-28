"""
Explanation generator — produces human-readable explanations.

Converts structured log analysis into explanations using templates.
Never fabricates facts. If the cause is unclear, it says so explicitly.
"""

from __future__ import annotations

from app.explanation.templates import get_template
from app.utils.helpers import truncate
from models.schemas import (
    LogEntry,
    AnomalyResult,
    SeverityResult,
    Explanation,
)


def generate_explanation(
    entry: LogEntry,
    anomaly: AnomalyResult,
    severity: SeverityResult,
) -> Explanation:
    """
    Generate a human-readable explanation for a log analysis result.

    Args:
        entry: Parsed log entry.
        anomaly: Anomaly detection result.
        severity: Severity scoring result.

    Returns:
        Explanation with summary, possible causes, and remediation steps.
    """
    template = get_template(anomaly.anomaly_type)

    # Prepare template variables
    message_preview = truncate(entry.message, max_length=100)
    template_vars = {
        "severity": severity.level.value,
        "log_level": entry.log_level.value,
        "message_preview": message_preview,
        "details": anomaly.details or "No additional details",
        "anomaly_type": anomaly.anomaly_type,
        "confidence": f"{anomaly.confidence:.0%}",
        "score": f"{severity.score:.2f}",
    }

    # Render summary
    try:
        summary = template.summary_template.format(**template_vars)
    except KeyError:
        summary = f"{severity.level.value} severity event detected."

    # Render possible causes
    possible_causes: list[str] = []
    for cause_tmpl in template.cause_templates:
        try:
            cause = cause_tmpl.format(**template_vars)
            possible_causes.append(cause)
        except KeyError:
            possible_causes.append(cause_tmpl)

    # Render remediation steps
    remediation: list[str] = []
    for rem_tmpl in template.remediation_templates:
        try:
            step = rem_tmpl.format(**template_vars)
            remediation.append(step)
        except KeyError:
            remediation.append(rem_tmpl)

    confidence_score = float(anomaly.confidence or 0.0)
    if not anomaly.is_anomaly:
        confidence_score = 0.0

    confidence_label = (
        "High" if confidence_score >= 0.8 else "Medium" if confidence_score >= 0.5 else "Low"
    )

    # Confidence note (anti-hallucination: always state uncertainty)
    if confidence_score < 0.5:
        confidence_note = (
            "Low confidence detection. This may be a false positive. "
            "Review in context before taking action."
        )
    elif confidence_score < 0.8:
        confidence_note = (
            "Moderate confidence detection. Verify findings against "
            "system behavior and recent changes."
        )
    else:
        confidence_note = (
            "High confidence detection based on multiple indicators."
        )

    if not anomaly.is_anomaly:
        confidence_note = "No anomaly detected. Entry appears normal."
        confidence_label = "Low"

    # UX-friendly narrative sections (kept generic to avoid hallucination)
    what_happened = summary
    why_it_matters = (
        "Higher-severity anomalies often correlate with real service instability "
        "and should be reviewed alongside recent system changes."
        if severity.level.value in ("HIGH", "CRITICAL")
        else "This anomaly may indicate a developing issue; review context to confirm impact."
    )

    technical_explanation = (
        f"Anomaly type: {anomaly.anomaly_type}. Details: {anomaly.details or 'No additional details'}. "
        f"Confidence: {confidence_label} ({confidence_score:.2f})."
    )
    if confidence_score < 0.5:
        technical_explanation = (
            "Insufficient evidence for a definitive cause. Possible issues include: "
            + ", ".join(possible_causes[:3])
            + ". " + technical_explanation
        )

    return Explanation(
        summary=summary,
        possible_causes=possible_causes,
        remediation=remediation,
        confidence_note=confidence_note,
        confidence_score=confidence_score,
        confidence_label=confidence_label,
        what_happened=what_happened,
        why_it_matters=why_it_matters,
        technical_explanation=technical_explanation,
        detail_levels={
            "simple": what_happened,
            "technical": technical_explanation,
            "raw": {
                "anomaly_type": anomaly.anomaly_type,
                "confidence": confidence_score,
                "severity": severity.level.value,
                "details": anomaly.details,
            },
        },
    )


def generate_explanations(
    entries: list[LogEntry],
    anomalies: dict[int, AnomalyResult],
    severities: dict[int, SeverityResult],
) -> dict[int, Explanation]:
    """
    Generate explanations for all entries in a batch.

    Args:
        entries: All parsed log entries.
        anomalies: Anomaly results keyed by line_number.
        severities: Severity results keyed by line_number.

    Returns:
        Dict mapping line_number → Explanation.
    """
    results: dict[int, Explanation] = {}

    for entry in entries:
        anomaly = anomalies.get(entry.line_number, AnomalyResult())
        severity = severities.get(entry.line_number, SeverityResult())
        results[entry.line_number] = generate_explanation(
            entry, anomaly, severity
        )

    return results
