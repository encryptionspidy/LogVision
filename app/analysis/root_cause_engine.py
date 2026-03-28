"""
Root-cause engine — groups related anomalies into actionable incidents.

This engine reuses the existing template/time-based root-cause aggregator
and enriches its output with shared entities (IP, error code, source module).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.root_cause.aggregator import aggregate_root_causes
from app.root_cause.correlation_engine import detect_cascades
from app.clustering.template_miner import extract_template
from models.schemas import AnalysisReport, RootCauseEvent, SeverityLevel


@dataclass
class RootCause:
    title: str
    summary: str
    related_logs: list[int]
    confidence: float
    severity: str
    recommended_action: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "related_logs": self.related_logs,
            "confidence": self.confidence,
            "severity": self.severity,
            "recommended_action": self.recommended_action,
            "evidence": self.evidence,
        }


_IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
_ERROR_CODE_RE = re.compile(r"\b(?:ERR|ERROR|CODE|RC)[-_:]?(?:\s*)[A-Za-z0-9]{2,}\b")
_NUM_CODE_RE = re.compile(r"\b(?:[1-9]\d{2,})\b")  # 3+ digits


def _extract_ips(text: str) -> list[str]:
    return sorted(set(_IP_RE.findall(text or "")))


def _extract_error_codes(text: str) -> list[str]:
    """
    Best-effort extraction of error codes without claiming certainty.
    Returns deduplicated tokens found in the log text.
    """
    found = set()
    for m in _ERROR_CODE_RE.findall(text or ""):
        found.add(str(m))
    # Some systems only emit numeric codes (e.g., HTTP-ish codes).
    # Keep this conservative: only add if we also saw an error-ish prefix.
    if _ERROR_CODE_RE.search(text or ""):
        found.update(_NUM_CODE_RE.findall(text or ""))
    return sorted(found)


def _dominant_source(reports: list[AnalysisReport]) -> str | None:
    sources = [r.log_entry.source for r in reports if r.log_entry.source]
    if not sources:
        return None
    counts: dict[str, int] = defaultdict(int)
    for s in sources:
        counts[s] += 1
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _severity_label(level: SeverityLevel | str) -> str:
    if isinstance(level, SeverityLevel):
        return level.value
    return str(level)


def _recommended_actions_for_context(
    *,
    template: str,
    ips: list[str],
    error_codes: list[str],
    source: str | None,
) -> list[str]:
    """
    Produce safe, non-hallucinatory remediation steps based on observed text.
    """
    template_l = (template or "").lower()
    actions: list[str] = []

    if any(k in template_l for k in ("timeout", "timed out", "deadlock", "lock", "connection refused", "connection reset")):
        actions.extend(
            [
                "Inspect downstream dependency health (database/cache/service) around the incident window.",
                "Verify network connectivity and connection-pool limits.",
            ]
        )
    if any(k in template_l for k in ("auth", "authentication", "login", "invalid token", "permission denied")):
        actions.extend(
            [
                "Review authentication configuration and session/token validation.",
                "If applicable, apply rate limiting and investigate suspicious IP activity.",
            ]
        )
    if any(k in template_l for k in ("out of memory", "oom", "disk space", "no space")):
        actions.extend(
            [
                "Check resource saturation (memory/disk) and recent workload changes.",
                "Consider scaling limits and tuning retention/log rotation.",
            ]
        )
    if any(k in template_l for k in ("restarting", "restart", "shutdown", "sigterm", "segfault")):
        actions.extend(
            [
                "Correlate with deployment/restart events and investigate crash signals in system logs.",
                "Validate configuration and perform regression checks on the impacted component.",
            ]
        )

    # Context hints without claiming certainty.
    if source:
        actions.append(f"Prioritize investigation of service/module: {source}.")
    if ips:
        actions.append(f"Observed {len(ips)} distinct IP(s); review access logs and rate-limit if necessary.")
    if error_codes:
        actions.append(f"Error tokens observed: {', '.join(error_codes[:3])}{'...' if len(error_codes) > 3 else ''}.")

    if not actions:
        actions = [
            "Review the affected component and recent changes around the incident window.",
            "Confirm whether the pattern matches known failure modes by comparing with healthy periods.",
        ]

    # Deduplicate while preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for a in actions:
        if a not in seen:
            seen.add(a)
            deduped.append(a)
    return deduped[:5]


def build_root_causes(
    reports: list[AnalysisReport],
    *,
    time_window_seconds: int = 300,
    min_group_size: int = 2,
) -> list[RootCause]:
    """
    Build enriched root-cause objects.
    """
    if not reports:
        return []

    # Use existing high-quality grouping logic.
    base_events: list[RootCauseEvent] = aggregate_root_causes(
        reports,
        time_window_seconds=time_window_seconds,
        min_group_size=min_group_size,
    )
    base_events = detect_cascades(base_events)

    report_by_line: dict[int, AnalysisReport] = {r.log_entry.line_number: r for r in reports}

    # Compute per-event entities.
    enriched: list[RootCause] = []
    for ev in base_events:
        related_reports = [
            report_by_line[ln]
            for ln in ev.related_log_ids
            if ln in report_by_line
        ]

        combined_text = "\n".join(r.log_entry.message for r in related_reports if r.log_entry.message)
        ips = _extract_ips(combined_text)
        error_codes = _extract_error_codes(combined_text)
        source = _dominant_source(related_reports)
        template = ev.template_pattern or extract_template(related_reports[0].log_entry.message) if related_reports else ""

        entity_bits: list[str] = []
        if ips:
            entity_bits.append(f"{len(ips)} distinct IP(s)")
        if error_codes:
            entity_bits.append(f"{len(error_codes)} error token(s)")
        if source:
            entity_bits.append(f"source={source}")

        entity_suffix = f" Observed entities: {', '.join(entity_bits)}." if entity_bits else ""

        severity = _severity_label(ev.severity)
        recommended_action = _recommended_actions_for_context(
            template=template,
            ips=ips,
            error_codes=error_codes,
            source=source,
        )

        enriched.append(
            RootCause(
                title=ev.title,
                summary=ev.description + entity_suffix,
                related_logs=list(ev.related_log_ids),
                confidence=float(ev.confidence),
                severity=severity,
                recommended_action=recommended_action,
                evidence={
                    "template_pattern": ev.template_pattern,
                    "event_count": ev.event_count,
                    "ips": ips,
                    "error_codes": error_codes,
                    "dominant_source": source,
                },
            )
        )

    # Sort by confidence for a stable premium UX.
    enriched.sort(key=lambda c: c.confidence, reverse=True)
    return enriched

