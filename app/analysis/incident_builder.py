"""
Incident builder for AI investigation UI.

Combines root causes, relationship groups, severity distribution and pattern
signals into ranked incidents and a short system story.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.analysis.pattern_analyzer import PatternInsight
from app.analysis.relationship_mapper import RelationshipGroup
from app.analysis.root_cause_engine import RootCause
from models.schemas import AnalysisReport


@dataclass
class Incident:
    title: str
    severity: str
    confidence: float
    time_range: tuple[str, str] | None
    affected_components: list[str] = field(default_factory=list)
    related_logs: list[int] = field(default_factory=list)
    summary: str = ""
    recommended_action: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "severity": self.severity,
            "confidence": self.confidence,
            "time_range": self.time_range,
            "affected_components": self.affected_components,
            "related_logs": self.related_logs,
            "summary": self.summary,
            "recommended_action": self.recommended_action,
        }


def _incident_from_root_cause(c: RootCause) -> Incident:
    dominant_source = str(c.evidence.get("dominant_source")) if c.evidence.get("dominant_source") else None
    components = [dominant_source] if dominant_source and dominant_source != "None" else []
    return Incident(
        title=c.title,
        severity=c.severity,
        confidence=round(float(c.confidence), 3),
        time_range=None,
        affected_components=components,
        related_logs=list(c.related_logs),
        summary=c.summary,
        recommended_action=list(c.recommended_action[:4]),
    )


def build_incidents(
    *,
    reports: list[AnalysisReport],
    root_causes: list[RootCause],
    patterns: list[PatternInsight],
    relationships: list[RelationshipGroup],
) -> list[Incident]:
    incidents: list[Incident] = []

    for rc in root_causes[:8]:
        incidents.append(_incident_from_root_cause(rc))

    # Add relationship-derived incidents when root-cause coverage is sparse.
    if len(incidents) < 3:
        for rg in relationships[: 3 - len(incidents)]:
            incidents.append(
                Incident(
                    title=rg.title,
                    severity="MEDIUM",
                    confidence=round(rg.confidence, 3),
                    time_range=None,
                    affected_components=rg.shared_entities.get("source", []),
                    related_logs=rg.related_logs,
                    summary="Logs share entities and time proximity, indicating a possibly common trigger.",
                    recommended_action=[
                        "Inspect correlated logs as a group before single-line remediation.",
                        "Validate shared entity health and recent changes.",
                    ],
                )
            )

    # Sort by severity then confidence.
    sev_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    incidents.sort(key=lambda x: (sev_order.get(x.severity, 0), x.confidence), reverse=True)

    return incidents[:10]


def build_system_story(*, incidents: list[Incident], patterns: list[PatternInsight], period_hours: int) -> str:
    if not incidents:
        return f"No major incidents were detected in the last {period_hours}h. Continue monitoring for emerging patterns."

    lead = incidents[0]
    pattern_line = patterns[0].summary if patterns else "No strong temporal pattern was identified."
    return (
        f"In the last {period_hours}h, the primary issue is '{lead.title}' "
        f"with {lead.severity} severity and {lead.confidence:.0%} confidence. "
        f"{pattern_line} Focus first on components: {', '.join(lead.affected_components) if lead.affected_components else 'not clearly isolated yet'}."
    )
