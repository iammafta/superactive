import asyncio
import pytest
from unittest.mock import MagicMock
from loguru import logger

# Mocking the FunctionCallParams class as it exists in pipecat
class FunctionCallParams:
    def __init__(self, function_name, tool_call_id, arguments, llm, context, result_callback):
        self.function_name = function_name
        self.tool_call_id = tool_call_id
        self.arguments = arguments
        self.llm = llm
        self.context = context
        self.result_callback = result_callback

# Re-implementing the wrapper logic to test it in isolation
@pytest.mark.asyncio
async def test_wrapper_logic():
    print("🧪 Testing wrapper reconstruction logic...")
    
    # Mock data matches what we saw in logs
    # Arg 0: function_name
    # Arg 1: tool_call_id
    # Arg 2: arguments
    tool_name = "tavily_search"
    tool_id = "call_123"
    tool_args = {"query": "test query"}
    
    # Arg 3: llm service
    mock_llm = MagicMock()
    # Arg 4: context
    mock_context = MagicMock()
    # Arg 5: callback
    async def mock_callback(result):
        print(f"✅ Callback received result: {result}")
    
    # The raw arguments passed by Google Vertex LLM service
    args = (tool_name, tool_id, tool_args, mock_llm, mock_context, mock_callback)
    
    # --- Logic from tool_registry.py ---
    params = None
    
    # Check if arg 0 is already FunctionCallParams (Standard Pipecat)
    if args and hasattr(args[0], "arguments"):
        print("ℹ️ Detected Standard Pipecat signature")
        params = args[0]
    
    # Check if we have the raw unpacked arguments (Google Vertex Pipecat)
    elif len(args) >= 6 and isinstance(args[2], dict) and callable(args[-1]):
        print("ℹ️ Detected Google Vertex signature")
        try:
            # We use our local mock class here just to verify the mapping
            params = FunctionCallParams(
                function_name=args[0],
                tool_call_id=args[1],
                arguments=args[2],
                llm=args[3],
                context=args[4],
                result_callback=args[-1]
            )
            print("✅ Successfully constructed FunctionCallParams!")
            print(f"   Name: {params.function_name}")
            print(f"   ID: {params.tool_call_id}")
            print(f"   Args: {params.arguments}")
        except Exception as e:
            print(f"❌ Error constructing params: {e}")
            
    if params:
        print("🎉 Logic passed!")
    else:
        print("💀 Logic failed to reconstruct params.")

if __name__ == "__main__":
    asyncio.run(test_wrapper_logic())
