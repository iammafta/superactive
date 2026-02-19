"""
Superactive — Telephony Routes (incoming calls, WebSocket, outbound)
"""

import os
import re
import uuid
import json

from fastapi import APIRouter, WebSocket, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from loguru import logger
from pydantic import BaseModel
from urllib.parse import unquote
from xml.sax.saxutils import escape as _xml_escape
from twilio.request_validator import RequestValidator

def xml_escape(s: str) -> str:
    """Escape a string for safe use inside an XML attribute value (double-quoted)."""
    return _xml_escape(s, {'"': '&quot;', "'": '&apos;'})

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import TTSSpeakFrame
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

from agent_config import load_agent, get_default_agent
from tool_registry import get_tools_for_agent, register_tools_for_agent
from state_machine import (
    StateMachineProcessor, StateTransitionFilter,
    TranscriptLoggerProcessor, TranscriptLoggerFilter,
)
from call_logger import call_logger

router = APIRouter(tags=["telephony"])

# Config from .env
CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
GCP_PROJECT = os.getenv("GCP_PROJECT_ID", "divine-apogee-480205-h8")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
PORT = int(os.getenv("PORT", 8765))

_E164_RE = re.compile(r'^\+[1-9]\d{1,14}$')


def _validate_e164(phone: str) -> str:
    """Validate and normalize a phone number to E.164 format."""
    phone = phone.strip()
    if not phone.startswith("+"):
        phone = f"+{phone}"
    if not _E164_RE.match(phone):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid phone number '{phone}'. Must be E.164 format (e.g. +14155551234)"
        )
    return phone


# ── Health ────────────────────────────────────────────────────────────

@router.get("/")
async def health():
    return {"status": "ok", "service": "Superactive", "phase": 3}


# ── Incoming Call Webhook ─────────────────────────────────────────────

@router.api_route("/incoming-call", methods=["GET", "POST"])
async def incoming_call(request: Request):
    """Handle incoming Twilio call — return TwiML to connect to WebSocket.
    Passes agent_id via custom parameters if specified."""
    # 1. Validate Twilio Signature
    if os.getenv("TWILIO_VALIDATION", "true").lower() != "false":
        auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        if auth_token:
            validator = RequestValidator(auth_token)
            signature = request.headers.get("X-Twilio-Signature", "")
            
            public_url = os.getenv("PUBLIC_URL", "")
            if public_url:
                url = f"{public_url.rstrip('/')}{request.url.path}"
                if request.url.query:
                    url += f"?{request.url.query}"
            else:
                url = str(request.url)
            
            if request.method == "POST":
                form_data = await request.form()
                params = dict(form_data)
            else:
                params = {}
                
            if not validator.validate(url, params, signature):
                logger.warning(f"🚨 Invalid Twilio signature for URL: {url}")
                raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    public_url = os.getenv("PUBLIC_URL", "")
    if public_url:
        ws_host = public_url.replace("https://", "").replace("http://", "").rstrip("/")
        ws_scheme = "wss" if "https" in public_url else "ws"
    else:
        ws_host = request.headers.get("host", "localhost:8765")
        ws_scheme = "wss"

    logger.info(f"📞 Incoming call webhook — WS target: {ws_scheme}://{ws_host}/media-stream")

    agent_id = request.query_params.get("agent_id", "")
    outbound = request.query_params.get("outbound", "")
    contact_name = request.query_params.get("contact_name", "")
    contact_extra = request.query_params.get("contact_extra", "")

    param_tags = []
    if agent_id:
        param_tags.append(f'<Parameter name="agent_id" value="{xml_escape(agent_id)}" />')
    if outbound:
        param_tags.append(f'<Parameter name="outbound" value="{xml_escape(outbound)}" />')
    if contact_name:
        param_tags.append(f'<Parameter name="contact_name" value="{xml_escape(contact_name)}" />')
    if contact_extra:
        param_tags.append(f'<Parameter name="contact_extra" value="{xml_escape(contact_extra)}" />')
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


# ── WebSocket Media Stream ────────────────────────────────────────────

@router.websocket("/media-stream")
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
    custom_params = call_data.get("body", {})
    agent_id = custom_params.get("agent_id", None)
    is_outbound = custom_params.get("outbound", "") == "1"
    contact_name = unquote(custom_params.get("contact_name", ""))
    contact_extra_raw = unquote(custom_params.get("contact_extra", ""))
    contact_extra = {}
    if contact_extra_raw:
        try:
            contact_extra = json.loads(contact_extra_raw)
        except Exception:
            pass
    logger.info(f"🔍 Custom params: {custom_params} → agent_id={agent_id} outbound={is_outbound} contact={contact_name} extra={contact_extra}")

    if agent_id:
        agent_config = await load_agent(agent_id)
        if not agent_config:
            logger.warning(f"Agent {agent_id} not found, using default")
            agent_config = await get_default_agent()
    else:
        agent_config = await get_default_agent()

    logger.info(f"🤖 Using agent: {agent_config.name} ({agent_config.id}) | "
                f"Guardrail: {agent_config.guardrail_level} | Outbound: {is_outbound}")

    # Start call logging
    call_logger.start_call(call_sid, agent_config.id, agent_config.business_type, agent_config.tenant_id)

    # 2. VAD (Voice Activity Detection) — init before transport
    vad = None
    try:
        logger.debug("Initializing Silero VAD...")
        vad = SileroVADAnalyzer(
            params=VADParams(
                start_confidence=0.7,
                stop_duration=1.5,
                min_audio_duration=0.5,
            )
        )
        logger.debug("Silero VAD initialized successfully")
    except Exception as e:
        logger.error(f"Failed to init VAD, continuing without: {e}")

    # 3. Transport — handles Twilio's µ-law audio format
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_enabled=True if vad else False,
            vad_analyzer=vad,
            serializer=TwilioFrameSerializer(
                stream_sid=stream_sid,
                call_sid=call_sid,
                account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
                auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
                params=TwilioFrameSerializer.InputParams(auto_hang_up=True),
            ),
        ),
    )

    # 4. STT — Google Cloud Speech-to-Text
    stt = GoogleSTTService(
        credentials_path=CREDENTIALS_PATH,
        location="global",
    )

    # 5. LLM — Gemini via Vertex AI (with config-driven prompt and tools)
    tools = get_tools_for_agent(agent_config)
    full_prompt = agent_config.build_full_prompt()

    # Outbound call context — inject awareness that WE called THEM
    outbound_greeting = agent_config.greeting  # default inbound greeting
    if is_outbound:
        who = contact_name or "there"
        # Build a natural outbound greeting — use the doctor/business name
        # from contact_extra if available, falling back to generic
        doctor_name = contact_extra.get("doctor", "")
        if doctor_name:
            outbound_greeting = f"Hi {who}, this is Sarah calling from {doctor_name}'s office. How are you doing?"
        else:
            outbound_greeting = f"Hi {who}, this is Sarah. How are you doing today?"
        context_lines = [
            f"IMPORTANT: You are making an OUTBOUND call. YOU called the customer, "
            f"they did NOT call you. The customer's name is {who}.",
            f"Your name is Sarah. Use it if asked who you are.",
            f"You already know why you're calling — explain it naturally when they answer.",
            f"Do NOT ask 'how can I help you?' — YOU called THEM.",
            f"Never say 'thank you for calling' — YOU initiated this call.",
        ]
        if contact_extra:
            extra_lines = [f"  - {k.replace('_', ' ').title()}: {v}" for k, v in contact_extra.items()]
            context_lines.append("What you know about this customer:\n" + "\n".join(extra_lines))
        full_prompt += "\n\n## OUTBOUND CALL CONTEXT\n" + "\n".join(context_lines)
        logger.info(f"📤 Outbound mode: greeting='{outbound_greeting[:60]}...' contact={who} extra={contact_extra}")

    llm = GoogleVertexLLMService(
        credentials_path=CREDENTIALS_PATH,
        project_id=GCP_PROJECT,
        location=GCP_LOCATION,
        model="gemini-2.0-flash",
        system_instruction=full_prompt,
        tools=[{"function_declarations": tools}] if tools else None,
    )

    # Register tool handlers (only the ones this agent is allowed to use)
    register_tools_for_agent(llm, agent_config, call_id=call_sid, call_logger=call_logger, call_sid=call_sid)

    # 6. TTS — Google Cloud Text-to-Speech
    tts = GoogleHttpTTSService(
        credentials_path=CREDENTIALS_PATH,
        voice_id=agent_config.voice_id,
    )

    # 7. Conversation context — using OpenAILLMContext (proven working pattern)
    messages = []
    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

    # 8. State machine (if agent has states) or lightweight transcript loggers
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


# ── Outbound Calls ────────────────────────────────────────────────────

from auth import get_current_user, UserContext

class OutboundCallRequest(BaseModel):
    to: str                  # Phone number to call
    agent_id: str            # Which agent config to use


@router.post("/api/outbound-call")
async def api_outbound_call(req: OutboundCallRequest, user: UserContext = Depends(get_current_user)):
    """Trigger an outbound call using a specific agent."""
    # Verify agent exists
    agent = await load_agent(req.agent_id, user.tenant_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{req.agent_id}' not found")

    # Validate destination phone number
    to_number = _validate_e164(req.to)

    try:
        from twilio.rest import Client
        client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN"),
        )

        host = os.getenv("PUBLIC_URL", f"https://localhost:{PORT}")

        from_number = os.getenv("TWILIO_PHONE_NUMBER", "")
        if not from_number.startswith("+"):
            from_number = f"+{from_number}"

        call = client.calls.create(
            to=to_number,
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
