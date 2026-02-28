"""
Base configuration — shared across all environments.

All fields are defined here with sensible defaults.
Environment-specific overrides live in dev.py and prod.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class BaseConfig:
    """Base configuration shared across environments."""

    # Application
    app_name: str = "log-analyzer"
    debug: bool = False

    # Database
    db_path: str = "logs.db"

    # API Server
    host: str = "0.0.0.0"
    port: int = 5000

    # Security
    jwt_secret: str = ""  # MUST be set in production
    jwt_expiry_hours: int = 24
    cors_origins: tuple[str, ...] = ("*",)
    secure_cookies: bool = False

    # Rate limiting
    rate_limit_default: str = "200 per day"
    rate_limit_analyze: str = "30 per hour"

    # Ingestion
    max_file_size_bytes: int = 50 * 1024 * 1024  # 50 MB
    allowed_extensions: tuple[str, ...] = (".log", ".txt", ".json")

    # Worker
    max_workers: int = 4

    # Monitoring
    monitor_enabled: bool = False
    monitor_log_path: str = ""
