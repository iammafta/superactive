import pytest
import os
import uuid
import asyncio

# Point POSTGRES settings to an alternative DB or just the local one for testing
# Note: In a real CI, we'd use a separate test DB.
os.environ["POSTGRES_DB"] = "superactive" 

from db import (
    init_db, get_pool,
    db_create_tenant, db_get_tenant,
    db_create_user, db_get_user_by_email,
    db_save_agent, db_load_agent, db_list_agents,
    db_save_campaign, db_load_campaign, db_list_campaigns,
    db_save_contacts, db_get_contacts,
    db_persist_call, db_get_calls
)

import pytest_asyncio
@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_database():
    """Ensure database schema is initialized before tests run."""
    await init_db()
    yield
    # We could theoretically drop tables here, but we'll leave them for now
    pool = await get_pool()
    if pool:
        await pool.close()
    import db
    db._pool = None

@pytest.fixture
def unique_tenant_id():
    return str(uuid.uuid4())

@pytest.mark.asyncio
async def test_tenant_crud(unique_tenant_id):
    # Create
    email = f"test_{unique_tenant_id}@example.com"
    tenant = await db_create_tenant(f"Test Tenant {unique_tenant_id}", email)
    assert tenant["email"] == email
    
    # Get
    fetched = await db_get_tenant(tenant["id"])
    assert fetched["id"] == tenant["id"]
    assert fetched["name"] == f"Test Tenant {unique_tenant_id}"

@pytest.mark.asyncio
async def test_user_crud():
    tenant = await db_create_tenant(f"User Test {uuid.uuid4()}", f"user_test_{uuid.uuid4()}@example.com")
    tenant_id = tenant["id"]
    
    email = f"user_{uuid.uuid4()}@example.com"
    user = await db_create_user(email, "hashed_password", tenant_id, "admin")
    
    fetched = await db_get_user_by_email(email)
    assert fetched["id"] == user["id"]
    assert fetched["tenant_id"] == tenant_id
    assert fetched["role"] == "admin"

@pytest.mark.asyncio
async def test_agent_tenant_isolation():
    tenant1 = await db_create_tenant("Tenant 1", f"t1_{uuid.uuid4()}@ex.com")
    tenant2 = await db_create_tenant("Tenant 2", f"t2_{uuid.uuid4()}@ex.com")
    
    agent_id_1 = str(uuid.uuid4())
    agent_id_2 = str(uuid.uuid4())
    
    # Same IDs but different tenants (should be prevented by PK, but let's test different IDs first)
    agent1 = {
        "id": agent_id_1,
        "name": "Agent 1",
        "business_type": "Test",
        "system_prompt": "You are a test agent."
    }
    
    agent2 = {
        "id": agent_id_2,
        "name": "Agent 2",
        "business_type": "Test",
        "system_prompt": "You are a test agent."
    }
    
    await db_save_agent(agent1, tenant1["id"])
    await db_save_agent(agent2, tenant2["id"])
    
    # List agents for tenant 1 should NOT include tenant 2's agent
    t1_agents = await db_list_agents(tenant1["id"])
    assert len(t1_agents) == 1
    assert t1_agents[0]["id"] == agent_id_1
    
    t2_agents = await db_list_agents(tenant2["id"])
    assert len(t2_agents) == 1
    assert t2_agents[0]["id"] == agent_id_2

@pytest.mark.asyncio
async def test_campaign_and_contacts():
    tenant = await db_create_tenant("Camp Test", f"camp_{uuid.uuid4()}@ex.com")
    agent_id = str(uuid.uuid4())
    
    await db_save_agent({
        "id": agent_id,
        "name": "Agent for Campaign",
        "business_type": "Test",
        "system_prompt": "Prompt"
    }, tenant["id"])
    
    camp_id = str(uuid.uuid4())
    campaign = {
        "id": camp_id,
        "name": "Test Campaign",
        "agent_id": agent_id
    }
    
    await db_save_campaign(campaign, tenant["id"])
    
    contacts = [
        {"phone": "+1234567890", "name": "Alice"},
        {"phone": "+0987654321", "name": "Bob"}
    ]
    
    count = await db_save_contacts(camp_id, contacts)
    assert count == 2
    
    fetched = await db_load_campaign(camp_id, tenant["id"])
    assert fetched["name"] == "Test Campaign"
    assert len(fetched["contacts"]) == 2
    assert fetched["contacts"][0]["phone"] == "+1234567890"

@pytest.mark.asyncio
async def test_jsonb_parsing():
    tenant = await db_create_tenant("JSONB Test", f"jsonb_{uuid.uuid4()}@ex.com")
    agent_id = str(uuid.uuid4())
    
    agent = {
        "id": agent_id,
        "name": "Agent JSONB",
        "business_type": "Test",
        "system_prompt": "Prompt",
        "allowed_tools": ["tool1", "tool2"],
        "states": [{"name": "state1", "actions": ["do_something"]}],
        "webhook_headers": {"Authorization": "Bearer Token"}
    }
    
    await db_save_agent(agent, tenant["id"])
    
    fetched = await db_load_agent(agent_id, tenant["id"])
    
    # Test that JSON fields are properly parsed back into lists/dicts, not returned as raw strings
    assert isinstance(fetched["allowed_tools"], list)
    assert fetched["allowed_tools"] == ["tool1", "tool2"]
    
    assert isinstance(fetched["states"], list)
    assert fetched["states"][0]["actions"] == ["do_something"]
    
    assert isinstance(fetched["webhook_headers"], dict)
    assert fetched["webhook_headers"]["Authorization"] == "Bearer Token"
