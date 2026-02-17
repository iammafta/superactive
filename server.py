"""
Superactive — AI Voice Agent Server
Phase 3: Configurable Agent Platform

Config-driven agents with tool calling, state machine, and call logging.
Dashboard API endpoints for agent CRUD, call history, and analytics.
"""

import os
import sys
import uuid
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
logger.remove()
logger.add(sys.stderr, level="DEBUG")

# Pipecat logging (INFO level — DEBUG floods the event loop)
import logging
logging.basicConfig(level=logging.INFO)
from pydantic import BaseModel

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import EndFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.runner.utils import parse_telephony_websocket
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.google.llm_vertex import GoogleVertexLLMService
from pipecat.services.google.stt import GoogleSTTService
from pipecat.services.google.tts import GoogleHttpTTSService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from agent_config import (
    AgentConfig, load_agent, save_agent, list_agents, delete_agent, get_default_agent,
)
from tool_registry import get_tools_for_agent, register_tools_for_agent
from state_machine import StateMachineProcessor, StateTransitionFilter
from call_logger import call_logger

app = FastAPI(title="Superactive", version="3.0")

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Lock down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Config from .env
PORT = int(os.getenv("PORT", 8765))
CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
GCP_PROJECT = os.getenv("GCP_PROJECT_ID", "divine-apogee-480205-h8")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")


# ══════════════════════════════════════════════════════════════════════
#  HEALTH & TELEPHONY
# ══════════════════════════════════════════════════════════════════════

@app.get("/")
async def health():
    return {"status": "ok", "service": "Superactive", "phase": 3}


@app.api_route("/incoming-call", methods=["GET", "POST"])
async def incoming_call(request: Request):
    """Handle incoming Twilio call — return TwiML to connect to WebSocket.
    Passes agent_id via custom parameters if specified."""
    host = request.headers.get("host", "localhost:8765")
    print(f"DEBUG: Incoming call request from {host}")
    logger.info(f"DEBUG: Incoming call request from {host}")

    # Check for agent_id in query params (for outbound calls)
    agent_id = request.query_params.get("agent_id", "")
    custom_params = f'<Parameter name="agent_id" value="{agent_id}" />' if agent_id else ""

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="wss://{host}/media-stream">
            {custom_params}
        </Stream>
    </Connect>
</Response>"""
    return HTMLResponse(content=twiml, media_type="application/xml")


@app.websocket("/media-stream")
async def websocket_endpoint(websocket: WebSocket):
    """Handle the WebSocket connection from Twilio Media Streams."""
    await websocket.accept()
    logger.info("🔌 Twilio WebSocket connected")

    # 1a. Parse the Twilio handshake to get stream_sid + call_sid
    _transport_type, call_data = await parse_telephony_websocket(websocket)
    stream_sid = call_data["stream_id"]
    call_sid = call_data.get("call_id", str(uuid.uuid4()))
    logger.info(f"📞 Twilio stream={stream_sid} call={call_sid}")

    # 1b. Determine which agent config to use
    # Pipecat puts Twilio's customParameters under "body"
    custom_params = call_data.get("body", {})
    agent_id = custom_params.get("agent_id", None)
    logger.info(f"🔍 Custom params from Twilio: {custom_params} → agent_id={agent_id}")

    if agent_id:
        agent_config = load_agent(agent_id)
        if not agent_config:
            logger.warning(f"Agent {agent_id} not found, using default")
            agent_config = get_default_agent()
    else:
        agent_config = get_default_agent()

    logger.info(f"🤖 Using agent: {agent_config.name} ({agent_config.id}) | "
                f"Guardrail: {agent_config.guardrail_level}")

    # Start call logging
    call_logger.start_call(call_sid, agent_config.id, agent_config.business_type)

    # 2. Transport — handles Twilio's µ-law audio format
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_enabled=False,
            serializer=TwilioFrameSerializer(
                stream_sid=stream_sid,
                call_sid=call_sid,
                account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
                auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
                params=TwilioFrameSerializer.InputParams(auto_hang_up=True),
            ),
        ),
    )

    # 3. STT — Google Cloud Speech-to-Text
    stt = GoogleSTTService(
        credentials_path=CREDENTIALS_PATH,
        location="global",
    )

    # 4. LLM — Gemini via Vertex AI (with config-driven prompt and tools)
    tools = get_tools_for_agent(agent_config)
    full_prompt = agent_config.build_full_prompt(
        current_state=agent_config.states[0].name if agent_config.states else None
    )

    llm = GoogleVertexLLMService(
        credentials_path=CREDENTIALS_PATH,
        project_id=GCP_PROJECT,
        location=GCP_LOCATION,
        model="gemini-2.0-flash",
        system_instruction=full_prompt,
        tools=[{"function_declarations": tools}] if tools else None,
    )

    # Register tool handlers (only the ones this agent is allowed to use)
    register_tools_for_agent(llm, agent_config)

    # 5. TTS — Google Cloud Text-to-Speech
    tts = GoogleHttpTTSService(
        credentials_path=CREDENTIALS_PATH,
        voice_id=agent_config.voice_id,
    )

    # 6. Conversation context — using OpenAILLMContext (proven working pattern)
    # The system prompt is in llm.system_instruction, messages start empty
    messages = []
    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

    # 7. State machine (if agent has states defined)
    state_processor = None
    transition_filter = None
    if agent_config.states:
        state_processor = StateMachineProcessor(agent_config)
        transition_filter = StateTransitionFilter(state_processor)

    # 8. Build pipeline
    pipeline_components = [
        transport.input(),           # Twilio audio in
        stt,                         # Speech → Text
    ]

    if state_processor:
        pipeline_components.append(state_processor)  # State-aware context injection

    pipeline_components.extend([
        context_aggregator.user(),   # Accumulate user speech
        llm,                         # Text → AI Response
    ])

    if transition_filter:
        pipeline_components.append(transition_filter)

    pipeline_components.extend([
        tts,                         # AI Response → Speech
        transport.output(),          # Speech → Twilio audio out
        context_aggregator.assistant(),  # Store assistant response
    ])

    pipeline = Pipeline(pipeline_components)

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    # Kick off the conversation with the agent's greeting
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("📞 Call connected — sending greeting")
        logger.info(f"📝 Agent greeting: {agent_config.greeting}")

        # Push greeting directly to TTS (bypasses LLM, avoids tool format issues).
        # append_to_context=True ensures the LLM knows it said the greeting.
        await task.queue_frames([
            TTSSpeakFrame(text=agent_config.greeting, append_to_context=True)
        ])
        logger.info("✅ Greeting queued for TTS")

        if state_processor:
            call_logger.record_state_transition(
                call_sid, "start", state_processor.current_state or "greeting", 0
            )

    runner = PipelineRunner()

    try:
        await runner.run(task)
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
    finally:
        # End call logging
        outcome = "completed"
        hang_up_state = None
        if state_processor:
            info = state_processor.get_state_info()
            hang_up_state = info.get("current_state")
            if info["turn_count"] < 3:
                outcome = "hung_up"
        await call_logger.end_call(call_sid, outcome=outcome, hang_up_state=hang_up_state)
        logger.info("📞 Call ended")


# ══════════════════════════════════════════════════════════════════════
#  AGENT CRUD API (for dashboard)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/agents")
async def api_list_agents():
    """List all agent configs."""
    agents = list_agents()
    return [a.model_dump() for a in agents]


@app.get("/api/agents/{agent_id}")
async def api_get_agent(agent_id: str):
    """Get a specific agent config."""
    agent = load_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return agent.model_dump()


@app.post("/api/agents")
async def api_create_agent(config: AgentConfig):
    """Create a new agent config."""
    existing = load_agent(config.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Agent '{config.id}' already exists")
    if save_agent(config):
        return {"status": "created", "id": config.id}
    raise HTTPException(status_code=500, detail="Failed to save agent config")


@app.put("/api/agents/{agent_id}")
async def api_update_agent(agent_id: str, config: AgentConfig):
    """Update an agent config."""
    config.id = agent_id  # Ensure ID matches URL
    if save_agent(config):
        return {"status": "updated", "id": agent_id}
    raise HTTPException(status_code=500, detail="Failed to update agent config")


@app.delete("/api/agents/{agent_id}")
async def api_delete_agent(agent_id: str):
    """Delete an agent config."""
    if delete_agent(agent_id):
        return {"status": "deleted", "id": agent_id}
    raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")


# ══════════════════════════════════════════════════════════════════════
#  CALL HISTORY & ANALYTICS API
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/calls")
async def api_get_calls(
    days: int = Query(default=7, ge=1, le=90),
    agent_id: Optional[str] = None,
    business_type: Optional[str] = None,
):
    """Get call history."""
    calls = await call_logger.get_calls(days=days, agent_id=agent_id, business_type=business_type)
    return [c.model_dump() for c in calls]


@app.get("/api/calls/active")
async def api_get_active_calls():
    """Get currently active calls (for live dashboard)."""
    return call_logger.get_active_calls()


@app.get("/api/analytics")
async def api_get_analytics(days: int = Query(default=30, ge=1, le=365)):
    """Get aggregated analytics."""
    return await call_logger.get_analytics(days=days)


# ══════════════════════════════════════════════════════════════════════
#  OUTBOUND CALLS
# ══════════════════════════════════════════════════════════════════════

class OutboundCallRequest(BaseModel):
    to: str                  # Phone number to call
    agent_id: str            # Which agent config to use


@app.post("/api/outbound-call")
async def api_outbound_call(req: OutboundCallRequest):
    """Trigger an outbound call using a specific agent."""
    # Verify agent exists
    agent = load_agent(req.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{req.agent_id}' not found")

    try:
        from twilio.rest import Client
        client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN"),
        )

        # Get the public URL for the webhook
        # In production, this comes from config; locally, ngrok URL
        host = os.getenv("PUBLIC_URL", f"https://localhost:{PORT}")

        from_number = os.getenv("TWILIO_PHONE_NUMBER", "")
        # Ensure E.164 format
        if not from_number.startswith("+"):
            from_number = f"+{from_number}"

        call = client.calls.create(
            to=req.to,
            from_=from_number,
            url=f"{host}/incoming-call?agent_id={req.agent_id}",
        )

        logger.info(f"📤 Outbound call initiated: {call.sid} → {req.to} (agent: {req.agent_id})")
        return {
            "status": "initiated",
            "call_sid": call.sid,
            "to": req.to,
            "agent_id": req.agent_id,
        }
    except Exception as e:
        logger.error(f"Outbound call failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ══════════════════════════════════════════════════════════════════════
#  TOOL DEFINITIONS API (for dashboard tool picker)
# ══════════════════════════════════════════════════════════════════════

@app.get("/api/tools")
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
