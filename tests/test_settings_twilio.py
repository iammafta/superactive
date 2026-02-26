"""
Integration tests for Twilio Settings (Sprint 5).

Tests that Twilio credentials can be saved, read back (masked), and cleared
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
        "email": f"twilio_test_{unique_id}@test.com",
        "password": "SecurePassword123!",
        "business_name": f"Twilio Test Corp {unique_id}"
    })
    assert reg_res.status_code == 200, f"Register failed: {reg_res.text}"
    return client


# ── Tests ─────────────────────────────────────────────────────────────

class TestTwilioSettings:
    """End-to-end tests for per-tenant Twilio credential management."""

    def test_get_settings_returns_masked_defaults(self, auth_client):
        """GET /api/settings should return masked Twilio values (from env or empty)."""
        res = auth_client.get("/api/settings")
        assert res.status_code == 200
        data = res.json()

        # Must have these keys
        assert "twilio_sid_masked" in data
        assert "twilio_token_masked" in data
        assert "twilio_phone" in data
        assert "has_custom_twilio" in data

        # New tenant should NOT have custom twilio
        assert data["has_custom_twilio"] is False

    def test_save_twilio_credentials(self, auth_client):
        """PUT /api/settings with twilio fields should persist and mask them."""
        # 1. Save credentials
        save_res = auth_client.put("/api/settings", json={
            "twilio_sid": "AC_test_sid_1234567890abcdef",
            "twilio_token": "test_token_abcdef1234567890",
            "twilio_phone": "+15551234567",
        })
        assert save_res.status_code == 200
        assert save_res.json()["status"] == "saved"

        # 2. Read back
        get_res = auth_client.get("/api/settings")
        assert get_res.status_code == 200
        data = get_res.json()

        # SID should be masked but recognizable
        assert data["twilio_sid_masked"] != "••••"  # Not fully masked
        assert "••" in data["twilio_sid_masked"]  # Contains mask chars
        # Token should be masked
        assert "••" in data["twilio_token_masked"]
        # Phone should be returned as-is
        assert data["twilio_phone"] == "+15551234567"
        # Flag should be set
        assert data["has_custom_twilio"] is True

    def test_partial_twilio_update(self, auth_client):
        """Updating only twilio_phone should not clear sid/token."""
        # 1. Save all three
        auth_client.put("/api/settings", json={
            "twilio_sid": "AC_partial_test_sid_abcdef12",
            "twilio_token": "partial_token_1234567890ab",
            "twilio_phone": "+15559999999",
        })

        # 2. Update only phone
        auth_client.put("/api/settings", json={
            "twilio_phone": "+15558888888",
        })

        # 3. Read back — SID should still be set
        get_res = auth_client.get("/api/settings")
        data = get_res.json()
        assert data["has_custom_twilio"] is True
        assert data["twilio_phone"] == "+15558888888"

    def test_clear_twilio_falls_back_to_env(self, auth_client):
        """Saving empty strings for Twilio fields should fall back to env vars."""
        # 1. Set custom creds
        auth_client.put("/api/settings", json={
            "twilio_sid": "AC_temp_sid_to_clear",
            "twilio_token": "temp_token_to_clear_abc",
            "twilio_phone": "+15557777777",
        })

        # 2. Clear them
        auth_client.put("/api/settings", json={
            "twilio_sid": "",
            "twilio_token": "",
            "twilio_phone": "",
        })

        # 3. Read back — should fall back to env vars
        get_res = auth_client.get("/api/settings")
        data = get_res.json()
        assert data["has_custom_twilio"] is False

    def test_save_only_business_fields_unchanged_twilio(self, auth_client):
        """Saving only business_name should not affect Twilio credentials."""
        # 1. Set twilio creds
        auth_client.put("/api/settings", json={
            "twilio_sid": "AC_stable_sid_1234567890ab",
        })

        # 2. Update business name only (no twilio fields)
        auth_client.put("/api/settings", json={
            "business_name": "Updated Business Name"
        })

        # 3. Twilio should still be set
        get_res = auth_client.get("/api/settings")
        data = get_res.json()
        assert data["has_custom_twilio"] is True
        assert data["business_name"] == "Updated Business Name"
