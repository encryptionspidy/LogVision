"""
Semantic tagging for log messages.

Provides deterministic keyword-based tags to enrich downstream explanation
and incident grouping quality.
"""

from __future__ import annotations

from typing import Iterable

_TAG_RULES: dict[str, tuple[str, ...]] = {
    "authentication": (
        "auth", "authentication", "login", "invalid token", "token expired",
        "unauthorized", "forbidden", "permission denied", "credential",
    ),
    "network": (
        "connection", "socket", "dns", "network", "refused", "reset", "broken pipe", "unreachable",
    ),
    "database": (
        "database", "db", "sql", "query", "postgres", "mysql", "deadlock", "transaction",
    ),
    "filesystem": (
        "file", "filesystem", "disk", "inode", "mount", "read-only", "no such file", "path",
    ),
    "permission": (
        "permission", "access denied", "forbidden", "unauthorized", "policy", "acl",
    ),
    "timeout": (
        "timeout", "timed out", "deadline exceeded", "latency", "slow response",
    ),
    "resource": (
        "memory", "oom", "cpu", "load", "throttle", "quota", "no space", "resource exhausted",
    ),
}


def infer_semantic_tags(*parts: str | None) -> list[str]:
    text = " ".join(p for p in parts if p).lower()
    if not text:
        return []

    tags: list[str] = []
    for tag, keywords in _TAG_RULES.items():
        if any(k in text for k in keywords):
            tags.append(tag)

    # stable ordering for deterministic UX
    ordered = [k for k in _TAG_RULES.keys() if k in tags]
    return ordered


def top_tag(tags: Iterable[str]) -> str | None:
    for tag in tags:
        return tag
    return None
