import os
import uuid
import sys
import asyncio
import time
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["POSTGRES_DB"] = "superactive"
os.environ["DISABLE_TELEMETRY"] = "1"

def test_worker_end_to_end():
    print("Importing server...")
    from server import app
    print("Server imported.")
    app.state.limiter.enabled = False
    
    unique_id = str(uuid.uuid4())
    
    print("Initializing TestClient...")
    with TestClient(app) as client:
        print("TestClient initialized.")
        # Register
        reg_res = client.post("/api/auth/register", json={
            "email": f"worker_test_{unique_id}@integration.com",
            "password": "SecurePassword123!",
            "business_name": f"Integration Corp {unique_id}"
        })
        assert reg_res.status_code == 200, f"Register failed: {reg_res.text}"

        # 1. Create Agent
        create_agent_res = client.post("/api/agents", json={
            "name": "Worker E2E Agent",
            "business_type": "Outbound",
            "system_prompt": "Dialing out.",
            "language": "en",
            "voice_prompt": "Professional",
            "voice_id": "outbound_voice",
            "allowed_tools": []
        })
        assert create_agent_res.status_code == 200
        agent_id = create_agent_res.json()["id"]

        # 2. Create Campaign
        create_camp_res = client.post("/api/campaigns", json={
            "name": "Worker E2E Campaign",
            "agent_id": agent_id,
            "max_concurrent_calls": 5
        })
        assert create_camp_res.status_code == 200, create_camp_res.text
        campaign_id = create_camp_res.json()["id"]
        
        # 3. Upload Contacts
        csv_content = "name,phone\nAlice,+1234567890\nBob,+1987654321\n"
        upload_res = client.post(
            f"/api/campaigns/{campaign_id}/upload-contacts",
            files={"file": ("in.csv", csv_content, "text/csv")}
        )
        assert upload_res.status_code == 200, upload_res.text
        
        # 4. Start Campaign
        start_res = client.post(f"/api/campaigns/{campaign_id}/start")
        assert start_res.status_code == 200

        # Wait
        print("Waiting 8 seconds for background worker to dial contacts...")
        time.sleep(8)
            
        # 6. Verify database reflects the updates performed by the worker
        progress_res = client.get(f"/api/campaigns/{campaign_id}/progress")
        assert progress_res.status_code == 200
        progress = progress_res.json()
        
    from db import db_get_contacts
    import db
    # We need async event loop to call db_get_contacts
    async def verify_contacts():
        contacts = await db_get_contacts(campaign_id)
        assert len(contacts) == 2
        for contact in contacts:
            assert contact["status"] == "called", f"Expected 'called', got {contact['status']}"
            assert contact["call_sid"] is not None
            assert contact["call_sid"].startswith("CA_mock_")
        print("========================================")
        print("Worker end-to-end verification successful!")
        print("========================================")
        
        # Cleanly close the pool created on this temporary event loop
        if db._pool:
            await db._pool.close()
            db._pool = None
        
    db._pool = None
    asyncio.run(verify_contacts())
    db._pool = None

if __name__ == "__main__":
    test_worker_end_to_end()
