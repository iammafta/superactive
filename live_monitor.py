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
from redis_client import get_redis

class LiveMonitorManager:
    REDIS_CHANNEL = "superactive:live_monitor"

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

    async def listen_to_redis(self):
        """Continuously listen to the Redis Pub/Sub channel and broadcast to local WebSockets."""
        r = get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(self.REDIS_CHANNEL)
        logger.info("📡 LiveMonitor subscribed to Redis Pub/Sub")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    payload = json.loads(message["data"])
                    await self._send_to_websockets(
                        event_type=payload["event_type"],
                        data=payload["data"],
                        call_id=payload.get("call_id"),
                        tenant_id=payload.get("tenant_id")
                    )
        except asyncio.CancelledError:
            logger.info("📡 LiveMonitor Redis listener cancelled")
        finally:
            await pubsub.unsubscribe(self.REDIS_CHANNEL)
            await pubsub.close()

    async def emit(self, event_type: str, data: dict | str, call_id: str = None, tenant_id: str = None):
        """Publish an event to the Redis channel for all workers to see."""
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except:
                pass

        payload = {
            "event_type": event_type,
            "data": data,
            "call_id": call_id,
            "tenant_id": tenant_id
        }
        try:
            r = get_redis()
            await r.publish(self.REDIS_CHANNEL, json.dumps(payload))
        except Exception as e:
            logger.error(f"Failed to publish to Redis Pub/Sub: {e}")

    async def _send_to_websockets(self, event_type: str, data: dict, call_id: str = None, tenant_id: str = None):
        """Broadcast an event ONLY to connected clients in this process."""
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

live_monitor = LiveMonitorManager()
