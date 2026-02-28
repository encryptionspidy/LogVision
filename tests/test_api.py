"""Tests for api.server — Flask API endpoint tests."""

import io
import json
import pytest
from api.server import create_app
from app.security.auth import create_token, ROLE_ADMIN


@pytest.fixture
def client():
    """Create a Flask test client."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def admin_headers():
    """Auth headers for admin user."""
    token = create_token("test_admin", ROLE_ADMIN)
    return {"Authorization": f"Bearer {token}"}


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"


class TestAnalyzeEndpoint:
    def test_no_file_returns_400(self, client, admin_headers):
        response = client.post("/analyze", headers=admin_headers)
        assert response.status_code == 400

    def test_empty_file_name_returns_400(self, client, admin_headers):
        response = client.post("/analyze", data={
            "file": (io.BytesIO(b""), ""),
        }, headers=admin_headers)
        assert response.status_code == 400

    def test_wrong_extension_returns_400(self, client, admin_headers):
        response = client.post("/analyze", data={
            "file": (io.BytesIO(b"data"), "test.csv"),
        }, content_type="multipart/form-data", headers=admin_headers)
        assert response.status_code == 400

    def test_valid_log_file_returns_200(self, client, admin_headers, sample_log_path):
        with open(sample_log_path, "rb") as f:
            response = client.post("/analyze", data={
                "file": (f, "sample.log"),
            }, content_type="multipart/form-data", headers=admin_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert "results" in data
        assert "summary" in data
        assert data["total_entries"] > 0

    def test_response_structure(self, client, admin_headers, sample_log_path):
        with open(sample_log_path, "rb") as f:
            response = client.post("/analyze", data={
                "file": (f, "sample.log"),
            }, content_type="multipart/form-data", headers=admin_headers)
        data = response.get_json()
        # Check first result has expected structure
        result = data["results"][0]
        assert "log_entry" in result
        assert "anomaly" in result
        assert "severity" in result
        assert "explanation" in result
        # Check severity has level
        assert result["severity"]["level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_summary_has_distribution(self, client, admin_headers, sample_log_path):
        with open(sample_log_path, "rb") as f:
            response = client.post("/analyze", data={
                "file": (f, "sample.log"),
            }, content_type="multipart/form-data", headers=admin_headers)
        summary = response.get_json()["summary"]
        assert "severity_distribution" in summary
        assert "anomalies_detected" in summary

    def test_corrupted_file_still_processes(self, client, admin_headers, corrupted_log_path):
        """Corrupted/unknown format should still return 200 with UNCLASSIFIED entries."""
        with open(corrupted_log_path, "rb") as f:
            response = client.post("/analyze", data={
                "file": (f, "corrupted.log"),
            }, content_type="multipart/form-data", headers=admin_headers)
        assert response.status_code == 200


class TestUIServing:
    def test_root_serves_html(self, client):
        response = client.get("/")
        assert response.status_code == 200
