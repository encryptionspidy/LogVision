"""
Alert notification system with cooldowns.
"""

import logging
import time
from typing import Dict, Any
from models.schemas import Alert

logger = logging.getLogger(__name__)

class Notifier:
    """
    Handles dispatching alerts and managing cooldowns.
    """
    def __init__(self):
        # Map rule_name -> last_alert_timestamp
        self._last_alerted: Dict[str, float] = {}

    def should_send(self, rule_name: str, cooldown_seconds: int) -> bool:
        """Check if cooldown has expired for this rule."""
        now = time.time()
        last = self._last_alerted.get(rule_name, 0)
        
        if now - last >= cooldown_seconds:
            return True
        return False

    def send_alert(self, alert: Alert, cooldown_seconds: int = 300):
        """
        Dispatch alert if cooldown passes.
        Currently logs to console/file. Can be extended to Email/Webhook.
        """
        if not self.should_send(alert.rule_name, cooldown_seconds):
            logger.debug("Alert '%s' suppressed due to cooldown", alert.rule_name)
            return

        # Mark as sent
        self._last_alerted[alert.rule_name] = time.time()
        
        # Dispatch (Mock implementation)
        self._dispatch_console(alert)
        self._dispatch_webhook(alert)

    def _dispatch_console(self, alert: Alert):
        """Log alert to console/logger."""
        logger.critical(
            f"🚨 ALERT TRIGGERED: {alert.rule_name}\n"
            f"   Severity: {alert.severity}\n"
            f"   Message: {alert.message}\n"
            f"   Details: {alert.details}"
        )
        # In production, this might go to a dedicated alert log file

    def _dispatch_webhook(self, alert: Alert):
        """Mock webhook dispatch."""
        # TODO: Implement actual requests.post if configured
        pass
