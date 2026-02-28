"""Tests for Phase 2 API endpoints."""

import pytest
import json
from api.server import create_app
from app.storage.database import init_db, get_db, close_db
from app.security.auth import create_token, ROLE_ADMIN

@pytest.fixture
def client():
    # Force new DB per test
    init_db(":memory:", force=True)
    
    app = create_app()
    app.config["TESTING"] = True
    
    with app.test_client() as client:
        yield client
        
    close_db()

def test_search_endpoint_empty_db(client):
    """Search on empty DB should return 0 results."""
    # Ensure DB initialized (create_app does this for :memory:)
    resp = client.get("/search?q=test")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 0
    assert data["items"] == []

def test_analytics_endpoint(client):
    """Analytics should return default structure even if empty."""
    resp = client.get("/analytics?hours=24")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "total_entries" in data
    assert "anomaly_rate" in data
    assert "top_sources" in data

def test_alerts_config_endpoint(client):
    """Alerts config should return default rules."""
    resp = client.get("/alerts/config")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["name"] == "Critical Error"

def test_analyze_persists_to_db(client, tmp_path):
    """Verify batch analysis persists to DB."""
    token = create_token("test_admin", ROLE_ADMIN)
    headers = {"Authorization": f"Bearer {token}"}
    # Create dummy log
    log_file = tmp_path / "test.log"
    log_file.write_text("Jan 15 10:30:45 host app: ERROR: Database connection failed\n")
    
    with open(log_file, "rb") as f:
        client.post("/analyze", data={"file": (f, "test.log")}, headers=headers)
        
    # Search should now find it
    resp = client.get("/search?q=database")
    data = resp.get_json()
    assert data["total"] == 1
    assert "Database connection failed" in data["items"][0]["message"]
