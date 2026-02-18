"""
Superactive — Agent CRUD Routes
"""

from fastapi import APIRouter, HTTPException

from agent_config import (
    AgentConfig, load_agent, save_agent, list_agents, delete_agent,
)

router = APIRouter(prefix="/api", tags=["agents"])


@router.get("/agents")
async def api_list_agents():
    """List all agent configs."""
    agents = list_agents()
    return [a.model_dump() for a in agents]


@router.get("/agents/{agent_id}")
async def api_get_agent(agent_id: str):
    """Get a specific agent config."""
    agent = load_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent.model_dump()


@router.post("/agents")
async def api_create_agent(config: AgentConfig):
    """Create a new agent config."""
    existing = load_agent(config.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Agent '{config.id}' already exists")
    if save_agent(config):
        return {"status": "created", "id": config.id}
    raise HTTPException(status_code=500, detail="Failed to save agent config")


@router.put("/agents/{agent_id}")
async def api_update_agent(agent_id: str, config: AgentConfig):
    """Update an agent config."""
    config.id = agent_id  # Ensure ID matches URL
    if save_agent(config):
        return {"status": "updated", "id": agent_id}
    raise HTTPException(status_code=500, detail="Failed to update agent config")


@router.delete("/agents/{agent_id}")
async def api_delete_agent(agent_id: str):
    """Delete an agent config."""
    if delete_agent(agent_id):
        return {"status": "deleted", "id": agent_id}
    raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")


@router.get("/tools")
async def api_list_tools():
    """List all available tools (for dashboard tool picker)."""
    from tool_registry import TOOL_DEFINITIONS
    return {
        name: {
            "name": name,
            "description": defn["description"],
            "parameters": list(defn["parameters"]["properties"].keys()),
        }
        for name, defn in TOOL_DEFINITIONS.items()
    }
