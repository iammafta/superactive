"""
Superactive — Tool Registry

Dynamic tool registration for Pipecat's LLM function calling.
Each agent config specifies which tools it can access — this module
registers only those tools with the LLM service.
Persisted in SQLite via db.py.
"""

import asyncio
import os
from datetime import datetime
from typing import Optional

import httpx
from loguru import logger

from pipecat.frames.frames import TTSSpeakFrame
from pipecat.services.llm_service import FunctionCallParams

from agent_config import AgentConfig
from db import db_log_lead, db_lookup_client
from orders import (
    get_item,
    hold_order,
    order_status,
    pickup_windows,
    price_order,
    send_payment_link,
    send_sms,
)


# ── Tool Definitions (Gemini function declaration format) ─────────────

TOOL_DEFINITIONS = {
    "book_appointment": {
        "name": "book_appointment",
        "description": "Book an appointment or reservation for the caller.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Preferred date (YYYY-MM-DD)"},
                "time": {"type": "string", "description": "Preferred time (HH:MM)"},
                "name": {"type": "string", "description": "Caller's full name"},
                "reason": {"type": "string", "description": "Reason for appointment"},
                "phone": {"type": "string", "description": "Caller's phone number"},
            },
            "required": ["name", "reason"],
        },
    },
    "check_availability": {
        "name": "check_availability",
        "description": "Check available appointment slots or reservation availability.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date to check (YYYY-MM-DD)"},
                "service_type": {"type": "string", "description": "Type of service or appointment"},
            },
            "required": ["date"],
        },
    },
    "transfer_to_human": {
        "name": "transfer_to_human",
        "description": "Transfer the call to a human representative.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Reason for transfer"},
                "department": {"type": "string", "description": "Department to transfer to"},
            },
            "required": ["reason"],
        },
    },
    "send_followup_sms": {
        "name": "send_followup_sms",
        "description": "Send a follow-up SMS to the caller after the call.",
        "parameters": {
            "type": "object",
            "properties": {
                "phone": {"type": "string", "description": "Phone number to send SMS to"},
                "message": {"type": "string", "description": "SMS message content"},
            },
            "required": ["phone", "message"],
        },
    },
    "log_lead": {
        "name": "log_lead",
        "description": "Log a lead with the caller's information for follow-up.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Caller's name"},
                "phone": {"type": "string", "description": "Phone number"},
                "interest": {"type": "string", "description": "What the caller is interested in"},
                "notes": {"type": "string", "description": "Additional notes from the conversation"},
                "priority": {
                    "type": "string",
                    "description": "Lead priority",
                    "enum": ["low", "medium", "high"],
                },
            },
            "required": ["name", "interest"],
        },
    },
    "lookup_client": {
        "name": "lookup_client",
        "description": "Look up if the caller is an existing client based on their phone number.",
        "parameters": {
            "type": "object",
            "properties": {
                "phone": {"type": "string", "description": "Caller's phone number"},
            },
            "required": ["phone"],
        },
    },
    "call_business_api": {
        "name": "call_business_api",
        "description": "Query the business's custom API for specific information.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What information to look up"},
                "context": {"type": "string", "description": "Additional context for the query"},
            },
            "required": ["query"],
        },
    },
    "tavily_search": {
        "name": "tavily_search",
        "description": "Perform a real-time web search using Tavily to find up-to-date information.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
    "get_item": {
        "name": "get_item",
        "description": "Look up one dish on this restaurant's menu. Returns the price in cents and whether it is available. Never guess a dish or a price.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Dish name the caller asked for"},
            },
            "required": ["name"],
        },
    },
    "price_order": {
        "name": "price_order",
        "description": "Price the items and quantities from the menu. The total is computed for you. Do not add prices yourself.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "Dishes to price",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "qty": {"type": "integer"},
                        },
                        "required": ["name", "qty"],
                    },
                },
            },
            "required": ["items"],
        },
    },
    "pickup_windows": {
        "name": "pickup_windows",
        "description": "List open pickup times for a date. Offer only the times this returns.",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "YYYY-MM-DD, today, or tomorrow"},
            },
            "required": ["date"],
        },
    },
    "hold_order": {
        "name": "hold_order",
        "description": "Hold a draft takeout order at a pickup time this system offered. This does not place the order.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "qty": {"type": "integer"},
                        },
                        "required": ["name", "qty"],
                    },
                },
                "pickup_time": {"type": "string", "description": "A time label returned by pickup_windows"},
                "date": {"type": "string", "description": "The same date passed to pickup_windows"},
                "name": {"type": "string"},
                "phone": {"type": "string"},
            },
            "required": ["items", "pickup_time"],
        },
    },
    "send_payment_link": {
        "name": "send_payment_link",
        "description": "Text a payment link for a held order. Do not invent a URL. The order is not placed until payment lands.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
            },
            "required": ["order_id"],
        },
    },
    "order_status": {
        "name": "order_status",
        "description": "Read whether a held order is draft, link_sent, paid, or expired. Confirm the order only when status is paid.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
            },
            "required": ["order_id"],
        },
    },
}


AGENT_CONTEXT_TOOLS = {
    "book_appointment",
    "check_availability",
    "log_lead",
    "lookup_client",
    "get_item",
    "price_order",
    "pickup_windows",
    "hold_order",
    "send_payment_link",
    "order_status",
}


class ToolFiller:
    """Speak one short line only when a tool is still running after 400ms."""

    def __init__(self):
        self.task = None
        self._job = None
        self._token = 0

    def bind(self, task) -> None:
        self.task = task

    def arm(self) -> None:
        if self._job and not self._job.done():
            return
        self._token += 1
        token = self._token
        self._job = asyncio.create_task(self._speak(token))

    def cancel(self) -> None:
        self._token += 1
        if self._job and not self._job.done():
            self._job.cancel()
        self._job = None

    async def _speak(self, token: int) -> None:
        try:
            await asyncio.sleep(0.4)
        except asyncio.CancelledError:
            return
        if token != self._token or self.task is None:
            return
        try:
            await self.task.queue_frames([
                TTSSpeakFrame(text="One second, I'll check that.", append_to_context=False)
            ])
        except Exception as exc:
            logger.warning(f"Filler failed: {exc}")


# ── Per-Call Helpers ───────────────────────────────────────────────────
# Note: agent_config and call_sid are passed explicitly (not globals)
# to ensure concurrent calls don't overwrite each other's context.


async def _try_webhook(tool_name: str, args: dict, agent_config: Optional[AgentConfig] = None) -> Optional[dict]:
    """Try routing a tool call through the agent's webhook. Returns None if no webhook configured."""
    if not agent_config or not agent_config.webhook_url:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                agent_config.webhook_url,
                json={
                    "tool": tool_name,
                    "arguments": args,
                    "agent_id": agent_config.id,
                },
                headers=agent_config.webhook_headers,
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f"Webhook returned {response.status_code} for {tool_name}, using fallback")
            return None
    except Exception as e:
        logger.warning(f"Webhook failed for {tool_name}: {e}, using fallback")
        return None


async def _log_booking_locally(args: dict, confirmation: str, agent_config: Optional[AgentConfig] = None):
    """Log a booking to DB."""
    if not agent_config:
        logger.error("Cannot log booking: no active agent config context")
        return
        
    try:
        booking = {
            "type": "booking",
            "name": args.get("name", "Unknown"),
            "phone": args.get("phone", ""),
            "date": args.get("date", ""),
            "time": args.get("time", ""),
            "reason": args.get("reason", ""),
            "confirmation": confirmation,
            "timestamp": datetime.now().isoformat(),
        }
        await db_log_lead(booking, agent_config.tenant_id)
    except Exception as e:
        logger.error(f"Failed to log booking locally: {e}")


# ── Tool Handlers ─────────────────────────────────────────────────────

async def handle_book_appointment(params: FunctionCallParams, agent_config: Optional[AgentConfig] = None):
    """Book an appointment. Routes through webhook if configured, otherwise smart fallback."""
    args = params.arguments
    logger.info(f"📅 Booking appointment: {args}")

    # Try webhook first (client's real booking system)
    webhook_result = await _try_webhook("book_appointment", args, agent_config)
    if webhook_result is not None:
        await params.result_callback(webhook_result)
        return

    result = {
        "booked": False,
        "status": "not_booked",
        "message": "The reservation book is not connected. Do not tell the caller they are booked.",
    }
    logger.info("Booking refused: no webhook")
    await params.result_callback(result)


async def handle_check_availability(params: FunctionCallParams, agent_config: Optional[AgentConfig] = None):
    """Check availability. Routes through webhook if configured, otherwise smart fallback."""
    args = params.arguments
    logger.info(f"📋 Checking availability: {args}")

    # Try webhook first (client's real calendar/booking system)
    webhook_result = await _try_webhook("check_availability", args, agent_config)
    if webhook_result is not None:
        await params.result_callback(webhook_result)
        return

    result = {
        "available": False,
        "date": args.get("date", ""),
        "slots": [],
        "message": "No schedule is connected. Do not offer times.",
    }
    logger.info("Availability refused: no webhook")
    await params.result_callback(result)


async def handle_transfer_to_human(params: FunctionCallParams, agent_config: Optional[AgentConfig] = None, call_sid: Optional[str] = None):
    """Transfer to human via Twilio call redirect, or log if no transfer number configured."""
    args = params.arguments
    logger.info(f"🔄 Transfer requested: {args}")

    transfer_number = os.getenv("TRANSFER_PHONE_NUMBER", "")

    if transfer_number and call_sid:
        # Real Twilio transfer — redirect the active call to the human's number
        try:
            from twilio.rest import Client
            client = Client(
                os.getenv("TWILIO_ACCOUNT_SID"),
                os.getenv("TWILIO_AUTH_TOKEN"),
            )
            # Update the live call with TwiML that dials the human
            twiml = (
                f'<Response><Say>Connecting you to a team member now. Please hold.</Say>'
                f'<Dial>{transfer_number}</Dial></Response>'
            )
            client.calls(call_sid).update(twiml=twiml)
            result = {
                "status": "transferred",
                "reason": args.get("reason", "Caller request"),
                "message": "Transferring you to a team member now.",
            }
            logger.info(f"✅ Call {call_sid} transferred to {transfer_number}")
        except Exception as e:
            logger.error(f"Transfer failed: {e}")
            result = {
                "status": "transfer_failed",
                "reason": args.get("reason", "Caller request"),
                "message": "I wasn't able to transfer right now. Let me take your details and have someone call you back.",
            }
    else:
        # No transfer number configured — graceful fallback
        result = {
            "status": "callback_scheduled",
            "reason": args.get("reason", "Caller request"),
            "department": args.get("department", "General"),
            "message": "I'll make sure a team member calls you back shortly.",
        }
        logger.info("📝 Transfer requested but no TRANSFER_PHONE_NUMBER configured — offering callback")

    await params.result_callback(result)


async def handle_send_followup_sms(params: FunctionCallParams):
    """Send follow-up SMS via Twilio."""
    args = params.arguments
    logger.info(f"📱 Sending SMS to {args.get('phone', 'unknown')}")
    result = send_sms(args.get("phone", ""), args.get("message", ""))
    await params.result_callback(result)


def _tenant_id(agent_config: Optional[AgentConfig]) -> str:
    return agent_config.tenant_id if agent_config else ""


async def handle_get_item(params: FunctionCallParams, agent_config: Optional[AgentConfig] = None):
    result = await get_item(_tenant_id(agent_config), params.arguments.get("name", ""))
    await params.result_callback(result)


async def handle_price_order(params: FunctionCallParams, agent_config: Optional[AgentConfig] = None):
    result = await price_order(_tenant_id(agent_config), params.arguments.get("items") or [])
    await params.result_callback(result)


async def handle_pickup_windows(params: FunctionCallParams, agent_config: Optional[AgentConfig] = None):
    result = await pickup_windows(_tenant_id(agent_config), params.arguments.get("date"))
    public = {key: value for key, value in result.items() if key != "slot_keys"}
    await params.result_callback(public)


async def handle_hold_order(params: FunctionCallParams, agent_config: Optional[AgentConfig] = None):
    args = params.arguments
    result = await hold_order(
        _tenant_id(agent_config),
        args.get("items") or [],
        args.get("pickup_time", ""),
        name=args.get("name", ""),
        phone=args.get("phone", ""),
        agent_id=agent_config.id if agent_config else "",
        day_text=args.get("date"),
    )
    await params.result_callback(result)


async def handle_send_payment_link(params: FunctionCallParams, agent_config: Optional[AgentConfig] = None):
    result = await send_payment_link(_tenant_id(agent_config), params.arguments.get("order_id", ""))
    await params.result_callback(result)


async def handle_order_status(params: FunctionCallParams, agent_config: Optional[AgentConfig] = None):
    result = await order_status(_tenant_id(agent_config), params.arguments.get("order_id", ""))
    await params.result_callback(result)


async def handle_log_lead(params: FunctionCallParams, agent_config: Optional[AgentConfig] = None):
    """Log a lead to local storage."""
    args = params.arguments
    logger.info(f"📝 Logging lead: {args}")
    
    if not agent_config:
        result = {"status": "error", "message": "Internal error: no active agent context"}
        await params.result_callback(result)
        return

    lead = {
        "name": args.get("name", "Unknown"),
        "phone": args.get("phone", ""),
        "interest": args.get("interest", ""),
        "notes": args.get("notes", ""),
        "priority": args.get("priority", "medium"),
        "timestamp": datetime.now().isoformat(),
    }

    await db_log_lead(lead, agent_config.tenant_id)

    result = {"status": "logged", "lead_id": f"LEAD-{datetime.now().strftime('%Y%m%d%H%M%S')}"}
    await params.result_callback(result)


async def handle_lookup_client(params: FunctionCallParams, agent_config: Optional[AgentConfig] = None):
    """Look up a client by phone number."""
    args = params.arguments
    phone = args.get("phone", "")
    logger.info(f"🔍 Looking up client: {phone}")

    if not agent_config:
        result = {"found": False, "message": "Internal error: no active agent context"}
        await params.result_callback(result)
        return

    client_data = await db_lookup_client(phone, agent_config.tenant_id)

    if client_data:
        result = {"found": True, "client": client_data}
    else:
        result = {"found": False, "message": "New caller — no previous records found."}

    await params.result_callback(result)


async def handle_call_business_api(params: FunctionCallParams, agent_config: AgentConfig):
    """Call the business's custom webhook API."""
    args = params.arguments
    logger.info(f"🌐 Calling business API: {args}")

    if not agent_config.webhook_url:
        result = {"error": "No business API configured for this agent."}
        await params.result_callback(result)
        return

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                agent_config.webhook_url,
                json={
                    "query": args.get("query", ""),
                    "context": args.get("context", ""),
                    "agent_id": agent_config.id,
                },
                headers=agent_config.webhook_headers,
            )
            result = response.json()
    except Exception as e:
        logger.error(f"Business API call failed: {e}")
        result = {"error": "Could not reach the business system. Please try again."}

    await params.result_callback(result)


async def handle_tavily_search(params: FunctionCallParams):
    """Perform a web search via Tavily (preferred) or DuckDuckGo."""
    args = params.arguments
    query = args.get("query", "").strip()
    logger.info(f"🔎 Search Query: '{query}'")
    
    import asyncio

    def _perform_search_sync():
        results = []
        # 0. Try Tavily (Best for Company Data/Real-time)
        tavily_key = os.getenv("TAVILY_API_KEY")
        if tavily_key:
            try:
                from tavily import TavilyClient
                tavily = TavilyClient(api_key=tavily_key)
                response = tavily.search(query=query, search_depth="basic", max_results=3)
                for r in response.get("results", []):
                    results.append({
                        "title": r.get("title"),
                        "description": r.get("content"),
                        "url": r.get("url")
                    })
            except Exception as e:
                logger.error(f"Tavily search failed: {e}")

        # 1. Fallback: DuckDuckGo
        if not results:
            try:
                from duckduckgo_search import DDGS
                with DDGS() as ddgs:
                    search_results = list(ddgs.text(query, max_results=3))
                    for r in search_results:
                        results.append({
                            "title": r.get("title"),
                            "description": r.get("body"),
                            "url": r.get("href")
                        })
            except Exception as e:
                logger.error(f"DuckDuckGo failed: {e}")
                
        # 2. Fallback: Wikipedia
        if not results:
            try:
                import wikipedia
                wiki_search = wikipedia.search(query, results=1)
                if wiki_search:
                    page_title = wiki_search[0]
                    summary = wikipedia.summary(page_title, sentences=3)
                    results.append({
                        "title": f"Wikipedia: {page_title}",
                        "description": summary,
                        "url": f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}"
                    })
            except Exception as e:
                logger.error(f"Wikipedia failed: {e}")

        return results

    # Run blocking search in thread
    results = await asyncio.to_thread(_perform_search_sync)

    if results:
        result = {"status": "success", "results": results}
    else:
        result = {"status": "error", "message": "No results found."}

    await params.result_callback(result)


# ── Handler Registry ──────────────────────────────────────────────────

TOOL_HANDLERS = {
    "book_appointment": handle_book_appointment,
    "check_availability": handle_check_availability,
    "transfer_to_human": handle_transfer_to_human,
    "send_followup_sms": handle_send_followup_sms,
    "log_lead": handle_log_lead,
    "lookup_client": handle_lookup_client,
    "tavily_search": handle_tavily_search,
    "get_item": handle_get_item,
    "price_order": handle_price_order,
    "pickup_windows": handle_pickup_windows,
    "hold_order": handle_hold_order,
    "send_payment_link": handle_send_payment_link,
    "order_status": handle_order_status,
    # call_business_api is special — needs agent_config closure
}


async def _dispatch_handler(handler, name, params, agent_config, call_sid, filler: Optional[ToolFiller]):
    if filler is not None:
        filler.arm()
    try:
        if name in AGENT_CONTEXT_TOOLS:
            await handler(params, agent_config=agent_config)
        elif name == "transfer_to_human":
            await handler(params, agent_config=agent_config, call_sid=call_sid)
        else:
            await handler(params)
    finally:
        if filler is not None:
            filler.cancel()


# ── Registration ──────────────────────────────────────────────────────

def get_tools_for_agent(agent_config: AgentConfig) -> list[dict]:
    """Get Gemini tool declarations for the agent's allowed tools."""
    tools = []
    for tool_name in agent_config.allowed_tools:
        if tool_name in TOOL_DEFINITIONS:
            tools.append(TOOL_DEFINITIONS[tool_name])
        else:
            logger.warning(f"Unknown tool in config: {tool_name}")
    return tools


def register_tools_for_agent(llm, agent_config: AgentConfig, call_id: str = None, call_logger=None, call_sid: str = None, filler: Optional[ToolFiller] = None):
    """Register tool handlers with the LLM service for this agent.
    
    Each handler is wrapped in a closure that captures agent_config and call_sid
    for this specific call, preventing race conditions during concurrent calls.
    """
    # Capture per-call context via closure — no globals!
    _call_agent_config = agent_config
    _call_sid = call_sid
    registered = []

    for tool_name in agent_config.allowed_tools:
        if tool_name in TOOL_HANDLERS:
            handler = TOOL_HANDLERS[tool_name]
            if call_id and call_logger:
                async def logging_wrapper(*args, _handler=handler, _name=tool_name,
                                         _cfg=_call_agent_config, _sid=_call_sid, **kwargs):
                    logger.info(f"🐛 DEBUG: Wrapper called for {_name} with {len(args)} args")
                    
                    call_logger.record_tool_use(call_id, _name)
                    
                    # Reconstruction logic for Google Vertex LLM invocation signature
                    params = None
                    if args and hasattr(args[0], "arguments"):
                        params = args[0]
                    elif len(args) >= 6 and isinstance(args[2], dict) and callable(args[-1]):
                         from pipecat.services.llm_service import FunctionCallParams
                         try:
                             params = FunctionCallParams(
                                 function_name=args[0],
                                 tool_call_id=args[1],
                                 arguments=args[2],
                                 llm=args[3],
                                 context=args[4],
                                 result_callback=args[-1]
                             )
                         except Exception as e:
                             logger.error(f"❌ Error constructing FunctionCallParams: {e}")
                             if callable(args[-1]):
                                 await args[-1]({"error": f"Internal error constructing params: {e}"})
                             return
                    
                    if params:
                        try:
                            if not params.llm or not params.context:
                                logger.warning(f"⚠️ Warning: llm or context is None for {params.function_name}")
                            logger.info(f"▶️ Executing handler for {_name}...")
                            await _dispatch_handler(_handler, _name, params, _cfg, _sid, filler)
                            logger.info(f"✅ Handler for {_name} completed.")
                        except Exception as e:
                            logger.error(f"❌ API Handler Crashed: {e}")
                            if params.result_callback:
                                await params.result_callback({"error": "Tool execution failed internally."})
                    else:
                        logger.error(f"❌ Could not reconstruct FunctionCallParams from args: {args}")
                        for arg in args:
                            if callable(arg):
                                await arg({"error": "Internal tooling error: invalid argument format."})
                                return
                llm.register_function(tool_name, logging_wrapper)
            else:
                # No call logger — register with context closure for direct calls
                async def direct_wrapper(params: FunctionCallParams, _handler=handler, _name=tool_name,
                                         _cfg=_call_agent_config, _sid=_call_sid):
                    await _dispatch_handler(_handler, _name, params, _cfg, _sid, filler)
                llm.register_function(tool_name, direct_wrapper)
            registered.append(tool_name)
        elif tool_name == "call_business_api":
            # Special: closure over agent_config for webhook URL
            async def webhook_handler(params: FunctionCallParams, _cfg=_call_agent_config):
                if call_id and call_logger:
                    call_logger.record_tool_use(call_id, "call_business_api")
                await handle_call_business_api(params, _cfg)
            llm.register_function("call_business_api", webhook_handler)
            registered.append("call_business_api")
        else:
            logger.warning(f"No handler for tool: {tool_name}")

    logger.info(f"🔧 Registered {len(registered)} tools: {registered}")
    return registered
