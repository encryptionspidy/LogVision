"""
Severity scoring weight configuration.

All weights and thresholds are defined here, not in scorer logic.
"""

from app.config.settings import DEFAULT_CONFIG

# Re-export from central config for convenience
SEVERITY_CONFIG = DEFAULT_CONFIG.severity

# Explicit constants for direct import
RULE_WEIGHT: float = SEVERITY_CONFIG.rule_weight
FREQUENCY_WEIGHT: float = SEVERITY_CONFIG.frequency_weight
ANOMALY_WEIGHT: float = SEVERITY_CONFIG.anomaly_weight

CRITICAL_THRESHOLD: float = SEVERITY_CONFIG.critical_threshold
HIGH_THRESHOLD: float = SEVERITY_CONFIG.high_threshold
MEDIUM_THRESHOLD: float = SEVERITY_CONFIG.medium_threshold

LEVEL_BASE_SCORES: dict[str, float] = dict(SEVERITY_CONFIG.level_base_scores)
