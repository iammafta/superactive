"""
Pytest configuration and shared fixtures.
"""
import os
import sys
import asyncio
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env for tests
from dotenv import load_dotenv
load_dotenv()

# Prevent OpenTelemetry from attempting to export to Google Cloud during tests
os.environ["DISABLE_TELEMETRY"] = "1"


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for all tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
def reset_db_pool():
    """Ensure db._pool is reset for each test to avoid event loop conflicts."""
    import db
    db._pool = None
    yield
    db._pool = None


@pytest.fixture
def sample_agent_config():
    """Return a minimal AgentConfig for testing."""
    from agent_config import AgentConfig
    return AgentConfig(
        id="test-agent-001",
        tenant_id="test-tenant-001",
        name="Test Agent",
        business_type="medical",
        system_prompt="You are a test agent.",
        greeting="Hello, how can I help?",
        states=[
            {
                "name": "greeting",
                "instructions": "Greet the caller warmly",
                "transitions": {"qualifying": "After greeting, qualify"},
            },
            {
                "name": "qualifying",
                "instructions": "Qualify the caller's needs",
                "transitions": {"closing": "After qualifying, close"},
            },
            {
                "name": "closing",
                "instructions": "Close the conversation",
                "transitions": {},
            },
        ],
        allowed_tools=["book_appointment", "tavily_search"],
        guardrail_level=0.7,
    )
