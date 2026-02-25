"""
Tests for JWT HttpOnly cookie authentication flow.

Validates the full lifecycle: login sets cookies, cookies authenticate
protected endpoints, logout clears cookies, and header auth still works.

Uses mocked DB functions to avoid requiring a running PostgreSQL instance.
"""
import os
import sys
import pytest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import hash_password, create_token, COOKIE_NAME, verify_ws_ticket
import uuid

@pytest.fixture(autouse=True)
def bypass_rate_limit():
    from rate_limit import limiter
    limiter.enabled = False
    yield
    limiter.enabled = True

# ── Fixtures ──────────────────────────────────────────────────────────

async def mock_ws_connect(websocket, *args, **kwargs):
    await websocket.accept()

MOCK_TENANT = {"id": "t-test-001", "name": "Test Corp", "email": "test@test.com", "plan": "starter"}
MOCK_PASSWORD = "secure-password-12345"
MOCK_PASSWORD_HASH = hash_password(MOCK_PASSWORD)
MOCK_USER = {
    "id": "u-test-001",
    "email": "test@test.com",
    "password_hash": MOCK_PASSWORD_HASH,
    "tenant_id": "t-test-001",
    "role": "admin",
    "tenant_name": "Test Corp",
}


@pytest.fixture
def client():
    """Create a FastAPI TestClient with mocked DB dependencies."""
    with patch("routes.auth.db_get_user_by_email", new_callable=AsyncMock) as mock_get_user, \
         patch("routes.auth.db_create_tenant", new_callable=AsyncMock) as mock_create_tenant, \
         patch("routes.auth.db_create_user", new_callable=AsyncMock) as mock_create_user, \
         patch("routes.auth.db_get_tenant", new_callable=AsyncMock) as mock_get_tenant, \
         patch("db.get_pool", new_callable=AsyncMock), \
         patch("db.init_db", new_callable=AsyncMock), \
         patch("routes.monitor.live_monitor.connect", side_effect=mock_ws_connect), \
         patch("routes.monitor.call_logger.get_active_calls", return_value=[]):

        # Configure mocks
        mock_get_user.return_value = MOCK_USER
        mock_create_tenant.return_value = MOCK_TENANT
        mock_create_user.return_value = MOCK_USER
        mock_get_tenant.return_value = MOCK_TENANT

        from fastapi.testclient import TestClient
        from server import app
        app.state.limiter.enabled = False
        yield TestClient(app)


@pytest.fixture
def client_no_user():
    """TestClient with db_get_user_by_email returning None (for register)."""
    with patch("routes.auth.db_get_user_by_email", new_callable=AsyncMock) as mock_get_user, \
         patch("routes.auth.db_create_tenant", new_callable=AsyncMock) as mock_create_tenant, \
         patch("routes.auth.db_create_user", new_callable=AsyncMock) as mock_create_user, \
         patch("routes.auth.db_get_tenant", new_callable=AsyncMock) as mock_get_tenant, \
         patch("db.get_pool", new_callable=AsyncMock), \
         patch("db.init_db", new_callable=AsyncMock):

        mock_get_user.return_value = None
        mock_create_tenant.return_value = MOCK_TENANT
        mock_create_user.return_value = MOCK_USER
        mock_get_tenant.return_value = MOCK_TENANT

        from fastapi.testclient import TestClient
        from server import app
        app.state.limiter.enabled = False
        yield TestClient(app)


# ── Tests ─────────────────────────────────────────────────────────────

class TestLoginSetsCookie:
    """POST /api/auth/login should set an HttpOnly cookie."""

    def test_login_sets_httponly_cookie(self, client):
        res = client.post("/api/auth/login", json={
            "email": "test@test.com",
            "password": MOCK_PASSWORD,
        })
        assert res.status_code == 200

        # Check Set-Cookie header
        set_cookie = res.headers.get("set-cookie", "")
        assert COOKIE_NAME in set_cookie
        assert "httponly" in set_cookie.lower()
        assert "samesite=lax" in set_cookie.lower()
        assert "path=/" in set_cookie.lower()

    def test_login_still_returns_token_in_body(self, client):
        res = client.post("/api/auth/login", json={
            "email": "test@test.com",
            "password": MOCK_PASSWORD,
        })
        data = res.json()
        assert "token" in data
        assert len(data["token"]) > 20


class TestRegisterSetsCookie:
    """POST /api/auth/register should set an HttpOnly cookie."""

    def test_register_sets_httponly_cookie(self, client_no_user):
        res = client_no_user.post("/api/auth/register", json={
            "email": "new@test.com",
            "password": "a-long-secure-password",
            "business_name": "New Corp",
        })
        assert res.status_code == 200

        set_cookie = res.headers.get("set-cookie", "")
        assert COOKIE_NAME in set_cookie
        assert "httponly" in set_cookie.lower()


class TestCookieAuth:
    """Protected endpoints should accept cookie-based auth."""

    def test_cookie_auth_on_protected_endpoint(self, client):
        # First, login to get the cookie
        login_res = client.post("/api/auth/login", json={
            "email": "test@test.com",
            "password": MOCK_PASSWORD,
        })
        assert login_res.status_code == 200

        # Call /api/auth/me with the cookie (no Authorization header)
        me_res = client.get("/api/auth/me")
        assert me_res.status_code == 200
        data = me_res.json()
        assert data["email"] == "test@test.com"
        assert data["tenant_id"] == "t-test-001"

    def test_header_auth_still_works(self, client):
        """Backwards compatibility: Authorization header should still work."""
        token = create_token(
            user_id="u-test-001",
            tenant_id="t-test-001",
            email="test@test.com",
            role="admin",
        )
        me_res = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert me_res.status_code == 200
        data = me_res.json()
        assert data["email"] == "test@test.com"


class TestLogout:
    """POST /api/auth/logout should clear the cookie."""

    def test_logout_clears_cookie(self, client):
        # Login first
        client.post("/api/auth/login", json={
            "email": "test@test.com",
            "password": MOCK_PASSWORD,
        })

        # Logout
        logout_res = client.post("/api/auth/logout")
        assert logout_res.status_code == 200
        assert logout_res.json() == {"ok": True}

        # Verify the Set-Cookie header expires/clears the cookie
        set_cookie = logout_res.headers.get("set-cookie", "")
        assert COOKIE_NAME in set_cookie
        # FastAPI delete_cookie sets max-age=0 or expires in the past
        assert 'max-age=0' in set_cookie.lower() or '1970' in set_cookie


class TestWebSocketTicket:
    """POST /api/auth/ticket should generate a short-lived WS ticket."""

    def test_get_ticket_with_cookie(self, client):
        client.cookies.clear()
        # Login
        login_res = client.post("/api/auth/login", json={
            "email": "test@test.com",
            "password": MOCK_PASSWORD,
        })
        client.cookies = login_res.cookies

        # Get ticket
        res = client.post("/api/auth/ticket")
        assert res.status_code == 200
        data = res.json()
        assert "ticket" in data

        # Verify ticket
        tenant_id = verify_ws_ticket(data["ticket"])
        assert tenant_id == "t-test-001"

    def test_get_ticket_fails_without_auth(self, client):
        res = client.post("/api/auth/ticket")
        assert res.status_code == 401
        
    def test_websocket_connects_with_ticket(self, client):
        client.cookies.clear()
        # 1. Login
        login_res = client.post("/api/auth/login", json={
            "email": "test@test.com",
            "password": MOCK_PASSWORD,
        })
        client.cookies = login_res.cookies

        # 2. Get ticket
        res = client.post("/api/auth/ticket")
        ticket = res.json()["ticket"]

        # 3. Connect to WS with ticket
        with client.websocket_connect(f"/ws/monitor?token={ticket}") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "active_calls_update"

    def test_websocket_rejects_without_ticket(self, client):
        from starlette.websockets import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws/monitor"):
                pass
        assert exc.value.code == 4001


class TestNoAuth:
    """Requests with no auth should be rejected."""

    def test_no_auth_returns_401(self, client):
        res = client.get("/api/auth/me")
        assert res.status_code == 401
