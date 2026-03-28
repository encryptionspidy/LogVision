"""
Relationship mapper for anomaly investigation.

Builds lightweight graph-like groups by shared entities:
- IP address
- error code
- source/service
- temporal proximity
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from models.schemas import AnalysisReport


@dataclass
class RelationshipGroup:
    group_id: int
    title: str
    related_logs: list[int]
    shared_entities: dict[str, list[str]] = field(default_factory=dict)
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "title": self.title,
            "related_logs": self.related_logs,
            "shared_entities": self.shared_entities,
            "confidence": self.confidence,
        }


def _time_key(ts: datetime | None, minutes: int = 10) -> str:
    if ts is None:
        return "unknown"
    mm = (ts.minute // minutes) * minutes
    return ts.replace(minute=mm, second=0, microsecond=0).isoformat()


def map_relationships(reports: list[AnalysisReport]) -> list[RelationshipGroup]:
    if not reports:
        return []

    buckets: dict[str, list[AnalysisReport]] = {}
    for r in reports:
        ip = r.log_entry.ip_address or ""
        code = r.log_entry.error_code or ""
        src = r.log_entry.source or ""
        tk = _time_key(r.log_entry.timestamp)
        key = f"{ip}|{code}|{src}|{tk}"
        buckets.setdefault(key, []).append(r)

    groups: list[RelationshipGroup] = []
    gid = 1
    for items in buckets.values():
        if len(items) < 2:
            continue
        ips = sorted({x.log_entry.ip_address for x in items if x.log_entry.ip_address})
        codes = sorted({x.log_entry.error_code for x in items if x.log_entry.error_code})
        sources = sorted({x.log_entry.source for x in items if x.log_entry.source})
        related = sorted({x.log_entry.line_number for x in items})

        confidence = min(1.0, 0.35 + (0.1 * len(related)))
        title_parts = []
        if codes:
            title_parts.append(f"code {codes[0]}")
        if ips:
            title_parts.append(f"IP {ips[0]}")
        if sources:
            title_parts.append(f"source {sources[0]}")
        title = "Relationship group: " + ", ".join(title_parts) if title_parts else "Relationship group"

        groups.append(
            RelationshipGroup(
                group_id=gid,
                title=title,
                related_logs=related,
                shared_entities={"ip": ips, "error_code": codes, "source": sources},
                confidence=round(confidence, 3),
            )
        )
        gid += 1

    groups.sort(key=lambda g: (len(g.related_logs), g.confidence), reverse=True)
    return groups[:30]
