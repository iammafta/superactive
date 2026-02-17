"""
Superactive — Call Logger

Anonymized call data collection for the value flywheel.
Every call logs: outcome, state transitions, duration, frustration triggers.
This data improves prompt templates per vertical over time.
"""

# ... imports
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from loguru import logger


DATA_DIR = Path(__file__).parent / "data" / "calls"


class CallLog(BaseModel):
    """Single call record — anonymized for cross-client learning."""

    call_id: str
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

    # Transcript (for call history page)
    transcript: list[dict] = Field(default_factory=list)    # [{"role": "user|agent", "text": "...", "ts": "..."}]


class CallLogger:
    """Manages call logging for the value flywheel."""

    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._active_calls: dict[str, CallLog] = {}

    def start_call(self, call_id: str, agent_id: str, business_type: str) -> CallLog:
        """Start logging a new call."""
        log = CallLog(
            call_id=call_id,
            agent_id=agent_id,
            business_type=business_type,
            started_at=datetime.now().isoformat(),
        )
        self._active_calls[call_id] = log
        logger.info(f"📊 Call logging started: {call_id} (agent: {agent_id})")
        return log

    def add_transcript(self, call_id: str, role: str, text: str):
        """Add a transcript entry."""
        if call_id in self._active_calls:
            self._active_calls[call_id].transcript.append({
                "role": role,
                "text": text,
                "ts": datetime.now().isoformat(),
            })

    def record_state_transition(self, call_id: str, from_state: str, to_state: str, turn: int):
        """Record a state transition."""
        if call_id in self._active_calls:
            log = self._active_calls[call_id]
            log.state_transitions.append({
                "from": from_state,
                "to": to_state,
                "turn": turn,
            })
            if to_state not in log.states_visited:
                log.states_visited.append(to_state)

    def record_tool_use(self, call_id: str, tool_name: str):
        """Record that a tool was used."""
        if call_id in self._active_calls:
            self._active_calls[call_id].tools_used.append(tool_name)

    def record_frustration(self, call_id: str):
        """Record that frustration was detected."""
        if call_id in self._active_calls:
            self._active_calls[call_id].frustration_triggered = True

    def record_escalation(self, call_id: str):
        """Record that escalation was triggered."""
        if call_id in self._active_calls:
            self._active_calls[call_id].escalation_triggered = True

    async def end_call(self, call_id: str, outcome: str = "completed",
                 outcome_detail: str = "", hang_up_state: Optional[str] = None):
        """End and persist a call log."""
        if call_id not in self._active_calls:
            logger.warning(f"Call not found for logging: {call_id}")
            return None

        log = self._active_calls[call_id]
        log.ended_at = datetime.now().isoformat()
        log.outcome = outcome
        log.outcome_detail = outcome_detail
        log.hang_up_state = hang_up_state

        # Calculate duration
        start = datetime.fromisoformat(log.started_at)
        end = datetime.fromisoformat(log.ended_at)
        log.duration_seconds = int((end - start).total_seconds())
        log.total_turns = len([t for t in log.transcript if t["role"] == "user"])

        # Persist to daily JSONL file asynchronously
        await self._persist(log)

        # Remove from active
        del self._active_calls[call_id]
        logger.info(f"📊 Call logged: {call_id} | {outcome} | {log.duration_seconds}s | {log.total_turns} turns")
        return log

    async def _persist(self, log: CallLog):
        """Write call log to daily JSONL file in a separate thread."""
        def _write():
            today = datetime.now().strftime("%Y-%m-%d")
            path = DATA_DIR / f"{today}.jsonl"
            with open(path, "a") as f:
                f.write(log.model_dump_json() + "\n")
        
        await asyncio.to_thread(_write)

    def get_active_calls(self) -> list[dict]:
        """Get all active call summaries (for live dashboard)."""
        return [
            {
                "call_id": log.call_id,
                "agent_id": log.agent_id,
                "business_type": log.business_type,
                "started_at": log.started_at,
                "duration_seconds": int((datetime.now() - datetime.fromisoformat(log.started_at)).total_seconds()),
                "current_state": log.states_visited[-1] if log.states_visited else "unknown",
                "total_turns": len([t for t in log.transcript if t["role"] == "user"]),
            }
            for log in self._active_calls.values()
        ]

    async def get_calls(self, days: int = 7, agent_id: Optional[str] = None,
                  business_type: Optional[str] = None) -> list[CallLog]:
        """Get call history from JSONL files asynchronously."""
        
        def _read_calls():
            calls = []
            # Sort files recent first
            files = sorted(DATA_DIR.glob("*.jsonl"), reverse=True)[:days]
            for path in files:
                if not path.exists(): continue
                with open(path) as f:
                    for line in f:
                        try:
                            data = json.loads(line.strip())
                            log = CallLog(**data)
                            if agent_id and log.agent_id != agent_id:
                                continue
                            if business_type and log.business_type != business_type:
                                continue
                            calls.append(log)
                        except Exception:
                            continue
            # Sort calls by start time descending
            calls.sort(key=lambda c: c.started_at, reverse=True)
            return calls

        return await asyncio.to_thread(_read_calls)

    async def get_analytics(self, days: int = 30) -> dict:
        """Aggregate analytics for the dashboard."""
        calls = await self.get_calls(days=days)
        
        if not calls:
            return {
                "total_calls": 0, "avg_duration": 0, "booking_rate": 0,
                "frustration_rate": 0,
                "outcomes": {}, "agent_performance": [], "hang_up_heatmap": {}
            }

        total = len(calls)
        total_duration = sum(c.duration_seconds for c in calls)
        booked = sum(1 for c in calls if c.outcome == "booked")
        transferred = sum(1 for c in calls if c.outcome == "transferred")
        hung_up = sum(1 for c in calls if c.outcome == "hung_up")
        completed = sum(1 for c in calls if c.outcome == "completed")
        frustrated = sum(1 for c in calls if c.frustration_triggered)

        # Per-agent breakdown
        agent_stats: dict = {}
        for call in calls:
            aid = call.agent_id
            if aid not in agent_stats:
                agent_stats[aid] = {"calls": 0, "booked": 0, "total_duration": 0, "business_type": call.business_type}
            agent_stats[aid]["calls"] += 1
            agent_stats[aid]["total_duration"] += call.duration_seconds
            if call.outcome == "booked":
                agent_stats[aid]["booked"] += 1

        agent_performance = [
            {
                "agent_id": aid,
                "business_type": s["business_type"],
                "calls": s["calls"],
                "conversion_rate": round(s["booked"] / s["calls"] * 100, 1) if s["calls"] else 0,
                "avg_duration": round(s["total_duration"] / s["calls"]) if s["calls"] else 0,
            }
            for aid, s in agent_stats.items()
        ]

        # Hang-up state analysis (where callers drop off)
        hang_up_states: dict = {}
        for call in calls:
            if call.hang_up_state:
                hang_up_states[call.hang_up_state] = hang_up_states.get(call.hang_up_state, 0) + 1

        return {
            "total_calls": total,
            "avg_duration": round(total_duration / total) if total else 0,
            "booking_rate": round(booked / total * 100, 1) if total else 0,
            "frustration_rate": round(frustrated / total * 100, 1) if total else 0,
            "outcomes": {
                "booked": booked,
                "transferred": transferred,
                "completed": completed,
                "hung_up": hung_up,
            },
            "agent_performance": agent_performance,
            "hang_up_heatmap": hang_up_states,
        }


# Global instance
call_logger = CallLogger()
