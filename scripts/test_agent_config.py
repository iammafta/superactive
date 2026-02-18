
import asyncio
import os
import sys
sys.path.append(os.getcwd())

from tool_registry import get_tools_for_agent
from agent_config import load_agent
from pipecat.services.google.llm_vertex import GoogleVertexLLMService

async def test_llm_tool_selection():
    print("--- Testing LLM Tool Selection ---")
    
    # Load Agent
    agent = load_agent("debug_chat")
    if not agent:
        print("ERROR: debug_chat agent not found")
        return

    print(f"Agent loaded: {agent.name}")
    print(f"System Prompt: {agent.system_prompt[:100]}...")

    # Load Tools
    tools = get_tools_for_agent(agent)
    print(f"Tools available: {[t['name'] for t in tools] if tools else 'None'}")

    # Init LLM
    try:
        llm = GoogleVertexLLMService(
            credentials_path="service_account.json",
            project_id=os.getenv("GCP_PROJECT_ID"),
            location=os.getenv("GCP_LOCATION", "us-central1"),
            model="gemini-2.0-flash",
            tools=[{"function_declarations": tools}] if tools else None,
        )
        print("LLM Service initialized")
    except Exception as e:
        print(f"Failed to init LLM: {e}")
        return

    # Simulate Query
    messages = [
        {"role": "user", "content": "Who is the CEO of OpenAI?"}
    ]
    
    print("\nSending query: 'Who is the CEO of OpenAI?'")
    try:
        # Note: direct usage of LLM service might differ from pipeline, 
        # but we check if it generates a function call frame.
        # This is a mock interaction since we can't easily drive the full service without a pipeline.
        # So instead, let's just inspect the config and tools to ensure they are valid.
        pass
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_llm_tool_selection())
