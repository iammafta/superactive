import pytest
import os
import uuid
import sys
import asyncio
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["POSTGRES_DB"] = "superactive"

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
    """End-to-end user journey test: Registration -> Create Agent -> Test Call / Campaign -> Analytics."""

    def test_end_to_end_onboarding_flow(self, client):
        # ── 1. Register a new User ──
        unique_id = str(uuid.uuid4())
        email = f"new_user_{unique_id}@onboarding.com"
        password = "SecurePassword123!"

        reg_res = client.post("/api/auth/register", json={
            "email": email,
            "password": password,
            "business_name": "New Onboarding Co"
        })
        assert reg_res.status_code == 200, f"Register failed: {reg_res.text}"

        # ── 2. Login (sets HttpOnly cookie) ──
        login_res = client.post("/api/auth/login", json={
            "email": email,
            "password": password
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"

        # ── 3. Create an Agent ──
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

        # ── 4. Verify Dashboard Zero-State Analytics ──
        analytics_empty_res = client.get("/api/analytics")
        assert analytics_empty_res.status_code == 200
        empty_data = analytics_empty_res.json()
        assert empty_data["total_calls"] == 0, "Brand new user should have 0 total calls"
        
        # ── 5. Create a Campaign and Upload 1 Contact ──
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

        # ── 6. Start Campaign (Simulating action) ──
        start_res = client.post(f"/api/campaigns/{campaign_id}/start")
        assert start_res.status_code == 200
        assert start_res.json()["status"] == "started"

        # ── 7. Wait for worker to emulate taking the call ──
        print("Waiting 10s for the background worker to pick up the onboarding task...")
        time.sleep(10)

        # ── 8. Call Log Insertion / Analytics reflection ──
        # Since the worker just marks status as "called" and doesn't actually place a real
        # twilio call that generates a log row (the mock creates the actual call row),
        # we will directly simulate the webhook arriving to finalize a call to verify analytics.
        
        # Fetch profile for tenant ID
        me_res = client.get("/api/auth/me")
        tenant_id = me_res.json()["tenant_id"]

        # Simulate inbound webhook terminating a call
        db_mock_call_id = "CA_mock_" + str(uuid.uuid4())[:10]
        webhook_res = client.post("/api/telephony/status", data={
            "CallSid": db_mock_call_id,
            "CallStatus": "completed",
            "Duration": "45"
        })
        
        # Let's forcefully insert a finished call log to check analytics logic.
        import asyncpg
        
        async def insert_fake_call():
            dsn = f"postgres://{os.environ.get('POSTGRES_USER', 'superactive')}:{os.environ.get('POSTGRES_PASSWORD', 'superactive')}@{os.environ.get('POSTGRES_HOST', 'localhost')}:{os.environ.get('POSTGRES_PORT', '5432')}/{os.environ.get('POSTGRES_DB', 'superactive')}"
            conn = await asyncpg.connect(dsn)
            try:
                await conn.execute(
                    "INSERT INTO calls (call_id, tenant_id, agent_id, duration_seconds, outcome, status) VALUES ($1, $2, $3, 45, 'booked', 'completed') ON CONFLICT DO NOTHING",
                    f"CA_fake_onboarding_{uuid.uuid4()}", tenant_id, agent_id
                )
            finally:
                await conn.close()
        
        try:
             loop = asyncio.get_running_loop()
             loop.run_until_complete(insert_fake_call())
        except RuntimeError:
             asyncio.run(insert_fake_call())

        # ── 9. Verify Dashboard Analytics Polulated ──
        analytics_populated_res = client.get("/api/analytics")
        assert analytics_populated_res.status_code == 200
        populated_data = analytics_populated_res.json()
        assert populated_data["total_calls"] > 0, "Dashboard should reflect the newly completed call"
        assert populated_data["avg_duration"] == 45
        assert populated_data["outcomes"]["booked"] == 1
