"""
Superactive — Agent CRUD Routes
"""

from fastapi import APIRouter, HTTPException, Depends
from loguru import logger

from agent_config import (
    AgentConfig, load_agent, save_agent, list_agents, delete_agent
)
from auth import get_current_user, UserContext
from tool_registry import TOOL_DEFINITIONS

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
async def api_list_agents(user: UserContext = Depends(get_current_user)):
    """List all agents for the current tenant."""
    agents = await list_agents(user.tenant_id)
    return [a.model_dump() for a in agents]


@router.get("/tools")
async def api_list_tools(user: UserContext = Depends(get_current_user)):
    """List all available tools (for dashboard tool picker)."""
    return {
        name: {
            "name": name,
            "description": defn["description"],
            "parameters": list(defn["parameters"]["properties"].keys()),
        }
        for name, defn in TOOL_DEFINITIONS.items()
    }


@router.get("/{agent_id}")
async def api_get_agent(agent_id: str, user: UserContext = Depends(get_current_user)):
    """Get a specific agent config."""
    agent = await load_agent(agent_id, user.tenant_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.model_dump()


@router.post("")
async def api_create_agent(config: AgentConfig, user: UserContext = Depends(get_current_user)):
    """Create a new agent config."""
    # Ensure tenant matches user (override if sent)
    config.tenant_id = user.tenant_id
    
    # Check if ID exists within this tenant (or globally if we enforce global uniqueness)
    # db_save_agent handles upsert, but for POST we might want to check existence?
    # For simplicity, we'll allow overwrite or handled by logic. 
    # But usually POST should fail if exists.
    existing = await load_agent(config.id, user.tenant_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Agent '{config.id}' already exists")

    if await save_agent(config, user.tenant_id):
        return {"status": "created", "id": config.id}
    raise HTTPException(status_code=500, detail="Failed to save agent config")


@router.put("/{agent_id}")
async def api_update_agent(agent_id: str, config: AgentConfig, user: UserContext = Depends(get_current_user)):
    """Update an agent config."""
    config.id = agent_id
    config.tenant_id = user.tenant_id
    
    # Ensure it exists and belongs to user
    existing = await load_agent(agent_id, user.tenant_id)
    if not existing:
         raise HTTPException(status_code=404, detail="Agent not found")

    if await save_agent(config, user.tenant_id):
        return {"status": "updated", "id": agent_id}
    raise HTTPException(status_code=500, detail="Failed to update agent config")


@router.delete("/{agent_id}")
async def api_delete_agent(agent_id: str, user: UserContext = Depends(get_current_user)):
    """Delete an agent config."""
    if await delete_agent(agent_id, user.tenant_id):
        return {"status": "deleted", "id": agent_id}
    raise HTTPException(status_code=404, detail="Agent not found")


