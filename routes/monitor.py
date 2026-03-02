"""
Superactive — Monitor Routes

WebSocket endpoint for the Admin Dashboard to receive real-time call events.
Authenticated via JWT token passed as query parameter.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from loguru import logger
import json

from live_monitor import live_monitor
from call_logger import call_logger
from auth import verify_ws_ticket

router = APIRouter(tags=["monitor"])

@router.websocket("/ws/monitor")
async def monitor_endpoint(websocket: WebSocket, token: str = Query(default=None)):
    """
    WebSocket endpoint for the frontend call center monitor.
    Requires JWT token via ?token= query parameter.
    Clients can send {"action": "subscribe", "call_id": "..."} to get detailed transcripts.
    """
    # Authenticate via short-lived WS ticket
    tenant_id = verify_ws_ticket(token) if token else None
    
    if not tenant_id:
        await websocket.close(code=4001, reason="Unauthorized")
        logger.warning("🔴 Monitor connection rejected: invalid or missing token")
        return

    await live_monitor.connect(websocket, tenant_id=tenant_id)
    
    # On connect, send the current list of active calls (filtered by tenant)
    active_calls = await call_logger.get_active_calls(tenant_id=tenant_id)
    await websocket.send_text(json.dumps({
        "type": "active_calls_update",
        "call_id": None,
        "data": {"calls": active_calls}
    }))

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                action = message.get("action")
                call_id = message.get("call_id")

                if action == "subscribe" and call_id:
                    live_monitor.subscribe(websocket, call_id)
                    # Send current transcript and state for this call
                    log = await call_logger.get_active_call(call_id)
                    if log and log.tenant_id == tenant_id:
                        await websocket.send_text(json.dumps({
                            "type": "transcript_history",
                            "call_id": call_id,
                            "data": {
                                "transcript": log.transcript,
                                "states_visited": log.states_visited,
                                "agent_id": log.agent_id,
                                "business_type": log.business_type
                            }
                        }))
                elif action == "unsubscribe":
                    live_monitor.unsubscribe(websocket)
                    
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        live_monitor.disconnect(websocket)
