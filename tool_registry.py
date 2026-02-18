"""
Superactive — Tool Registry

Dynamic tool registration for Pipecat's LLM function calling.
Each agent config specifies which tools it can access — this module
registers only those tools with the LLM service.
"""

import json
import os
from datetime import datetime
from typing import Any, Optional

import httpx
from loguru import logger

from pipecat.services.llm_service import FunctionCallParams

from agent_config import AgentConfig


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
}


# ── Tool Handlers ─────────────────────────────────────────────────────

async def handle_book_appointment(params: FunctionCallParams):
    """Book an appointment. Uses webhook if configured, otherwise logs locally."""
    args = params.arguments
    logger.info(f"📅 Booking appointment: {args}")

    # In production, this calls Google Calendar API or the business's webhook
    result = {
        "status": "booked",
        "name": args.get("name", "Unknown"),
        "date": args.get("date", "To be confirmed"),
        "time": args.get("time", "To be confirmed"),
        "reason": args.get("reason", "General"),
        "confirmation": f"APT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
    }
    logger.info(f"✅ Appointment booked: {result['confirmation']}")
    await params.result_callback(result)


async def handle_check_availability(params: FunctionCallParams):
    """Check availability. Stub — returns mock data."""
    args = params.arguments
    logger.info(f"📋 Checking availability: {args}")

    # Stub response — in production, queries calendar/booking system
    result = {
        "available": True,
        "date": args.get("date", "today"),
        "slots": ["9:00 AM", "10:30 AM", "2:00 PM", "3:30 PM"],
        "message": f"We have openings on {args.get('date', 'the requested date')}.",
    }
    await params.result_callback(result)


async def handle_transfer_to_human(params: FunctionCallParams):
    """Transfer to human. Logs the transfer request."""
    args = params.arguments
    logger.info(f"🔄 Transfer requested: {args}")

    # In production, this triggers a Twilio warm transfer
    result = {
        "status": "transferring",
        "reason": args.get("reason", "Caller request"),
        "department": args.get("department", "General"),
        "message": "Transferring you to a team member now.",
    }
    await params.result_callback(result)


async def handle_send_followup_sms(params: FunctionCallParams):
    """Send follow-up SMS via Twilio."""
    args = params.arguments
    logger.info(f"📱 Sending SMS to {args.get('phone', 'unknown')}")

    # In production, this calls Twilio SMS API
    try:
        from twilio.rest import Client
        client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN"),
        )
        message = client.messages.create(
            body=args["message"],
            from_=os.getenv("TWILIO_PHONE_NUMBER"),
            to=args["phone"],
        )
        result = {"status": "sent", "sid": message.sid}
    except Exception as e:
        logger.error(f"SMS failed: {e}")
        result = {"status": "queued", "message": "SMS will be sent after the call."}

    await params.result_callback(result)


async def handle_log_lead(params: FunctionCallParams):
    """Log a lead to local storage."""
    args = params.arguments
    logger.info(f"📝 Logging lead: {args}")

    lead = {
        "name": args.get("name", "Unknown"),
        "phone": args.get("phone", ""),
        "interest": args.get("interest", ""),
        "notes": args.get("notes", ""),
        "priority": args.get("priority", "medium"),
        "timestamp": datetime.now().isoformat(),
    }

    # Append to local leads file
    leads_file = "data/leads.jsonl"
    os.makedirs("data", exist_ok=True)
    with open(leads_file, "a") as f:
        f.write(json.dumps(lead) + "\n")

    result = {"status": "logged", "lead_id": f"LEAD-{datetime.now().strftime('%Y%m%d%H%M%S')}"}
    await params.result_callback(result)


async def handle_lookup_client(params: FunctionCallParams):
    """Look up a client by phone number."""
    args = params.arguments
    phone = args.get("phone", "")
    logger.info(f"🔍 Looking up client: {phone}")

    # Check local leads file for returning callers
    found = False
    client_data = {}
    leads_file = "data/leads.jsonl"
    if os.path.exists(leads_file):
        with open(leads_file) as f:
            for line in f:
                lead = json.loads(line.strip())
                if lead.get("phone") == phone:
                    found = True
                    client_data = lead
                    break

    if found:
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
    # call_business_api is special — needs agent_config closure
}


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


def register_tools_for_agent(llm, agent_config: AgentConfig, call_id: str = None, call_logger=None):
    """Register tool handlers with the LLM service for this agent."""
    registered = []

    for tool_name in agent_config.allowed_tools:
        if tool_name in TOOL_HANDLERS:
            handler = TOOL_HANDLERS[tool_name]
            if call_id and call_logger:
                async def logging_wrapper(*args, _handler=handler, _name=tool_name, **kwargs):
                    logger.info(f"🐛 DEBUG: Wrapper called for {_name} with {len(args)} args")
                    
                    call_logger.record_tool_use(call_id, _name)
                    
                    # Reconstruction logic for Google Vertex LLM invocation signature:
                    # Arg 0: name (str)
                    # Arg 1: id (str)
                    # Arg 2: arguments (dict)
                    # ...
                    # Last Arg: result_callback (function) or Arg 5
                    
                    params = None
                    
                    # Check if arg 0 is already FunctionCallParams (Standard Pipecat)
                    if args and hasattr(args[0], "arguments"):
                        params = args[0]
                    
                    # Check if we have the raw unpacked arguments (Google Vertex Pipecat)
                    elif len(args) >= 6 and isinstance(args[2], dict) and callable(args[-1]):
                         # Reconstruct FunctionCallParams
                         # Argument order from Google Vertex LLM service:
                         # 0: function_name
                         # 1: tool_call_id
                         # 2: arguments
                         # 3: llm service instance
                         # 4: context
                         # 5: result_callback
                         
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
                             # Fail gracefully by calling callback with error
                             if callable(args[-1]):
                                 await args[-1]({"error": f"Internal error constructing params: {e}"})
                             return
                    
                    if params:
                        try:
                            # Verify llm and context are valid before calling
                            if not params.llm or not params.context:
                                logger.warning(f"⚠️ Warning: llm or context is None for {params.function_name}")
                            
                            logger.info(f"▶️ Executing handler for {_name}...")
                            await _handler(params)
                            logger.info(f"✅ Handler for {_name} completed.")
                        except Exception as e:
                            logger.error(f"❌ API Handler Crashed: {e}")
                            import traceback
                            traceback.print_exc()
                            # Try to notify the user via callback if possible
                            if params.result_callback:
                                await params.result_callback({"error": "Tool execution failed interneally."})
                    else:
                        logger.error(f"❌ Could not reconstruct FunctionCallParams from args: {args}")
                        # Last ditch: try to find a callback and fail gracefully
                        for arg in args:
                            if callable(arg):
                                await arg({"error": "Internal tooling error: invalid argument format."})
                                return
                llm.register_function(tool_name, logging_wrapper)
            else:
                llm.register_function(tool_name, handler)
            registered.append(tool_name)
        elif tool_name == "call_business_api":
            # Special: closure over agent_config for webhook URL
            async def webhook_handler(params: FunctionCallParams, _cfg=agent_config):
                if call_id and call_logger:
                    call_logger.record_tool_use(call_id, "call_business_api")
                await handle_call_business_api(params, _cfg)
            llm.register_function("call_business_api", webhook_handler)
            registered.append("call_business_api")
        else:
            logger.warning(f"No handler for tool: {tool_name}")

    logger.info(f"🔧 Registered {len(registered)} tools: {registered}")
    return registered
