"""
Production configuration — strict settings for deployment.

All secrets MUST come from environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from config.base import BaseConfig


def _cors_origins() -> tuple[str, ...]:
    """Parse CORS origins from environment variable."""
    raw = os.environ.get("CORS_ORIGINS", "")
    if not raw:
        return ()
    return tuple(o.strip() for o in raw.split(",") if o.strip())


@dataclass(frozen=True)
class ProdConfig(BaseConfig):
    """Production environment configuration."""
    debug: bool = False
    db_path: str = os.environ.get("DB_PATH", "/var/data/log_analyzer/logs.db")
    jwt_secret: str = os.environ.get("JWT_SECRET", "")
    jwt_expiry_hours: int = int(os.environ.get("JWT_EXPIRY_HOURS", "8"))
    cors_origins: tuple[str, ...] = _cors_origins() or ("https://your-domain.com",)
    secure_cookies: bool = True
    rate_limit_default: str = "200 per day"
    rate_limit_analyze: str = "30 per hour"
    monitor_enabled: bool = os.environ.get("MONITOR_ENABLED", "false").lower() == "true"
    monitor_log_path: str = os.environ.get("MONITOR_LOG_PATH", "/var/log/app/app.log")
    max_workers: int = int(os.environ.get("MAX_WORKERS", "4"))


def validate_prod_config(config: ProdConfig) -> list[str]:
    """
    Validate production configuration.

    Returns list of warnings/errors. Empty list = all clear.
    """
    issues: list[str] = []

    if not config.jwt_secret:
        issues.append("CRITICAL: JWT_SECRET is not set")
    elif len(config.jwt_secret) < 32:
        issues.append("WARNING: JWT_SECRET is shorter than 32 characters")

    if config.cors_origins == ("*",):
        issues.append("WARNING: CORS is set to allow all origins")

    if config.debug:
        issues.append("WARNING: Debug mode is enabled in production")

    return issues
