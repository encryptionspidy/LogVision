"""
Security tests — JWT authentication, CORS, input validation.
"""

import json
import pytest

from api.server import create_app
from app.security.auth import create_token, ROLE_ADMIN, ROLE_VIEWER


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_token():
    return create_token("admin_user", ROLE_ADMIN)


@pytest.fixture
def viewer_token():
    return create_token("viewer_user", ROLE_VIEWER)


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def viewer_headers(viewer_token):
    return {"Authorization": f"Bearer {viewer_token}"}


# ─── Authentication ──────────────────────────────────────────────────────

class TestAuthentication:
    @pytest.fixture(autouse=True)
    def stop_dev_mode(self, monkeypatch):
        """Ensure DEV_MODE is OFF for all standard security tests."""
        monkeypatch.delenv("DEV_MODE", raising=False)

    def test_health_public(self, client):
        """Health endpoint should not require auth."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_search_public(self, client):
        """Search endpoint should be accessible without auth."""
        resp = client.get("/search")
        assert resp.status_code == 200

    def test_alerts_public(self, client):
        """Alert config endpoint should be accessible without auth."""
        resp = client.get("/alerts/config")
        assert resp.status_code == 200

    def test_analyze_requires_auth(self, client):
        """POST /analyze should require JWT."""
        resp = client.post("/analyze")
        assert resp.status_code == 401
        data = resp.get_json()
        assert "error" in data

    def test_analyze_input_validation_oversized(self, client, admin_headers):
        """Verify size limits on analyze endpoint."""
        from io import BytesIO
        # Server limit is 16MB. 17MB should definitively trigger error.
        large_data = b"x" * (1024 * 1024 * 17)
        resp = client.post(
            "/analyze",
            data={"file": (BytesIO(large_data), "large.log")},
            headers=admin_headers
        )
        assert resp.status_code in {413, 400, 422, 500}

    def test_analyze_rejects_viewer(self, client, viewer_headers):
        """POST /analyze should reject viewer role."""
        resp = client.post(
            "/analyze",
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    def test_analyze_allows_admin(self, client, admin_headers):
        """POST /analyze should accept admin role."""
        from io import BytesIO
        resp = client.post(
            "/analyze",
            data={"file": (BytesIO(b"test log"), "test.log")},
            headers=admin_headers,
        )
        assert resp.status_code == 200

    def test_malformed_token(self, client):
        """Invalid JWT should return 401."""
        resp = client.post(
            "/analyze",
            headers={"Authorization": "Bearer not.a.real.token"},
        )
        assert resp.status_code == 401

    def test_missing_bearer_prefix(self, client, admin_token):
        """Authorization header without 'Bearer ' prefix should fail."""
        resp = client.post(
            "/analyze",
            headers={"Authorization": admin_token},
        )
        assert resp.status_code == 401


# ─── Dev Mode ────────────────────────────────────────────────────────────

class TestDevMode:
    def test_dev_mode_auto_auth(self, monkeypatch):
        """Verify DEV_MODE auto-injects admin token."""
        monkeypatch.setenv("DEV_MODE", "1")

        # Re-create app to pick up injected middleware
        app = create_app()
        app.config["TESTING"] = True
        
        with app.test_client() as client:
            from io import BytesIO
            resp = client.post("/analyze", data={"file": (BytesIO(b"dev log"), "dev.log")})
            assert resp.status_code == 200
            data = resp.get_json()
            assert "total_entries" in data


# ─── Login Endpoint ──────────────────────────────────────────────────────

class TestLogin:
    def test_login_success(self, client):
        resp = client.post(
            "/login",
            data=json.dumps({"username": "testuser"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "token" in data
        assert data["username"] == "testuser"

    def test_login_missing_username(self, client):
        resp = client.post(
            "/login",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_login_with_role(self, client):
        resp = client.post(
            "/login",
            data=json.dumps({"username": "admin", "role": "admin"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["role"] == "admin"


# ─── Input Validation ────────────────────────────────────────────────────

class TestInputValidation:
    def test_sql_injection_search(self, client):
        """SQL injection in search should not crash the server."""
        resp = client.get("/search?q='; DROP TABLE logs; --")
        assert resp.status_code == 200

    def test_malformed_json_login(self, client):
        """Malformed JSON in login should return error."""
        resp = client.post(
            "/login",
            data="not valid json",
            content_type="application/json",
        )
        # Should handle gracefully (400 from empty username)
        assert resp.status_code == 400

    def test_oversized_query_param(self, client):
        """Very long query strings should not crash."""
        long_q = "a" * 10000
        resp = client.get(f"/search?q={long_q}")
        assert resp.status_code == 200
