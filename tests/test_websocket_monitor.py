import pytest
import asyncio
from datetime import datetime, timedelta
import jwt
from fastapi.websockets import WebSocketDisconnect
from fastapi.testclient import TestClient

import sys
from unittest.mock import MagicMock, AsyncMock, patch

# Mock telemetry BEFORE importing server to prevent GCP 403 errors during testing
sys.modules['telemetry'] = MagicMock()

from server import app
from live_monitor import live_monitor
from call_logger import call_logger, CallLog

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_ws_auth():
    with patch("routes.monitor.verify_ws_ticket", side_effect=lambda token: "test_tenant" if token == "valid_dummy_ticket" else None):
        yield

@pytest.fixture(autouse=True)
def mock_redis():
    """Mock out Redis dependency by mocking CallLogger calls."""
    call_logger.get_active_calls = AsyncMock(return_value=[])
    yield

@pytest.fixture
def valid_ws_token():
    return "valid_dummy_ticket"

@pytest.fixture
def invalid_ws_token():
    return "invalid_dummy_ticket"

def test_ws_connection_rejected_without_token():
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/monitor"):
            pass
    assert exc_info.value.code == 4001

def test_ws_connection_rejected_with_invalid_token(invalid_ws_token):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/monitor?token={invalid_ws_token}"):
            pass
    assert exc_info.value.code == 4001

def test_ws_connection_accepted_with_valid_token(valid_ws_token):
    try:
        with client.websocket_connect(f"/ws/monitor?token={valid_ws_token}") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "active_calls_update"
            assert "calls" in data["data"]
            assert len(live_monitor.active_connections) == 1
    except WebSocketDisconnect as e:
        pytest.fail(f"WebSocket rejected valid connection with code: {e.code}")

def test_ws_call_subscription(valid_ws_token):
    with client.websocket_connect(f"/ws/monitor?token={valid_ws_token}") as websocket:
        _ = websocket.receive_json() # active calls

        call_id = "test_call_id_123"
        dummy_log = CallLog(
            call_id=call_id,
            tenant_id="test_tenant",
            agent_id="test_agent",
            business_type="test",
            transcript=[{"role": "user", "text": "hello"}],
            states_visited=["greeting"],
            started_at=datetime.utcnow().isoformat()
        )
        call_logger.get_active_call = AsyncMock(return_value=dummy_log)

        websocket.send_json({"action": "subscribe", "call_id": call_id})
        
        # Should receive transcript history
        data = websocket.receive_json()
        assert data["type"] == "transcript_history"
        assert data["call_id"] == call_id
        assert data["data"]["transcript"][0]["text"] == "hello"

def test_ws_broadcast_frustration(valid_ws_token):
    with client.websocket_connect(f"/ws/monitor?token={valid_ws_token}") as websocket:
        _ = websocket.receive_json() # Ignore initial update
        
        # Test emitting an event via live_monitor singleton globally
        test_data = {"reason": "user swore"}
        # Must run in new event loop since we are in sync test
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(live_monitor._send_to_websockets("frustration", test_data, tenant_id="test_tenant"))
        finally:
            loop.close()
        
        data = websocket.receive_json()
        assert data["type"] == "frustration"
        assert data["data"]["reason"] == "user swore"
