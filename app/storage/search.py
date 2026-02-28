"""
Search implementation for persistent logs.
"""

from __future__ import annotations

from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy import select, desc, text
from app.storage.database import logs_table, get_db

def search_logs(
    query: Optional[str] = None,
    severity: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Search logs with filters and pagination.
    
    Args:
        query: Text search in message.
        severity: Filter by severity level.
        start_date: Filter by timestamp >= start.
        end_date: Filter by timestamp <= end.
        limit: Max results.
        offset: Pagination offset.
        
    Returns:
        Dict with 'total' count and 'items' list.
    """
    db = get_db()
    stmt = select(logs_table)
    
    # Apply filters
    if severity:
        stmt = stmt.where(logs_table.c.severity == severity)
        
    if start_date:
        stmt = stmt.where(logs_table.c.timestamp >= start_date)
        
    if end_date:
        stmt = stmt.where(logs_table.c.timestamp <= end_date)
        
    if query:
        # Basic case-insensitive partial match
        # For production SQLite, FTS5 is better, but LIKE is safe fall-back
        stmt = stmt.where(logs_table.c.message.ilike(f"%{query}%"))

    # Count total (separate query for pagination)
    count_stmt = select(text("count(*)")).select_from(stmt.subquery())
    
    # Apply sorting and pagination
    stmt = stmt.order_by(desc(logs_table.c.timestamp), desc(logs_table.c.id))
    stmt = stmt.limit(limit).offset(offset)
    
    with db.get_connection() as conn:
        total = conn.execute(count_stmt).scalar()
        result = conn.execute(stmt).fetchall()
        
        items = []
        for row in result:
            items.append({
                "id": row.id,
                "timestamp": row.timestamp.isoformat() if row.timestamp else None,
                "log_level": row.log_level,
                "message": row.message,
                "source": row.source,
                "line_number": row.line_number,
                "anomaly_score": row.anomaly_score,
                "severity": row.severity,
                "explanation": json.loads(row.explanation) if row.explanation else None
            })
            
    return {
        "total": total,
        "items": items,
        "page": (offset // limit) + 1,
        "limit": limit
    }

import json
