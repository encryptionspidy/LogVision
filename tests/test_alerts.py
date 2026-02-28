"""Tests for app.alerts.engine and notifier."""

import pytest
import time
from datetime import datetime
from models.schemas import LogEntry, LogLevel, SeverityResult, SeverityLevel, AnomalyResult, AlertConfig
from app.alerts.engine import AlertEngine
from app.alerts.notifier import Notifier

@pytest.fixture
def mock_notifier():
    notifier = Notifier()
    notifier._dispatched_alerts = [] # backdoor for testing
    
    def mock_dispatch(alert):
        notifier._dispatched_alerts.append(alert)
        
    notifier._dispatch_console = mock_dispatch
    notifier._dispatch_webhook = lambda a: None
    return notifier

@pytest.fixture
def alert_engine(mock_notifier):
    rules = [
        AlertConfig(name="CritRule", severity_threshold="CRITICAL", cooldown_seconds=1),
        AlertConfig(name="DBRule", match_keyword="database", cooldown_seconds=1),
    ]
    return AlertEngine(rules, mock_notifier)

def make_entry(msg="test", level=LogLevel.INFO):
    return LogEntry(
        raw=msg, line_number=1, timestamp=datetime.utcnow(),
        log_level=level, message=msg, source="test", log_type="test"
    )

def test_severity_trigger(alert_engine, mock_notifier):
    entry = make_entry(level=LogLevel.CRITICAL)
    sev = SeverityResult(level=SeverityLevel.CRITICAL, score=1.0)
    anom = AnomalyResult()
    
    alert_engine.check_entry(entry, sev, anom)
    
    assert len(mock_notifier._dispatched_alerts) == 1
    assert mock_notifier._dispatched_alerts[0].rule_name == "CritRule"

def test_keyword_trigger(alert_engine, mock_notifier):
    entry = make_entry(msg="Database connection lost")
    sev = SeverityResult(level=SeverityLevel.HIGH)
    anom = AnomalyResult()
    
    alert_engine.check_entry(entry, sev, anom)
    
    assert len(mock_notifier._dispatched_alerts) == 1
    assert mock_notifier._dispatched_alerts[0].rule_name == "DBRule"

def test_cooldown_logic(alert_engine, mock_notifier):
    entry = make_entry(level=LogLevel.CRITICAL)
    sev = SeverityResult(level=SeverityLevel.CRITICAL)
    anom = AnomalyResult()
    
    # First trigger
    alert_engine.check_entry(entry, sev, anom)
    assert len(mock_notifier._dispatched_alerts) == 1
    
    # Immediate second trigger (should be suppressed)
    alert_engine.check_entry(entry, sev, anom)
    assert len(mock_notifier._dispatched_alerts) == 1
    
    # Wait for cooldown
    time.sleep(1.1)
    
    # Third trigger (should succeed)
    alert_engine.check_entry(entry, sev, anom)
    assert len(mock_notifier._dispatched_alerts) == 2
