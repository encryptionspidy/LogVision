from __future__ import annotations

import pytest

from api.server import create_app
from app.storage.database import init_db, close_db


@pytest.fixture
def client():
    init_db(":memory:", force=True)
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
    close_db()


class TestPhase5AnalysisEndpoints:
    def test_analysis_summary_empty_db(self, client):
        resp = client.get("/analysis/summary?hours=24")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "executive_summary" in data
        assert "risk_assessment" in data
        assert "recommended_actions" in data
        assert "key_anomalies" in data
        assert isinstance(data["recommended_actions"], list)

    def test_analysis_root_causes_empty_db(self, client):
        resp = client.get("/analysis/root-causes?hours=24")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_analysis_patterns_empty_db(self, client):
        resp = client.get("/analysis/patterns?hours=24")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_analysis_clusters_empty_db(self, client):
        resp = client.get("/analysis/clusters?hours=24")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "clusters" in data
        assert "metrics" in data
        assert isinstance(data["clusters"], list)

