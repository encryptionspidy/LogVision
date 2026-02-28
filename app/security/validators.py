"""
Pydantic input validators for API endpoint security.

Validates incoming request bodies for:
- /login  — username, password
- /analyze — file presence (basic header validation)
- Other endpoints with query parameters

Prevents malformed or oversized inputs from reaching the pipeline.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    """Validates /login request body."""
    username: str = Field(..., min_length=1, max_length=128)
    password: Optional[str] = Field(default=None, max_length=256)

    @field_validator("username")
    @classmethod
    def username_no_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Username cannot be only whitespace")
        return v.strip()


class AnalyzeQueryParams(BaseModel):
    """Validates query params for /analyze and /analyze/async."""
    async_mode: bool = False


class SearchQueryParams(BaseModel):
    """Validates /search query parameters."""
    q: str = Field(default="", max_length=500)
    severity: Optional[str] = Field(default=None, pattern=r"^(LOW|MEDIUM|HIGH|CRITICAL)$")
    start_time: Optional[str] = Field(default=None, max_length=30)
    end_time: Optional[str] = Field(default=None, max_length=30)
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class TimelineQueryParams(BaseModel):
    """Validates /timeline query parameters."""
    hours: int = Field(default=6, ge=1, le=168)
    bucket: int = Field(default=15, ge=1, le=60)


class RootCauseQueryParams(BaseModel):
    """Validates /root-cause query parameters."""
    hours: int = Field(default=24, ge=1, le=720)
    min_group: int = Field(default=2, ge=1, le=100)
