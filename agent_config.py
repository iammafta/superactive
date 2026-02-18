"""
Superactive — Agent Configuration System

Pydantic models for config-driven agents. Each business gets their own
agent config (JSON) that controls persona, guardrails, tools, and state flow.
"""

import json
import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from loguru import logger


AGENTS_DIR = Path(__file__).parent / "agents"


# ── State Machine Config ──────────────────────────────────────────────

class StateConfig(BaseModel):
    """Single state in the conversation flow."""
    name: str                                    # "greeting", "qualifying", "booking"
    instructions: str                            # LLM instructions for this state
    transitions: dict[str, str] = Field(         # {"qualified": "booking", "frustrated": "escalation"}
        default_factory=dict
    )
    max_turns: int = 5                           # Per-state turn limit
    required_info: list[str] = Field(            # Info to collect in this state
        default_factory=list                     # e.g. ["name", "phone", "reason"]
    )


# ── Agent Config ──────────────────────────────────────────────────────

class AgentConfig(BaseModel):
    """Full agent configuration — one per business use case."""

    # Identity
    id: str                                      # "dr_smith_reception"
    name: str                                    # "Dr. Smith's Receptionist"
    business_type: str                           # "medical" | "restaurant" | "insurance"

    # Persona
    system_prompt: str                           # Full persona + business rules
    greeting: str = "Hello, how can I help you today?"
    voice_id: str = "en-US-Chirp3-HD-Charon"     # TTS voice

    # Guardrails (0.0 = free talk, 1.0 = strict script)
    guardrail_level: float = Field(default=0.5, ge=0.0, le=1.0)

    # Tools
    allowed_tools: list[str] = Field(            # ["book_appointment", "send_sms"]
        default_factory=list
    )

    # Business data hooks
    webhook_url: Optional[str] = None            # Client's custom API endpoint
    webhook_headers: dict[str, str] = Field(     # Auth headers for webhook
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

    def build_full_prompt(self, current_state: Optional[str] = None) -> str:
        """Build the complete system prompt with guardrail and state context."""
        parts = [self.system_prompt]
        
        # Inject context
        from datetime import datetime
        parts.append(f"\nCurrent Date: {datetime.now().strftime('%Y-%m-%d')}")
        
        parts.append(f"\n\n## Guardrails\n{self.get_guardrail_instruction()}")

        if self.escalation_triggers:
            triggers = ", ".join(f'"{t}"' for t in self.escalation_triggers)
            parts.append(
                f"\n\n## Escalation\nIf the caller says anything like {triggers}, "
                "immediately offer to transfer them to a human representative."
            )

        if current_state and self.states:
            state_cfg = next((s for s in self.states if s.name == current_state), None)
            if state_cfg:
                parts.append(f"\n\n## Current State: {state_cfg.name}\n{state_cfg.instructions}")
                if state_cfg.required_info:
                    info = ", ".join(state_cfg.required_info)
                    parts.append(f"\nYou need to collect: {info}")
                
                # Dynamic transition instructions
                if state_cfg.transitions:
                    trans_list = []
                    for event, next_state in state_cfg.transitions.items():
                        trans_list.append(f"- If {event}: Output [TRANSITION: {next_state}]")
                    parts.append("\n\n## Transitions\n" + "\n".join(trans_list))
                    parts.append("\nIMPORTANT: To move to the next state, you MUST output the transition tag exactly as shown.")
                else:
                    # Terminal state
                    parts.append("\n\n## Ending the Call\nIf the conversation is finished, output [HANGUP].")
                    
        return "\n".join(parts)


# ── CRUD Operations ──────────────────────────────────────────────────

def _ensure_agents_dir():
    """Create agents directory if it doesn't exist."""
    AGENTS_DIR.mkdir(exist_ok=True)


def load_agent(agent_id: str) -> Optional[AgentConfig]:
    """Load an agent config from JSON file."""
    path = AGENTS_DIR / f"{agent_id}.json"
    if not path.exists():
        logger.warning(f"Agent config not found: {agent_id}")
        return None
    try:
        data = json.loads(path.read_text())
        return AgentConfig(**data)
    except Exception as e:
        logger.error(f"Failed to load agent {agent_id}: {e}")
        return None


def save_agent(config: AgentConfig) -> bool:
    """Save an agent config to JSON file."""
    _ensure_agents_dir()
    path = AGENTS_DIR / f"{config.id}.json"
    try:
        path.write_text(config.model_dump_json(indent=2))
        logger.info(f"Saved agent config: {config.id}")
        return True
    except Exception as e:
        logger.error(f"Failed to save agent {config.id}: {e}")
        return False


def list_agents() -> list[AgentConfig]:
    """List all available agent configs."""
    _ensure_agents_dir()
    agents = []
    for path in AGENTS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            agents.append(AgentConfig(**data))
        except Exception as e:
            logger.error(f"Failed to load {path.name}: {e}")
    return agents


def delete_agent(agent_id: str) -> bool:
    """Delete an agent config."""
    path = AGENTS_DIR / f"{agent_id}.json"
    if path.exists():
        path.unlink()
        logger.info(f"Deleted agent config: {agent_id}")
        return True
    return False


def get_default_agent() -> AgentConfig:
    """Return a default agent config when no specific one is requested."""
    agents = list_agents()
    
    # Prefer debug_chat if available
    debug_agent = next((a for a in agents if a.id == "debug_chat"), None)
    if debug_agent:
        return debug_agent
        
    if agents:
        return agents[0]

    # Fallback — the original Sarah persona
    return load_agent("debug_chat") or AgentConfig(
        id="debug_chat",
        name="Debug Chat Agent",
        business_type="debug",
        system_prompt=(
            "You are the Debug Chat Agent. You have access to a 'google_search' tool. "
            "IMPORTANT: This tool is POWERFUL. It uses Tavily and Google under the hood. "
            "Use 'google_search' for: "
            "1. Real-time news (e.g. 'Who won the game?') "
            "2. Company data (e.g. 'Funding rounds for Anthropic') "
            "3. Fact checking (e.g. 'Who is president?') "
            "Do NOT say 'I only have google search'. Just USE the tool for any search request. "
            "You are helpful, knowledgeable, and ready to test system capabilities."
        ),
        greeting="Hello, I am the Debug Chat Agent. Ask me anything!",
        guardrail_level=0.0,
        allowed_tools=["google_search"],
    )

