"""
Superactive — Agent Configuration System

Pydantic models for config-driven agents.
Persisted in SQLite via db.py.
"""

import json
from typing import Optional
from pydantic import BaseModel, Field
from loguru import logger

# Import DB layer
from db import (
    db_load_agent,
    db_save_agent,
    db_list_agents,
    db_delete_agent
)

# ── State Machine Config ──────────────────────────────────────────────

class StateConfig(BaseModel):
    """Single state in the conversation flow."""
    name: str                                    # "greeting", "qualifying", "booking"
    instructions: str                            # LLM instructions for this state
    transitions: dict[str, str] = Field(         # {"qualified": "booking", "frustrated": "escalation"}
        default_factory=dict
    )
    max_turns: int = 5                           # Per-state turn limit
    required_info: list[dict] = Field(           # Info to collect: [{"name": "date", "description": "", "type": "string"}]
        default_factory=list
    )


# ── Agent Config ──────────────────────────────────────────────────────

import uuid

class AgentConfig(BaseModel):
    """Full agent configuration — one per business use case."""

    # Identity
    id: str = Field(default_factory=lambda: str(uuid.uuid4())) # Globally unique UUID or slug
    tenant_id: str = ""                          # Owner (injected by API route)
    name: str                                    # "Dr. Smith's Receptionist"
    business_type: str                           # "medical" | "restaurant" | "insurance"
    agent_type: str = Field(default="inbound", pattern="^(inbound|outbound|hybrid)$")  # Direction logic

    # Persona
    system_prompt: str                           # Full persona + business rules
    greeting: str = "Hello, how can I help you today?"
    outbound_greeting: str = ""                  # Greeting for outbound calls
    voice_id: str = "en-US-Chirp3-HD-Charon"     # TTS voice

    # Guardrails (0.0 = free talk, 1.0 = strict script)
    guardrail_level: float = Field(default=0.5, ge=0.0, le=1.0)
    frustration_tolerance: int = 1               # Number of frustration triggers before escalation
    loop_sensitivity: int = 2                    # Turns before forcing transition on repeated info

    # Tools
    allowed_tools: list[str] = Field(            # ["book_appointment", "send_sms"]
        default_factory=list
    )

    # Business data hooks
    webhook_url: Optional[str] = None            # Client's custom API endpoint
    webhook_headers: dict[str, str] = Field(     # Auth headers for webhook
        default_factory=dict
    )
    webhook_payload_mapping: dict[str, str] = Field( # Map state facts to custom JSON keys
        default_factory=dict
    )

    # State machine
    states: list[StateConfig] = Field(           # Conversation flow
        default_factory=list
    )

    # Limits
    max_turns: int = 20                          # Global turn limit
    max_duration_seconds: int = 300              # 5 min default

    # Escalation
    escalation_triggers: list[str] = Field(      # ["speak to manager", "human"]
        default_factory=lambda: ["speak to a human", "transfer me", "manager", "supervisor"]
    )

    # Metadata
    active: bool = True
    description: str = ""

    def get_guardrail_instruction(self) -> str:
        """Generate guardrail instruction based on level."""
        if self.guardrail_level >= 0.8:
            return (
                "STRICT MODE: Follow the conversation script exactly. Do NOT deviate from "
                "the defined states. Do NOT answer questions outside your scope. If the caller "
                "asks something off-topic, politely redirect to the current task."
            )
        elif self.guardrail_level >= 0.5:
            return (
                "GUIDED MODE: Follow the conversation flow but allow natural conversation. "
                "You may answer simple questions, but always steer back to the main goal. "
                "Do not help with anything unrelated to the business."
            )
        elif self.guardrail_level >= 0.2:
            return (
                "FLEXIBLE MODE: Have a natural conversation while working toward the goal. "
                "You can discuss related topics and be personable, but keep the business "
                "objective in mind."
            )
        else:
            return (
                "OPEN MODE: Have a free-flowing conversation. Be helpful and personable. "
                "You may assist with general inquiries while representing the business."
            )

    def build_full_prompt(self) -> str:
        """Build the system prompt with personality, guardrails, and flow rules."""
        parts = [self.system_prompt]

        from datetime import datetime
        parts.append(f"\nCurrent Date: {datetime.now().strftime('%Y-%m-%d')}")

        parts.append(f"\n\n## Guardrails\n{self.get_guardrail_instruction()}")

        if self.escalation_triggers:
            triggers = ", ".join(f'"{t}"' for t in self.escalation_triggers)
            parts.append(
                f"\n\n## Escalation\nIf the caller says anything like {triggers}, "
                "immediately offer to transfer them to a human representative."
            )

        if self.states:
            parts.append(
                "\n\n## Conversation Flow\n"
                "You are in a structured conversation with defined phases. "
                "During the conversation, you'll receive coaching notes in parentheses — "
                "these are your inner thoughts guiding the conversation naturally. Follow "
                "their guidance but never read them aloud or reference them to the caller.\n"
                "When a transition condition is met, output the transition tag "
                "EXACTLY as shown. Example: [TRANSITION: next_state]\n"
                "NEVER repeat a question the caller already answered. "
                "If they told you something, acknowledge it and move on to the NEXT question.\n"
                "Use brief acknowledgments like 'sure', 'got it', 'absolutely' to show you're listening."
            )

        parts.append(
            "\n\n## Call Conclusion\n"
            "When the conversation is completely finished and it is time to say goodbye, "
            "you MUST output the exact tag [HANGUP] to terminate the call."
        )

        return "\n".join(parts)


# ── CRUD Operations (Async + DB) ─────────────────────────────────────

async def load_agent(agent_id: str, tenant_id: str = None) -> Optional[AgentConfig]:
    """Load an agent config from DB.
    
    If tenant_id is provided, ensures ownership.
    If tenant_id is None (telephony), finds by ID (assumes valid global ID).
    """
    data = await db_load_agent(agent_id, tenant_id)
    if not data:
        return None
    try:
        return AgentConfig(**data)
    except Exception as e:
        logger.error(f"Failed to parse agent {agent_id}: {e}")
        return None


async def save_agent(config: AgentConfig, tenant_id: str) -> bool:
    """Save an agent config to DB."""
    # Enforce tenant ownership
    if config.tenant_id != tenant_id:
        logger.error(f"Tenant mismatch: {config.tenant_id} != {tenant_id}")
        return False
        
    return await db_save_agent(config.model_dump(), tenant_id)


async def list_agents(tenant_id: str) -> list[AgentConfig]:
    """List all agents for a tenant."""
    rows = await db_list_agents(tenant_id)
    agents = []
    for row in rows:
        try:
            agents.append(AgentConfig(**row))
        except Exception as e:
            logger.error(f"Skipping invalid agent: {e}")
    return agents


async def delete_agent(agent_id: str, tenant_id: str) -> bool:
    """Delete an agent config."""
    return await db_delete_agent(agent_id, tenant_id)


async def get_default_agent() -> AgentConfig:
    """Return a default agent config when no specific one is requested.
    
    WARNING: usage of this without tenant context is dangerous in multi-tenant mode.
    Mainly for fallback/debug.
    """
    # This is tricky because we don't know the tenant.
    # We'll just try to load "debug_chat" from any tenant.
    agent = await load_agent("debug_chat")
    if agent:
        return agent

    # Fallback in-memory
    return AgentConfig(
        id="debug_chat",
        tenant_id="default",
        name="Debug Chat Agent",
        business_type="debug",
        system_prompt=(
            "You are the Debug Chat Agent. You have access to a 'google_search' tool. "
            "Use it for real-time data."
        ),
        greeting="Hello, I am the Debug Chat Agent.",
        guardrail_level=0.0,
        allowed_tools=["google_search"],
    )
