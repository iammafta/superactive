"""One text turn of an agent, using the same prompt, coaching, and tools as a call."""

from __future__ import annotations

import asyncio
import os
import re
from typing import Optional

from loguru import logger

from agent_config import AgentConfig
from state_machine import coaching_for_state
from tool_registry import TOOL_HANDLERS, _dispatch_handler, get_tools_for_agent, handle_call_business_api

_TAG = re.compile(r"\[(?:TRANSITION:\s*(\w+)|HANGUP|[^\]]*)\]", re.IGNORECASE)


def credentials_ready() -> bool:
    path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "service_account.json")
    return bool(path) and os.path.isfile(path)


def apply_model_tags(text: str, state: Optional[str], known_states: set[str]) -> tuple[str, Optional[str]]:
    """Drop bracket tags and follow a transition the agent actually has."""
    current = state
    def replace(match: re.Match) -> str:
        nonlocal current
        target = match.group(1)
        if target and target in known_states:
            current = target
        return ""
    clean = _TAG.sub(replace, text or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean, current


async def run_tool(agent: AgentConfig, name: str, arguments: dict) -> dict:
    captured: dict = {}

    class _Params:
        def __init__(self):
            self.arguments = arguments or {}

        async def result_callback(self, result):
            captured["result"] = result

    params = _Params()
    if name == "call_business_api":
        await handle_call_business_api(params, agent)
    elif name in TOOL_HANDLERS:
        await _dispatch_handler(TOOL_HANDLERS[name], name, params, agent, None, None)
    else:
        captured["result"] = {"error": f"Unknown tool {name}"}
    result = captured.get("result") or {"error": "The tool returned nothing."}
    return result if isinstance(result, dict) else {"result": result}


def _known_states(agent: AgentConfig) -> set[str]:
    return {state.name for state in agent.states}


def _coaching(agent: AgentConfig, state_name: Optional[str]) -> str:
    if not agent.states:
        return ""
    name = state_name if state_name in _known_states(agent) else agent.states[0].name
    state = next(item for item in agent.states if item.name == name)
    return coaching_for_state(state)


async def simulate_turn(agent: AgentConfig, messages: list[dict], state: Optional[str] = None) -> dict:
    """Ask Gemini once, run any tool calls, and return the spoken text."""
    if not credentials_ready():
        raise RuntimeError("missing-credentials")

    from google import genai
    from google.genai import types

    known = _known_states(agent)
    current = state if state in known else (agent.states[0].name if agent.states else None)
    system = agent.build_full_prompt()
    coaching = _coaching(agent, current)
    if coaching:
        system = f"{system}\n\n## Current step\n{coaching}"

    declarations = []
    for tool in get_tools_for_agent(agent):
        declarations.append(
            types.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters=tool["parameters"],
            )
        )
    config = types.GenerateContentConfig(
        system_instruction=system,
        tools=[types.Tool(function_declarations=declarations)] if declarations else None,
    )
    client = genai.Client(
        vertexai=True,
        project=os.getenv("GCP_PROJECT_ID", ""),
        location=os.getenv("GCP_LOCATION", "us-central1"),
    )

    contents = []
    for message in messages:
        role = "user" if message.get("role") == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=message.get("text") or "")]))

    last_tool = None
    last_result = None
    spoken = ""
    for _ in range(4):
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.0-flash",
            contents=contents,
            config=config,
        )
        candidate = response.candidates[0].content
        contents.append(candidate)
        calls = []
        texts = []
        for part in candidate.parts or []:
            if getattr(part, "function_call", None) and part.function_call.name:
                calls.append(part.function_call)
            elif getattr(part, "text", None):
                texts.append(part.text)
        if not calls:
            spoken = " ".join(texts)
            break
        response_parts = []
        for call in calls:
            args = dict(call.args or {})
            result = await run_tool(agent, call.name, args)
            last_tool = call.name
            last_result = result
            response_parts.append(types.Part.from_function_response(name=call.name, response=result))
        contents.append(types.Content(role="user", parts=response_parts))
        logger.info(f"Simulator ran {last_tool}")

    clean, current = apply_model_tags(spoken, current, known)
    return {
        "text": clean or "I didn\u0027t catch that. Could you say it once more?",
        "state": current,
        "tool": last_tool,
        "tool_result": last_result,
    }
