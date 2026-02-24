import pytest
import os
import uuid
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["POSTGRES_DB"] = "superactive"
os.environ["DISABLE_TELEMETRY"] = "1"


def _sync_insert_call(tenant_id: str, agent_id: str, call_id: str):
    """Insert a fake completed call directly into PostgreSQL using synchronous psycopg2.
    This avoids all asyncio event loop conflicts with FastAPI's TestClient."""
    import psycopg2

    dsn = (
        f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
        f"port={os.environ.get('POSTGRES_PORT', '5432')} "
        f"dbname={os.environ.get('POSTGRES_DB', 'superactive')} "
        f"user={os.environ.get('POSTGRES_USER', 'superactive')} "
        f"password={os.environ.get('POSTGRES_PASSWORD', 'superactive')}"
    )
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO calls (call_id, tenant_id, agent_id, started_at, ended_at, "
                "duration_seconds, outcome) "
                "VALUES (%s, %s, %s, NOW(), NOW(), 45, 'booked') "
                "ON CONFLICT DO NOTHING",
                (call_id, tenant_id, agent_id),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def app():
    from server import app
    app.state.limiter.enabled = False
    return app


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c


class TestIntegrationOnboarding:
    """End-to-end user journey: Register -> Create Agent -> Campaign -> Analytics."""

    def test_end_to_end_onboarding_flow(self, client):
        # -- 1. Register a new User --
        unique_id = str(uuid.uuid4())
        email = f"new_user_{unique_id}@onboarding.com"
        password = "SecurePassword123!"

        reg_res = client.post("/api/auth/register", json={
            "email": email,
            "password": password,
            "business_name": "New Onboarding Co"
        })
        assert reg_res.status_code == 200, f"Register failed: {reg_res.text}"

        # -- 2. Login (sets HttpOnly cookie) --
        login_res = client.post("/api/auth/login", json={
            "email": email,
            "password": password
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"

        # -- 3. Create an Agent --
        create_res = client.post("/api/agents", json={
            "name": "Onboarding Bot",
            "business_type": "sales",
            "system_prompt": "You are a sales specialist.",
            "language": "en",
            "voice_prompt": "Friendly",
            "voice_id": "onbd_voice",
            "allowed_tools": []
        })
        assert create_res.status_code == 200, f"Create agent failed: {create_res.text}"
        agent_id = create_res.json()["id"]

        # -- 4. Verify Dashboard Zero-State Analytics --
        analytics_empty_res = client.get("/api/analytics")
        assert analytics_empty_res.status_code == 200
        empty_data = analytics_empty_res.json()
        assert empty_data["total_calls"] == 0, "Brand new user should have 0 total calls"

        # -- 5. Create a Campaign and Upload 1 Contact --
        create_camp_res = client.post("/api/campaigns", json={
            "name": "First Campaign",
            "agent_id": agent_id,
            "max_concurrent_calls": 5
        })
        assert create_camp_res.status_code == 200, f"Create campaign failed: {create_camp_res.text}"
        campaign_id = create_camp_res.json()["id"]

        csv_content = "name,phone\nJane Doe,+19998887777\n"
        upload_res = client.post(
            f"/api/campaigns/{campaign_id}/upload-contacts",
            files={"file": ("onboarding.csv", csv_content, "text/csv")}
        )
        assert upload_res.status_code == 200, f"Upload contacts failed: {upload_res.text}"
        assert upload_res.json()["total_contacts"] == 1

        # -- 6. Start Campaign --
        start_res = client.post(f"/api/campaigns/{campaign_id}/start")
        assert start_res.status_code == 200
        assert start_res.json()["status"] == "started"

        # -- 7. Simulate a completed call --
        # The ARQ worker is not running during tests, so we directly insert a
        # completed call row using synchronous psycopg2 (no asyncio conflicts).
        me_res = client.get("/api/auth/me")
        assert me_res.status_code == 200
        tenant_id = me_res.json()["tenant_id"]

        fake_call_id = f"CA_fake_onboarding_{uuid.uuid4()}"
        _sync_insert_call(tenant_id, agent_id, fake_call_id)

        # -- 8. Verify Dashboard Analytics Populated --
        analytics_res = client.get("/api/analytics")
        assert analytics_res.status_code == 200
        data = analytics_res.json()
        assert data["total_calls"] > 0, "Dashboard should reflect the newly completed call"
        assert data["avg_duration"] == 45
        assert data["outcomes"]["booked"] == 1
