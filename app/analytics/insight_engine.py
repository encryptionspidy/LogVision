"""
Insight engine — computes structured visualization payloads.

The goal is to generate deterministic chart-ready JSON without relying on
external LLMs. Computations are derived from anomaly-flagged reports and
lightweight entity extraction.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from app.analytics.metrics import AnalyticsEngine
from app.clustering.cluster_engine import cluster_logs
from app.clustering.template_miner import extract_template
from app.storage.database import get_db
from app.timeline.timeline_builder import build_timeline
from models.schemas import AnalysisReport


_IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


def _bucket_key(dt: datetime, bucket_minutes: int) -> datetime:
    minute = (dt.minute // bucket_minutes) * bucket_minutes
    return dt.replace(minute=minute, second=0, microsecond=0)


def _extract_ips(text: str) -> list[str]:
    return sorted(set(_IP_RE.findall(text or "")))


def _error_category(message: str) -> str:
    m = (message or "").lower()
    if any(k in m for k in ("auth", "authentication", "login", "invalid token", "permission denied", "unauthorized", "forbidden")):
        return "authentication"
    if any(k in m for k in ("timeout", "timed out", "deadlock", "database", "connection refused", "connection reset", "broken pipe", "socket")):
        return "database"
    if any(k in m for k in ("out of memory", "oom", "disk space", "no space", "segfault", "killed")):
        return "resource"
    if any(k in m for k in ("restarting", "restart", "shutdown", "sigterm", "segfault")):
        return "service_restart"
    if any(k in m for k in ("rate limit", "throttl", "too many requests", "ddos", "ddos attack")):
        return "security"
    return "other"


class InsightEngine:
    def __init__(self):
        self.db = get_db()

    def get_overview_charts(
        self,
        *,
        hours: int = 24,
        bucket_minutes: int = 15,
        heatmap_bucket_minutes: int = 60,
        max_cluster_samples: int = 2000,
        max_templates: int = 10,
    ) -> dict[str, Any]:
        reports: list[AnalysisReport] = self.db.get_recent_reports(hours=hours)
        if not reports:
            return {
                "period_hours": hours,
                "charts": {},
                "metrics": {},
            }

        anomaly_reports = [r for r in reports if r.anomaly.is_anomaly]

        # --- Metrics ---
        total_entries = len(reports)
        anomaly_count = len(anomaly_reports)
        anomaly_ratio = (anomaly_count / total_entries) if total_entries else 0.0

        severity_counts: dict[str, int] = defaultdict(int)
        for r in reports:
            severity_counts[r.severity.level.value] += 1

        # --- Severity donut (percentages) ---
        sev_total = sum(severity_counts.values()) or 1
        severity_distribution = {
            k: (v / sev_total) * 100.0 for k, v in severity_counts.items() if v > 0
        }

        # --- Anomaly timeline + spike markers ---
        timeline = build_timeline(anomaly_reports, hours=min(hours, 168), bucket_minutes=bucket_minutes)
        anomaly_timeline = timeline

        # --- Log volume trend (all events) ---
        vol_bucketed: dict[datetime, int] = defaultdict(int)
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        for r in reports:
            ts = r.log_entry.timestamp
            if ts is None or ts < cutoff:
                continue
            vol_bucketed[_bucket_key(ts, bucket_minutes)] += 1

        slots = sorted(vol_bucketed.keys())
        if slots:
            start = _bucket_key(slots[0], bucket_minutes)
            end = _bucket_key(slots[-1], bucket_minutes)
        else:
            start, end = cutoff, datetime.utcnow()

        current = start
        log_volume_trend: list[dict[str, Any]] = []
        while current <= end:
            log_volume_trend.append(
                {"time": current.isoformat(), "count": vol_bucketed.get(current, 0)}
            )
            current += timedelta(minutes=bucket_minutes)

        # --- Top IP sources ---
        ip_counts: Counter[str] = Counter()
        for r in anomaly_reports:
            for ip in _extract_ips(r.log_entry.message):
                ip_counts[ip] += 1
        top_ip_sources = [{"ip": ip, "count": c} for ip, c in ip_counts.most_common(5)]

        # --- Error category pie chart ---
        cat_counts: Counter[str] = Counter()
        for r in anomaly_reports:
            cat_counts[_error_category(r.log_entry.message)] += 1
        error_category_pie = [{"name": k, "value": v} for k, v in cat_counts.most_common(8)]

        # --- Error frequency heatmap (category vs time bucket) ---
        heatmap_categories = [c["name"] for c in error_category_pie]
        if not heatmap_categories:
            heatmap_categories = ["other"]

        heat_slots_bucketed: dict[datetime, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for r in anomaly_reports:
            ts = r.log_entry.timestamp
            if ts is None or ts < cutoff:
                continue
            b = _bucket_key(ts, heatmap_bucket_minutes)
            cat = _error_category(r.log_entry.message)
            if cat not in heatmap_categories:
                cat = "other"
            heat_slots_bucketed[b][cat] += 1

        heat_slots = sorted(heat_slots_bucketed.keys())
        if heat_slots:
            heat_start = _bucket_key(heat_slots[0], heatmap_bucket_minutes)
            heat_end = _bucket_key(heat_slots[-1], heatmap_bucket_minutes)
        else:
            heat_start, heat_end = cutoff, datetime.utcnow()

        heat_current = heat_start
        heatmap_rows: list[dict[str, Any]] = []
        while heat_current <= heat_end:
            row = {"time": heat_current.isoformat(), "values": {}}
            cat_map = heat_slots_bucketed.get(heat_current, {})
            for cat in heatmap_categories:
                row["values"][cat] = int(cat_map.get(cat, 0))
            heatmap_rows.append(row)
            heat_current += timedelta(minutes=heatmap_bucket_minutes)

        # --- Cluster distribution (similarity clusters) ---
        cluster_entries = [r.log_entry for r in anomaly_reports]
        # Cluster can be expensive; sample to stay under the performance budget.
        if len(cluster_entries) > max_cluster_samples:
            cluster_entries = cluster_entries[:max_cluster_samples]

        cluster_summary = cluster_logs(
            cluster_entries,
            max_clusters=12,
            min_cluster_size=2,
        )

        cluster_distribution: list[dict[str, Any]] = []
        if cluster_summary:
            for cluster_id, c in cluster_summary.clusters.items():
                cluster_distribution.append(
                    {
                        "cluster_id": cluster_id,
                        "cluster_size": c.cluster_size,
                        "representative": c.representative,
                        "is_outlier": c.is_outlier,
                    }
                )
            cluster_distribution.sort(key=lambda x: x["cluster_size"], reverse=True)

        # --- Error type ranking (template strings) ---
        template_counts: Counter[str] = Counter()
        for r in anomaly_reports:
            template_counts[extract_template(r.log_entry.message)] += 1
        error_type_ranking = [
            {"error_type": tmpl, "count": c, "percent": (c / anomaly_count * 100.0) if anomaly_count else 0.0}
            for tmpl, c in template_counts.most_common(max_templates)
        ]

        # --- Assemble charts payload ---
        charts = {
            "anomaly_timeline": [t.to_dict() if hasattr(t, "to_dict") else t for t in anomaly_timeline],
            "severity_distribution_percent": severity_distribution,
            "error_frequency_heatmap": {
                "categories": heatmap_categories,
                "rows": heatmap_rows,
                "bucket_minutes": heatmap_bucket_minutes,
            },
            "top_ip_sources": top_ip_sources,
            "cluster_distribution": cluster_distribution,
            "error_type_ranking": error_type_ranking,
            "log_volume_trend": log_volume_trend,
            "anomaly_spike_markers": [
                {"bucket_start": t.bucket_start, "is_spike": t.is_spike} for t in anomaly_timeline
            ],
            "error_category_pie": error_category_pie,
        }

        metrics = {
            "period_hours": hours,
            "total_entries": total_entries,
            "anomaly_count": anomaly_count,
            "anomaly_ratio": anomaly_ratio,
            "severity_counts": dict(severity_counts),
        }

        return {"charts": charts, "metrics": metrics}

