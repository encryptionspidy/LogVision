"""
Rule-based alerting engine.

Checks log entries against configured rules and triggers notifications.
"""

import logging
from typing import List, Optional
from models.schemas import LogEntry, AnomalyResult, SeverityResult, AlertConfig, Alert
from app.alerts.notifier import Notifier

logger = logging.getLogger(__name__)

# Default rules (Can be loaded from config file later)
DEFAULT_RULES = [
    AlertConfig(
        name="Critical Error",
        severity_threshold="CRITICAL",
        cooldown_seconds=300,
        enabled=True
    ),
    AlertConfig(
        name="Database Failure",
        match_keyword="database connection failed", 
        cooldown_seconds=600,
        enabled=True
    ),
    AlertConfig(
        name="Security/Auth Failure",
        match_keyword="failed password",
        severity_threshold="HIGH",
        cooldown_seconds=120,
        enabled=True
    )
]

class AlertEngine:
    """
    Evaluates logs against alert rules.
    """
    def __init__(self, rules: List[AlertConfig] = None, notifier: Notifier = None):
        self.rules = rules or DEFAULT_RULES
        self.notifier = notifier or Notifier()

    def check_entry(self, entry: LogEntry, severity: SeverityResult, anomaly: AnomalyResult):
        """
        Check a single log entry against all enabled rules.
        """
        for rule in self.rules:
            if not rule.enabled:
                continue

            triggered = False
            trigger_reason = ""

            # Check 1: Severity Threshold
            if rule.severity_threshold:
                if severity.level.value == rule.severity_threshold:
                    triggered = True
                    trigger_reason = f"Severity {severity.level.value} matched threshold"
            
            # Check 2: Keyword Match
            if rule.match_keyword:
                if rule.match_keyword.lower() in entry.message.lower():
                    triggered = True
                    trigger_reason = f"Message matched keyword '{rule.match_keyword}'"

            if triggered:
                # Dispatch Alert
                alert = Alert(
                    rule_name=rule.name,
                    timestamp=entry.timestamp,
                    message=entry.message,
                    log_entry=entry,
                    severity=severity.level.value,
                    details=trigger_reason
                )
                self.notifier.send_alert(alert, rule.cooldown_seconds)
