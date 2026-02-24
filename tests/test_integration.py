import pytest
import os
import uuid
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup environment for testing integration
os.environ["POSTGRES_DB"] = "superactive"

# ── Fixtures ──────────────────────────────────────────────────────────
@pytest.fixture
def app():
    from server import app
    app.state.limiter.enabled = False
    return app

@pytest.fixture
def client(app):
    """A standard client that is not authenticated."""
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c

@pytest.fixture
def auth_client(client):
    """A client that is registered, logged in, and holds the HttpOnly cookie."""
    unique_id = str(uuid.uuid4())
    # 1. Register
    reg_res = client.post("/api/auth/register", json={
        "email": f"test_{unique_id}@integration.com",
        "password": "SecurePassword123!",
        "business_name": f"Integration Corp {unique_id}"
    })
    assert reg_res.status_code == 200, f"Register failed: {reg_res.text}"
    
    # Cookie is now stored in client.cookies automatically
    return client

# ── 1. Auth Flow Integration ─────────────────────────────────────────

class TestIntegrationAuth:
    """End-to-end tests for the full authentication lifecycle over HTTP + DB."""

    def test_full_auth_lifecycle(self, client):
        unique_id = str(uuid.uuid4())
        email = f"auth_{unique_id}@integration.com"
        password = "SecurePassword123!"
        
        # 1. Register
        reg_res = client.post("/api/auth/register", json={
            "email": email,
            "password": password,
            "business_name": "Test Auth Flow Inc"
        })
        assert reg_res.status_code == 200
        assert "token" in reg_res.json()
        
        # 2. Login
        login_res = client.post("/api/auth/login", json={
            "email": email,
            "password": password
        })
        assert login_res.status_code == 200
        
        # 3. Profile Fetch (using HttpOnly cookie automatically appended by TestClient)
        me_res = client.get("/api/auth/me")
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["email"] == email
        assert "tenant_id" in me_data
        
        # 4. Logout
        logout_res = client.post("/api/auth/logout")
        assert logout_res.status_code == 200
        
        # 5. Profile Fetch again (should be rejected since cookie was cleared)
        me_res_after_logout = client.get("/api/auth/me")
        assert me_res_after_logout.status_code == 401


# ── 2. Agent CRUD Integration ────────────────────────────────────────

class TestIntegrationAgentCRUD:
    """End-to-end tests for agent management over HTTP + DB."""
    
    def test_agent_lifecycle(self, auth_client):
        # 1. Create Agent
        create_res = auth_client.post("/api/agents", json={
            "name": "E2E Test Agent",
            "business_type": "Integration Testing",
            "system_prompt": "You are verifying system behavior.",
            "language": "en",
            "voice_prompt": "Friendly",
            "voice_id": "test_voice",
            "allowed_tools": []
        })
        assert create_res.status_code == 200, create_res.text
        agent_id = create_res.json()["id"]
        
        # 2. List Agents (Read)
        list_res = auth_client.get("/api/agents")
        assert list_res.status_code == 200
        agents = list_res.json()
        assert any(a["id"] == agent_id for a in agents)
        
        # 3. Update Agent
        update_res = auth_client.put(f"/api/agents/{agent_id}", json={
            "name": "E2E Test Agent V2",
            "business_type": "Integration Testing Updated",
            "system_prompt": "You are verifying system behavior.",
            "language": "en",
            "voice_prompt": "Friendly",
            "voice_id": "test_voice",
            "allowed_tools": ["appointment_booking"]
        })
        assert update_res.status_code == 200
        
        # 4. Read to Verify Update
        read_res = auth_client.get(f"/api/agents/{agent_id}")
        assert read_res.status_code == 200
        assert read_res.json()["name"] == "E2E Test Agent V2"
        assert "appointment_booking" in read_res.json()["allowed_tools"]
        
        # 5. Delete Agent
        del_res = auth_client.delete(f"/api/agents/{agent_id}")
        assert del_res.status_code == 200
        
        # 6. List Agents (Verify Deletion)
        list_res2 = auth_client.get("/api/agents")
        assert not any(a["id"] == agent_id for a in list_res2.json())


# ── 3. Campaign Lifecycle Integration ────────────────────────────────

class TestIntegrationCampaign:
    """End-to-end tests for campaigns (creation, CSV contacts, start/pause)."""

    def test_campaign_lifecycle(self, auth_client):
        # Pre-requisite: Create Agent
        create_agent_res = auth_client.post("/api/agents", json={
            "name": "Campaign Bot",
            "business_type": "Outbound",
            "system_prompt": "Dialing out.",
            "language": "en",
            "voice_prompt": "Professional",
            "voice_id": "outbound_voice",
            "allowed_tools": []
        })
        assert create_agent_res.status_code == 200
        agent_id = create_agent_res.json()["id"]

        # 1. Create Campaign
        create_camp_res = auth_client.post("/api/campaigns", json={
            "name": "E2E Marketing Campaign",
            "agent_id": agent_id,
            "max_concurrent_calls": 5
        })
        assert create_camp_res.status_code == 200, create_camp_res.text
        campaign_id = create_camp_res.json()["id"]
        
        # 2. Upload Contacts
        csv_content = "name,phone\nAlice,+1234567890\nBob,+1987654321\n"
        upload_res = auth_client.post(
            f"/api/campaigns/{campaign_id}/upload-contacts",
            files={"file": ("in.csv", csv_content, "text/csv")}
        )
        assert upload_res.status_code == 200, upload_res.text
        assert upload_res.json()["total_contacts"] == 2
        
        # 3. List Campaigns to Verify Default Status
        list_res = auth_client.get("/api/campaigns")
        assert list_res.status_code == 200
        campaigns = list_res.json()
        target_camp = next(c for c in campaigns if c["id"] == campaign_id)
        assert target_camp["status"] == "draft"
        assert target_camp["total_contacts"] == 2
        
        # 4. Start Campaign
        start_res = auth_client.post(f"/api/campaigns/{campaign_id}/start")
        assert start_res.status_code == 200
        assert start_res.json()["status"] == "started"
        
        # 4.5 Wait for worker to process queue
        import time
        print("Waiting 10s for background worker...")
        time.sleep(10)
        
        # Check actual contact statuses via the existing /api/campaigns/{id} endpoint
        campaign_check_res = auth_client.get(f"/api/campaigns/{campaign_id}")
        assert campaign_check_res.status_code == 200
        camp_data = campaign_check_res.json()
        contacts = camp_data.get("contacts", [])
        
        assert len(contacts) == 2, f"Found {len(contacts)} contacts"
        for c in contacts:
            assert c["status"] == "called", f"Worker failed to process queue. Contact status left as {c.get('status')}"
            assert c["call_sid"] and c["call_sid"].startswith("CA_mock_"), "Call SID not correctly assigned"
        
        print("Worker successfully executed dial tasks!")
        
        # 5. Pause Campaign
        pause_res = auth_client.post(f"/api/campaigns/{campaign_id}/pause")
        assert pause_res.status_code == 200
        assert pause_res.json()["status"] == "paused"
