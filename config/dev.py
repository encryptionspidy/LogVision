"""
Development configuration — relaxed settings for local development.

Inherits from BaseConfig with development-friendly overrides.
"""

from __future__ import annotations

from dataclasses import dataclass

from config.base import BaseConfig


@dataclass(frozen=True)
class DevConfig(BaseConfig):
    """Development environment configuration."""
    debug: bool = True
    db_path: str = "logs_dev.db"
    jwt_secret: str = "dev-secret-do-not-use-in-production"
    jwt_expiry_hours: int = 168  # 1 week for convenience
    cors_origins: tuple[str, ...] = ("*",)  # Allow all in dev
    secure_cookies: bool = False
    rate_limit_default: str = "1000 per day"
    rate_limit_analyze: str = "100 per hour"
    monitor_enabled: bool = False
    max_workers: int = 2
