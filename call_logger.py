"""
Superactive — Call Logger

Anonymized call data collection for the value flywheel.
Every call logs: outcome, state transitions, duration, frustration triggers.
This data improves prompt templates per vertical over time.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

from pydantic import BaseModel, Field
from loguru import logger

from db import db_persist_call, db_get_calls, db_get_analytics, db_get_tenant
from webhook_dispatcher import dispatch_post_call_webhook
from live_monitor import live_monitor
from redis_client import get_redis

class CallLog(BaseModel):
    """Single call record — anonymized for cross-client learning."""

    call_id: str
    tenant_id: str
    agent_id: str
    business_type: str
    started_at: str
    ended_at: Optional[str] = None
    duration_seconds: int = 0

    # Outcome
    outcome: str = "in_progress"                  # booked | transferred | completed | hung_up
    outcome_detail: str = ""                       # e.g. "appointment booked for 3/15"

    # State machine tracking
    states_visited: list[str] = Field(default_factory=list)
    hang_up_state: Optional[str] = None            # Where caller dropped off
    state_transitions: list[dict] = Field(         # [{"from": "greeting", "to": "qualifying", "turn": 3}]
        default_factory=list
    )

    # Conversation metrics
    total_turns: int = 0
    frustration_triggered: bool = False
    escalation_triggered: bool = False
    repeat_detected: bool = False
    tools_used: list[str] = Field(default_factory=list)

    # Cost tracking (per-minute: Twilio $0.013 + STT $0.006 + LLM $0.005 + TTS $0.004 = ~$0.028/min)
    cost_per_minute: float = 0.028
    cost_estimate: float = 0.0

    # Transcript (for call history page)
    transcript: list[dict] = Field(default_factory=list)    # [{"role": "user|agent", "text": "...", "ts": "..."}]


class CallLogger:
    """Manages call logging for the value flywheel unconditionally backed by Redis."""

    REDIS_KEY = "superactive:active_calls"

    async def _get_call(self, call_id: str) -> Optional[CallLog]:
        r = get_redis()
        data = await r.hget(self.REDIS_KEY, call_id)
        if data:
            return CallLog.model_validate_json(data)
        return None

    async def _save_call(self, log: CallLog):
        r = get_redis()
        await r.hset(self.REDIS_KEY, log.call_id, log.model_dump_json())

    async def start_call(self, call_id: str, agent_id: str, business_type: str, tenant_id: str) -> CallLog:
        """Start logging a new call. Idempotent — returns existing log if already registered."""
        existing = await self._get_call(call_id)
        if existing:
            logger.debug(f"📊 Call already registered in Redis: {call_id} — skipping duplicate start_call")
            return existing

        log = CallLog(
            call_id=call_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            business_type=business_type,
            started_at=datetime.now().isoformat(),
        )
        await self._save_call(log)
        logger.info(f"📊 Call logging started: {call_id} (agent: {agent_id}, tenant: {tenant_id})")
        
        await live_monitor.emit("call_started", {
            "call_id": call_id,
            "agent_id": agent_id,
            "business_type": business_type,
            "tenant_id": tenant_id,
            "started_at": log.started_at,
            "current_state": "unknown"
        }, tenant_id=tenant_id)
        
        return log

    async def add_transcript(self, call_id: str, role: str, text: str):
        """Add a transcript entry."""
        log = await self._get_call(call_id)
        if log:
            ts = datetime.now().isoformat()
            log.transcript.append({
                "role": role,
                "text": text,
                "ts": ts,
            })
            await self._save_call(log)
            logger.debug(f"📝 Transcript [{role}]: {text[:80]}")
            
            await live_monitor.emit("transcript", {
                "role": role,
                "text": text,
                "ts": ts
            }, call_id=call_id, tenant_id=log.tenant_id)

    async def record_state_transition(self, call_id: str, from_state: str, to_state: str, turn: int):
        """Record a state transition."""
        log = await self._get_call(call_id)
        if log:
            log.state_transitions.append({
                "from": from_state,
                "to": to_state,
                "turn": turn,
            })
            if to_state not in log.states_visited:
                log.states_visited.append(to_state)
            
            await self._save_call(log)
            await live_monitor.emit("state_transition", {
                "from_state": from_state,
                "to_state": to_state,
                "turn": turn,
                "states_visited": log.states_visited
            }, call_id=call_id, tenant_id=log.tenant_id)

    async def record_tool_use(self, call_id: str, tool_name: str):
        """Record that a tool was used."""
        log = await self._get_call(call_id)
        if log:
            log.tools_used.append(tool_name)
            await self._save_call(log)

    async def record_frustration(self, call_id: str):
        """Record that frustration was detected."""
        log = await self._get_call(call_id)
        if log:
            log.frustration_triggered = True
            await self._save_call(log)

    async def record_escalation(self, call_id: str):
        """Record that escalation was triggered."""
        log = await self._get_call(call_id)
        if log:
            log.escalation_triggered = True
            await self._save_call(log)

    async def end_call(self, call_id: str, outcome: str = "completed",
                 outcome_detail: str = "", hang_up_state: Optional[str] = None):
        """End and persist a call log."""
        log = await self._get_call(call_id)
        if not log:
            return None

        log.ended_at = datetime.now().isoformat()
        log.outcome = outcome
        log.outcome_detail = outcome_detail
        log.hang_up_state = hang_up_state

        # Calculate duration and cost
        start = datetime.fromisoformat(log.started_at)
        end = datetime.fromisoformat(log.ended_at)
        log.duration_seconds = int((end - start).total_seconds())
        log.total_turns = len([t for t in log.transcript if t["role"] == "user"])
        log.cost_estimate = round((log.duration_seconds / 60) * log.cost_per_minute, 4)

        # Persist to DB
        await self._persist(log)

        # Remove from active Redis hash
        r = get_redis()
        await r.hdel(self.REDIS_KEY, call_id)
        logger.info(f"📊 Call logged: {call_id} | {outcome} | {log.duration_seconds}s | {log.total_turns} turns")
        
        await live_monitor.emit("call_ended", {
            "call_id": call_id,
            "duration_seconds": log.duration_seconds,
            "outcome": outcome,
            "total_turns": log.total_turns
        }, tenant_id=log.tenant_id)

        # Dispatch Post-Call Webhook (in background)
        tenant = await db_get_tenant(log.tenant_id)
        if tenant and tenant.get("webhook_url") and tenant.get("api_key"):
            asyncio.create_task(
                dispatch_post_call_webhook(
                    webhook_url=tenant["webhook_url"],
                    api_key=tenant["api_key"],
                    call_data=log.model_dump()
                )
            )

        return log

    async def _persist(self, log: CallLog):
        """Write call log to DB."""
        await db_persist_call(log.model_dump(), log.tenant_id)

    async def get_active_call(self, call_id: str) -> Optional[CallLog]:
        """Get a single active call log by ID."""
        return await self._get_call(call_id)

    async def get_active_calls(self, tenant_id: str = None) -> list[dict]:
        """Get active call summaries, optionally filtered by tenant."""
        r = get_redis()
        data = await r.hgetall(self.REDIS_KEY)
        results = []
        now = datetime.now()
        
        for k, v in data.items():
            log = CallLog.model_validate_json(v)
            if tenant_id and log.tenant_id != tenant_id:
                continue
                
            results.append({
                "call_id": log.call_id,
                "agent_id": log.agent_id,
                "tenant_id": log.tenant_id,
                "business_type": log.business_type,
                "started_at": log.started_at,
                "duration_seconds": int((now - datetime.fromisoformat(log.started_at)).total_seconds()),
                "current_state": log.states_visited[-1] if log.states_visited else "unknown",
                "total_turns": len([t for t in log.transcript if t["role"] == "user"]),
            })
            
        return results

    async def get_calls(self, tenant_id: str, days: int = 7, agent_id: Optional[str] = None,
                  business_type: Optional[str] = None) -> list[CallLog]:
        """Get call history from DB."""
        if not tenant_id:
            return []
        rows = await db_get_calls(tenant_id, days, agent_id, business_type)
        return [CallLog(**row) for row in rows]

    async def get_analytics(self, tenant_id: str, days: int = 30) -> dict:
        """Aggregate analytics from DB."""
        if not tenant_id:
            return {}
        return await db_get_analytics(tenant_id, days)

    async def clear_analytics(self, tenant_id: str) -> bool:
        from db import db_clear_analytics
        if not tenant_id:
            return False
        return await db_clear_analytics(tenant_id)

# Global instance
call_logger = CallLogger()
