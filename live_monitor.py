"""
Superactive — Live Call Monitor

Pub/Sub connection manager for the Enterprise-Grade Call Center view.
Manages active WebSockets and broadcasts call events.
Tenant-scoped: each connection is tagged with a tenant_id so broadcasts
only reach clients belonging to the same tenant.
"""

import asyncio
import json
from loguru import logger
from fastapi import WebSocket


class LiveMonitorManager:
    def __init__(self):
        # active websocket connections: list of WebSockets
        self.active_connections: list[WebSocket] = []
        # maps a websocket to a subscribed call_id (if any)
        self.subscriptions: dict[WebSocket, str] = {}
        # maps a websocket to the authenticated tenant_id
        self.tenant_map: dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, tenant_id: str = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        if tenant_id:
            self.tenant_map[websocket] = tenant_id
        logger.info(f"🟢 Monitor connected (tenant={tenant_id}). Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.subscriptions.pop(websocket, None)
        self.tenant_map.pop(websocket, None)
        logger.info(f"🔴 Monitor disconnected. Total: {len(self.active_connections)}")

    def subscribe(self, websocket: WebSocket, call_id: str):
        self.subscriptions[websocket] = call_id
        logger.info(f"📡 Monitor subscribed to: {call_id}")

    def unsubscribe(self, websocket: WebSocket):
        if websocket in self.subscriptions:
            old = self.subscriptions.pop(websocket)
            logger.info(f"📡 Monitor unsubscribed from: {old}")

    async def broadcast_event(self, event_type: str, data: dict, call_id: str = None, tenant_id: str = None):
        """
        Broadcast an event to connected clients.
        Global events (call_started, state_transition, etc) go to same-tenant clients.
        Detail events (transcript) go only to subscribed + same-tenant clients.
        """
        message = {
            "type": event_type,
            "call_id": call_id,
            "data": data
        }
        text_data = json.dumps(message)

        is_global = event_type in ("call_started", "call_ended", "state_transition", "frustration", "escalation", "active_calls_update")
        
        to_remove = []
        for connection in list(self.active_connections):
            try:
                # Tenant isolation: only send to clients in the same tenant
                conn_tenant = self.tenant_map.get(connection)
                if tenant_id and conn_tenant and conn_tenant != tenant_id:
                    continue

                subbed_call = self.subscriptions.get(connection)
                if is_global or subbed_call == call_id:
                    await connection.send_text(text_data)
            except RuntimeError:
                # Connection may be already closed
                to_remove.append(connection)
            except Exception as e:
                logger.error(f"Failed to send to monitor client: {e}")
                to_remove.append(connection)

        for connection in to_remove:
            self.disconnect(connection)

    def emit(self, event_type: str, data: dict, call_id: str = None, tenant_id: str = None):
        """Helper to fire-and-forget an event broadcast from synchronous code."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast_event(event_type, data, call_id, tenant_id))
        except RuntimeError:
            pass

live_monitor = LiveMonitorManager()
