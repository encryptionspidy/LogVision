"""
Analytics metrics engine.

Calculates aggregated stats from the persistent log database using efficient SQL queries.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from sqlalchemy import select, func, desc, text
from app.storage.database import get_db, logs_table

logger = logging.getLogger(__name__)

class AnalyticsEngine:
    """
    Provides aggregated metrics for dashboard visualization.
    """
    def __init__(self):
        self.db = get_db()

    def get_summary_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get high-level metrics for the dashboard.
        
        Args:
            hours: Lookback window in hours.
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        with self.db.get_connection() as conn:
            # 1. Total Enties
            total_stmt = select(func.count()).select_from(logs_table).where(logs_table.c.timestamp >= cutoff)
            total = conn.execute(total_stmt).scalar() or 0
            
            # 2. Anomaly Count
            anomaly_stmt = select(func.count()).select_from(logs_table).where(
                logs_table.c.timestamp >= cutoff,
                logs_table.c.anomaly_score > 0.5  # Assuming >0.5 is anomalous
            )
            anomalies = conn.execute(anomaly_stmt).scalar() or 0
            
            # 3. Severity Distribution
            sev_stmt = select(
                logs_table.c.severity, 
                func.count(logs_table.c.severity)
            ).where(
                logs_table.c.timestamp >= cutoff
            ).group_by(logs_table.c.severity)
            
            severity_counts = {row[0]: row[1] for row in conn.execute(sev_stmt).fetchall()}
            
            # 4. Top Sources (e.g. which service is noisy)
            source_count = func.count(logs_table.c.source).label("count")
            source_stmt = select(
                logs_table.c.source,
                source_count
            ).where(
                logs_table.c.timestamp >= cutoff
            ).group_by(logs_table.c.source).order_by(desc(source_count)).limit(5)
            
            top_sources = [
                {"source": row[0], "count": row[1]} 
                for row in conn.execute(source_stmt).fetchall()
                if row[0]
            ]
            
            # 5. Error trend (hourly buckets) - simplified
            # SQLite specific strftime
            trend_stmt = text("""
                SELECT strftime('%Y-%m-%d %H:00:00', timestamp) as hour, count(*) 
                FROM logs 
                WHERE timestamp >= :cutoff AND severity IN ('ERROR', 'CRITICAL')
                GROUP BY hour 
                ORDER BY hour
            """)
            trend_result = conn.execute(trend_stmt, {"cutoff": cutoff}).fetchall()
            error_trend = [{"time": row[0], "count": row[1]} for row in trend_result]

        return {
            "period_hours": hours,
            "total_entries": total,
            "anomaly_count": anomalies,
            "anomaly_rate": round(anomalies / total * 100, 2) if total > 0 else 0,
            "severity_distribution": severity_counts,
            "top_sources": top_sources,
            "error_trend": error_trend
        }
