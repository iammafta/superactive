"""
Integration tests for Telnyx Settings.

Tests that Telnyx credentials can be saved, read back (masked), and cleared
through the Settings API. Runs against a live PostgreSQL database.
"""

import pytest
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["POSTGRES_DB"] = "superactive"


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def app():
    from server import app
    from rate_limit import limiter
    limiter.enabled = False
    app.state.limiter = limiter
    yield app
    limiter.enabled = True


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_client(client):
    """Register + login, return an authenticated client."""
    unique_id = str(uuid.uuid4())
    reg_res = client.post("/api/auth/register", json={
        "email": f"telnyx_test_{unique_id}@test.com",
        "password": "SecurePassword123!",
        "business_name": f"Telnyx Test Corp {unique_id}"
    })
    assert reg_res.status_code == 200, f"Register failed: {reg_res.text}"
    return client


# ── Tests ─────────────────────────────────────────────────────────────

class TestTelnyxSettings:
    """End-to-end tests for per-tenant Telnyx credential management."""

    def test_get_settings_returns_masked_defaults(self, auth_client):
        """GET /api/settings should return masked Telnyx values (from env or empty)."""
        res = auth_client.get("/api/settings")
        assert res.status_code == 200
        data = res.json()

        # Must have these keys
        assert "telnyx_api_key_masked" in data
        assert "telnyx_connection_id_masked" in data
        assert "telnyx_phone" in data
        assert "has_custom_telnyx" in data

        # New tenant should NOT have custom telnyx
        assert data["has_custom_telnyx"] is False

    def test_save_telnyx_credentials(self, auth_client):
        """PUT /api/settings with telnyx fields should persist and mask them."""
        # 1. Save credentials
        save_res = auth_client.put("/api/settings", json={
            "telnyx_api_key": "KEY_test_api_key_1234567890abcdef",
            "telnyx_connection_id": "test_connection_id_abcdef12",
            "telnyx_phone": "+15551234567",
        })
        assert save_res.status_code == 200
        assert save_res.json()["status"] == "saved"

        # 2. Read back
        get_res = auth_client.get("/api/settings")
        assert get_res.status_code == 200
        data = get_res.json()

        # API key should be masked but recognizable
        assert data["telnyx_api_key_masked"] != "••••"  # Not fully masked
        assert "••" in data["telnyx_api_key_masked"]  # Contains mask chars
        # Connection ID should be masked
        assert "••" in data["telnyx_connection_id_masked"]
        # Phone should be returned as-is
        assert data["telnyx_phone"] == "+15551234567"
        # Flag should be set
        assert data["has_custom_telnyx"] is True

    def test_partial_telnyx_update(self, auth_client):
        """Updating only telnyx_phone should not clear api_key/connection_id."""
        # 1. Save all three
        auth_client.put("/api/settings", json={
            "telnyx_api_key": "KEY_partial_test_api_key_abcdef12",
            "telnyx_connection_id": "partial_conn_id_1234567890ab",
            "telnyx_phone": "+15559999999",
        })

        # 2. Update only phone
        auth_client.put("/api/settings", json={
            "telnyx_phone": "+15558888888",
        })

        # 3. Read back — API key should still be set
        get_res = auth_client.get("/api/settings")
        data = get_res.json()
        assert data["has_custom_telnyx"] is True
        assert data["telnyx_phone"] == "+15558888888"

    def test_clear_telnyx_falls_back_to_env(self, auth_client):
        """Saving empty strings for Telnyx fields should fall back to env vars."""
        # 1. Set custom creds
        auth_client.put("/api/settings", json={
            "telnyx_api_key": "KEY_temp_api_key_to_clear",
            "telnyx_connection_id": "temp_conn_id_to_clear_abc",
            "telnyx_phone": "+15557777777",
        })

        # 2. Clear them
        auth_client.put("/api/settings", json={
            "telnyx_api_key": "",
            "telnyx_connection_id": "",
            "telnyx_phone": "",
        })

        # 3. Read back — should fall back to env vars
        get_res = auth_client.get("/api/settings")
        data = get_res.json()
        assert data["has_custom_telnyx"] is False

    def test_save_only_business_fields_unchanged_telnyx(self, auth_client):
        """Saving only business_name should not affect Telnyx credentials."""
        # 1. Set telnyx creds
        auth_client.put("/api/settings", json={
            "telnyx_api_key": "KEY_stable_api_key_1234567890ab",
        })

        # 2. Update business name only (no telnyx fields)
        auth_client.put("/api/settings", json={
            "business_name": "Updated Business Name"
        })

        # 3. Telnyx should still be set
        get_res = auth_client.get("/api/settings")
        data = get_res.json()
        assert data["has_custom_telnyx"] is True
        assert data["business_name"] == "Updated Business Name"
