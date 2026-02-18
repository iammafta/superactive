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
from pipecat.audio.vad.vad_analyzer import VADParams
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
from state_machine import (
    StateMachineProcessor, StateTransitionFilter,
    TranscriptLoggerProcessor, TranscriptLoggerFilter,
)
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
tavily_key = os.getenv("TAVILY_API_KEY")
print(f"DEBUG: Startup - Tavily Key Present: {bool(tavily_key)}")
if tavily_key:
    print(f"DEBUG: Tavily Key Prefix: {tavily_key[:8]}...")


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
    # Use PUBLIC_URL for the WebSocket endpoint — this must be the tunnel URL
    # that Twilio can reach, not the request's Host header (which varies)
    public_url = os.getenv("PUBLIC_URL", "")
    if public_url:
        # Convert https://... to wss://... for WebSocket
        ws_host = public_url.replace("https://", "").replace("http://", "").rstrip("/")
        ws_scheme = "wss" if "https" in public_url else "ws"
    else:
        ws_host = request.headers.get("host", "localhost:8765")
        ws_scheme = "wss"

    logger.info(f"📞 Incoming call webhook — WS target: {ws_scheme}://{ws_host}/media-stream")

    # Check for agent_id + outbound context in query params
    agent_id = request.query_params.get("agent_id", "")
    outbound = request.query_params.get("outbound", "")
    contact_name = request.query_params.get("contact_name", "")

    param_tags = []
    if agent_id:
        param_tags.append(f'<Parameter name="agent_id" value="{agent_id}" />')
    if outbound:
        param_tags.append(f'<Parameter name="outbound" value="{outbound}" />')
    if contact_name:
        param_tags.append(f'<Parameter name="contact_name" value="{contact_name}" />')
    custom_params = "\n            ".join(param_tags)

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_scheme}://{ws_host}/media-stream">
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
    is_outbound = custom_params.get("outbound", "") == "1"
    from urllib.parse import unquote
    contact_name = unquote(custom_params.get("contact_name", ""))
    logger.info(f"🔍 Custom params: {custom_params} → agent_id={agent_id} outbound={is_outbound} contact={contact_name}")

    if agent_id:
        agent_config = load_agent(agent_id)
        if not agent_config:
            logger.warning(f"Agent {agent_id} not found, using default")
            agent_config = get_default_agent()
    else:
        agent_config = get_default_agent()

    logger.info(f"🤖 Using agent: {agent_config.name} ({agent_config.id}) | "
                f"Guardrail: {agent_config.guardrail_level} | Outbound: {is_outbound}")

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

    # Outbound call context — inject awareness that WE called THEM
    outbound_greeting = agent_config.greeting  # default inbound greeting
    if is_outbound:
        who = contact_name or "there"
        biz = agent_config.business_type.replace("_", " ").title()
        outbound_greeting = (
            f"Hi {who}, this is {agent_config.name} calling from {biz}. "
            f"How are you today?"
        )
        full_prompt += (
            f"\n\n## OUTBOUND CALL CONTEXT\n"
            f"IMPORTANT: You are making an OUTBOUND call. YOU called the customer, "
            f"they did NOT call you. The customer's name is {who}. "
            f"Introduce yourself, explain why you're calling, and be respectful of their time. "
            f"If they say they didn't call or seem confused, clarify: 'I apologize for any confusion — "
            f"we're reaching out to you from {biz}.' "
            f"Never say 'thank you for calling' — YOU initiated this call."
        )
        logger.info(f"📤 Outbound mode: greeting='{outbound_greeting[:60]}...' contact={who}")

    llm = GoogleVertexLLMService(
        credentials_path=CREDENTIALS_PATH,
        project_id=GCP_PROJECT,
        location=GCP_LOCATION,
        model="gemini-2.0-flash",
        system_instruction=full_prompt,
        tools=[{"function_declarations": tools}] if tools else None,
    )

    # Register tool handlers (only the ones this agent is allowed to use)
    register_tools_for_agent(llm, agent_config, call_id=call_sid, call_logger=call_logger)

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

    # 7. State machine (if agent has states) or lightweight transcript loggers
    state_processor = None
    transition_filter = None
    if agent_config.states:
        state_processor = StateMachineProcessor(
            agent_config, call_id=call_sid, call_logger=call_logger
        )
        transition_filter = StateTransitionFilter(
            state_processor, call_id=call_sid, call_logger=call_logger
        )
    else:
        # Stateless agent — still log transcripts
        state_processor = TranscriptLoggerProcessor(
            call_id=call_sid, call_logger=call_logger
        )
        transition_filter = TranscriptLoggerFilter(
            call_id=call_sid, call_logger=call_logger
        )

    # 8. Build pipeline
    # 8. Build pipeline
    # NEW: VAD (Voice Activity Detection) - Back to Silero (WebRTC not in installed pipecat version)
    try:
        print("DEBUG: Initializing Silero VAD...")
        vad = SileroVADAnalyzer(
            params=VADParams(
                start_confidence=0.6,
                stop_duration=1.0,
                min_audio_duration=0.2,
            )
        )
        print("DEBUG: Silero VAD Initialized successfully")
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to init VAD: {e}")
        # Fallback to no VAD if it fails to avoid crash
        logger.error(f"VAD Init Failed, continuing without VAD: {e}")
        vad = None

    pipeline_components = [
        transport.input(),           # Twilio audio in
        stt,                         # Speech → Text
        state_processor,             # State-aware context (or transcript logger)
        context_aggregator.user(),   # Accumulate user speech
        llm,                         # Text → AI Response
        transition_filter,           # Strip tags + log agent speech
        tts,                         # AI Response → Speech
        transport.output(),          # Speech → Twilio audio out
        context_aggregator.assistant(),  # Store assistant response
    ]

    pipeline = Pipeline(pipeline_components)

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    # Kick off the conversation with the appropriate greeting
    greeting_text = outbound_greeting if is_outbound else agent_config.greeting

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"📞 Call connected ({'OUTBOUND' if is_outbound else 'INBOUND'}) — sending greeting")
        logger.info(f"📝 Greeting: {greeting_text}")

        # Push greeting directly to TTS (bypasses LLM, avoids tool format issues).
        # append_to_context=True ensures the LLM knows it said the greeting.
        await task.queue_frames([
            TTSSpeakFrame(text=greeting_text, append_to_context=True)
        ])
        logger.info("✅ Greeting queued for TTS")

        # Log initial state transition (only for stateful agents)
        if isinstance(state_processor, StateMachineProcessor):
            call_logger.record_state_transition(
                call_sid, "start", state_processor.current_state or "greeting", 0
            )

        # Log greeting as agent transcript
        call_logger.add_transcript(call_sid, "agent", greeting_text)

    runner = PipelineRunner()

    try:
        await runner.run(task)
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
    finally:
        # End call logging
        outcome = "completed"
        hang_up_state = None
        if isinstance(state_processor, StateMachineProcessor):
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
            url=f"{host}/incoming-call?agent_id={req.agent_id}&outbound=1",
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


# ══════════════════════════════════════════════════════════════════════
#  CAMPAIGN API
# ══════════════════════════════════════════════════════════════════════

from campaign_config import (
    CampaignConfig as CampaignModel,
    ContactRecord,
    load_campaign, save_campaign, list_campaigns, delete_campaign as delete_campaign_file,
)
from campaign_dialer import CampaignDialer, get_active_dialer

from fastapi import UploadFile, File as FastAPIFile
import csv
import io


@app.get("/api/campaigns")
async def api_list_campaigns():
    return [c.model_dump() for c in list_campaigns()]


@app.get("/api/campaigns/{campaign_id}")
async def api_get_campaign(campaign_id: str):
    campaign = load_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")
    return campaign.model_dump()


@app.post("/api/campaigns")
async def api_create_campaign(config: CampaignModel):
    existing = load_campaign(config.id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Campaign '{config.id}' already exists")
    if save_campaign(config):
        return {"status": "created", "id": config.id}
    raise HTTPException(status_code=500, detail="Failed to save campaign")


@app.put("/api/campaigns/{campaign_id}")
async def api_update_campaign(campaign_id: str, config: CampaignModel):
    config.id = campaign_id
    if save_campaign(config):
        return {"status": "updated", "id": campaign_id}
    raise HTTPException(status_code=500, detail="Failed to update campaign")


@app.delete("/api/campaigns/{campaign_id}")
async def api_delete_campaign(campaign_id: str):
    if delete_campaign_file(campaign_id):
        return {"status": "deleted", "id": campaign_id}
    raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")


@app.post("/api/campaigns/{campaign_id}/upload-contacts")
async def api_upload_contacts(campaign_id: str, file: UploadFile = FastAPIFile(...)):
    """Upload a CSV file of contacts. Expected columns: phone, name (+ optional extras)."""
    campaign = load_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")

    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    contacts = []
    for row in reader:
        phone = row.get("phone", "").strip()
        if not phone:
            continue
        name = row.get("name", "").strip()
        extra = {k: v for k, v in row.items() if k not in ("phone", "name")}
        contacts.append(ContactRecord(phone=phone, name=name, extra=extra))

    campaign.contacts = contacts
    campaign.total_contacts = len(contacts)
    campaign.called = 0
    campaign.booked = 0
    campaign.failed = 0
    save_campaign(campaign)

    return {"status": "uploaded", "total_contacts": len(contacts)}


@app.post("/api/campaigns/{campaign_id}/start")
async def api_start_campaign(campaign_id: str):
    campaign = load_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")
    if not campaign.contacts:
        raise HTTPException(status_code=400, detail="No contacts to dial")

    # Check agent exists
    agent = load_agent(campaign.agent_id)
    if not agent:
        raise HTTPException(status_code=400, detail=f"Agent '{campaign.agent_id}' not found")

    max_concurrent = (campaign.schedule or {}).get("max_concurrent", 3)
    dialer = CampaignDialer(campaign_id, max_concurrent=max_concurrent)
    dialer.start()

    return {"status": "started", "campaign_id": campaign_id, "total_contacts": campaign.total_contacts}


@app.post("/api/campaigns/{campaign_id}/pause")
async def api_pause_campaign(campaign_id: str):
    dialer = get_active_dialer(campaign_id)
    if not dialer:
        raise HTTPException(status_code=400, detail="Campaign is not actively dialing")
    dialer.pause()
    return {"status": "paused", "campaign_id": campaign_id}


@app.post("/api/campaigns/{campaign_id}/resume")
async def api_resume_campaign(campaign_id: str):
    dialer = get_active_dialer(campaign_id)
    if not dialer:
        raise HTTPException(status_code=400, detail="Campaign is not actively dialing")
    dialer.resume()
    return {"status": "resumed", "campaign_id": campaign_id}


@app.post("/api/campaigns/{campaign_id}/reset")
async def api_reset_campaign(campaign_id: str):
    """Reset a completed/paused campaign back to draft with all contacts pending."""
    campaign = load_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")
    campaign.status = "draft"
    campaign.called = 0
    campaign.booked = 0
    campaign.failed = 0
    for contact in campaign.contacts:
        contact.status = "pending"
        contact.call_sid = None
        contact.outcome = None
    save_campaign(campaign)
    return {"status": "reset", "campaign_id": campaign_id}


@app.get("/api/campaigns/{campaign_id}/progress")
async def api_campaign_progress(campaign_id: str):
    campaign = load_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")
    return {
        "campaign_id": campaign_id,
        "status": campaign.status,
        "total_contacts": campaign.total_contacts,
        "called": campaign.called,
        "booked": campaign.booked,
        "failed": campaign.failed,
        "remaining": campaign.total_contacts - campaign.called - campaign.failed,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
