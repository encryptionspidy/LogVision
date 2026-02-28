"""
Structured prompt templates for log explanation generation.

Templates are organized by anomaly type and severity level.
Variables use Python str.format() syntax with named placeholders.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExplanationTemplate:
    """
    Template for generating a human-readable explanation.

    Attributes:
        summary_template: One-line summary with format placeholders.
        cause_templates: List of possible cause templates.
        remediation_templates: List of remediation step templates.
    """
    summary_template: str
    cause_templates: list[str] = field(default_factory=list)
    remediation_templates: list[str] = field(default_factory=list)


# ─── Templates by Anomaly Type ──────────────────────────────────────────

CRITICAL_KEYWORD_TEMPLATE = ExplanationTemplate(
    summary_template=(
        "{severity} severity: Detected critical keyword(s) in {log_level} log entry."
    ),
    cause_templates=[
        "Critical system event detected: {details}",
        "Possible causes include system resource exhaustion, service crash, or security incident.",
        "The log message '{message_preview}' suggests a significant operational issue.",
    ],
    remediation_templates=[
        "Immediately investigate the affected service or system component.",
        "Check system resource utilization (memory, disk, CPU).",
        "Review recent deployment or configuration changes.",
        "If security-related, initiate incident response procedures.",
    ],
)

FREQUENCY_SPIKE_TEMPLATE = ExplanationTemplate(
    summary_template=(
        "{severity} severity: Abnormal frequency spike detected in log entries."
    ),
    cause_templates=[
        "Frequency anomaly: {details}",
        "Possible causes include retry storms, cascading failures, or DDoS activity.",
        "A sudden increase in log volume often indicates a system under stress.",
    ],
    remediation_templates=[
        "Identify the root cause of the log volume spike.",
        "Check for retry loops or cascading failure patterns.",
        "Monitor system resources during the spike period.",
        "Consider implementing rate limiting or circuit breakers.",
    ],
)

REPEATED_ERROR_TEMPLATE = ExplanationTemplate(
    summary_template=(
        "{severity} severity: Repeated error pattern detected."
    ),
    cause_templates=[
        "Recurring error: {details}",
        "Possible causes include persistent misconfiguration, dependency failure, or unresolved bug.",
        "Repeated errors often indicate a systematic issue rather than a transient fault.",
    ],
    remediation_templates=[
        "Investigate the root cause of the recurring error.",
        "Check dependent services and connectivity.",
        "Review application configuration and recent changes.",
        "Consider adding alerting for this error pattern.",
    ],
)

ML_DETECTED_TEMPLATE = ExplanationTemplate(
    summary_template=(
        "{severity} severity: Statistical anomaly detected by ML analysis."
    ),
    cause_templates=[
        "ML anomaly detection flagged this entry as statistically unusual.",
        "Possible causes include unusual timing, message structure, or error patterns.",
        "This may indicate a novel issue not covered by existing rules.",
    ],
    remediation_templates=[
        "Review the log entry in context with surrounding entries.",
        "Compare against baseline behavior for this service.",
        "If this is a false positive, consider adding to the exclusion rules.",
    ],
)

ERROR_LEVEL_TEMPLATE = ExplanationTemplate(
    summary_template=(
        "{severity} severity: {log_level}-level event recorded."
    ),
    cause_templates=[
        "An {log_level}-level event was logged: '{message_preview}'",
        "Possible causes include application errors, failed operations, or misconfiguration.",
    ],
    remediation_templates=[
        "Review the error message and stack trace if available.",
        "Check application logs for additional context.",
        "Verify service health and dependencies.",
    ],
)

DEFAULT_TEMPLATE = ExplanationTemplate(
    summary_template=(
        "{severity} severity: Log entry flagged for review."
    ),
    cause_templates=[
        "This entry was flagged based on combined analysis.",
        "Possible causes include unusual patterns or elevated risk indicators.",
    ],
    remediation_templates=[
        "Review the log entry and its context.",
        "Monitor for recurrence of similar patterns.",
    ],
)

NORMAL_TEMPLATE = ExplanationTemplate(
    summary_template=(
        "Normal operation: {log_level}-level log entry."
    ),
    cause_templates=[
        "This entry appears to be within normal operating parameters.",
    ],
    remediation_templates=[
        "No immediate action required.",
    ],
)


# ─── Template Registry ──────────────────────────────────────────────────

TEMPLATE_MAP: dict[str, ExplanationTemplate] = {
    "critical_keyword": CRITICAL_KEYWORD_TEMPLATE,
    "frequency_spike": FREQUENCY_SPIKE_TEMPLATE,
    "repeated_error": REPEATED_ERROR_TEMPLATE,
    "ml_detected": ML_DETECTED_TEMPLATE,
    "error_level": ERROR_LEVEL_TEMPLATE,
    "critical_level": CRITICAL_KEYWORD_TEMPLATE,
    "none": NORMAL_TEMPLATE,
}


def get_template(anomaly_type: str) -> ExplanationTemplate:
    """
    Get the explanation template for a given anomaly type.

    Falls back to DEFAULT_TEMPLATE for unknown types.
    """
    return TEMPLATE_MAP.get(anomaly_type, DEFAULT_TEMPLATE)
