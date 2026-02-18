"""
Superactive — Conversation State Machine

Pipecat FrameProcessor that manages conversation flow, anti-loop guards,
and state-aware context injection. Sits between STT and context aggregator.

IMPORTANT: Pipecat's base FrameProcessor.process_frame() does NOT forward
frames to the next processor — it only handles internal bookkeeping. Every
custom processor MUST explicitly call `await self.push_frame(frame, direction)`
to forward frames through the pipeline.
"""

import time
from typing import Optional

from loguru import logger
import re

from pipecat.frames.frames import (
    Frame,
    LLMMessagesUpdateFrame,
    TextFrame,
    TranscriptionFrame,
    EndFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from agent_config import AgentConfig


class StateMachineProcessor(FrameProcessor):
    """Tracks conversation state and injects state-aware context into LLM.

    Sits between STT and the user context aggregator. Passes ALL frames through
    unchanged, and additionally injects state-aware context for TranscriptionFrames.
    """

    def __init__(self, agent_config: AgentConfig, call_id: str = None, call_logger=None, **kwargs):
        super().__init__(**kwargs)
        self._config = agent_config
        self._call_id = call_id
        self._call_logger = call_logger
        self._states = {s.name: s for s in agent_config.states}

        # Current state
        self._current_state = agent_config.states[0].name if agent_config.states else None
        self._turn_count = 0
        self._state_turn_count = 0
        self._start_time = time.time()
        self._last_user_text = ""
        self._repeat_count = 0
        self._collected_info: dict = {}

        # Frustration keywords
        self._frustration_keywords = [
            "this is ridiculous", "waste of time", "terrible",
            "awful", "useless", "stupid", "hate this",
            "not helpful", "worst", "incompetent",
        ]

        logger.info(f"🔄 State machine initialized: {self._current_state} | "
                     f"States: {list(self._states.keys())}")

    @property
    def current_state(self) -> Optional[str]:
        return self._current_state

    @property
    def turn_count(self) -> int:
        return self._turn_count

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self._start_time

    def get_state_info(self) -> dict:
        """Get current state machine status for logging/dashboard."""
        return {
            "current_state": self._current_state,
            "turn_count": self._turn_count,
            "state_turn_count": self._state_turn_count,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
            "collected_info": self._collected_info,
            "states_available": list(self._states.keys()),
        }

    def transition_to(self, new_state: str):
        """Transition to a new state."""
        if new_state in self._states:
            old = self._current_state
            self._current_state = new_state
            self._state_turn_count = 0
            logger.info(f"🔄 State transition: {old} → {new_state}")
            if self._call_id and self._call_logger:
                self._call_logger.record_state_transition(
                    self._call_id, old or "unknown", new_state, self._turn_count
                )
        else:
            logger.warning(f"Unknown state: {new_state}")

    def _check_escalation(self, text: str) -> bool:
        """Check if user text contains escalation triggers."""
        text_lower = text.lower()
        for trigger in self._config.escalation_triggers:
            if trigger.lower() in text_lower:
                logger.info(f"🚨 Escalation triggered: '{trigger}'")
                return True
        return False

    def _check_frustration(self, text: str) -> bool:
        """Check if user sounds frustrated."""
        text_lower = text.lower()
        for keyword in self._frustration_keywords:
            if keyword in text_lower:
                logger.info(f"😤 Frustration detected: '{keyword}'")
                return True
        return False

    def _check_repeat(self, text: str) -> bool:
        """Check if user is repeating themselves."""
        if text.lower().strip() == self._last_user_text.lower().strip() and text.strip():
            self._repeat_count += 1
            if self._repeat_count >= 2:
                logger.info(f"🔁 Repeat detected ({self._repeat_count}x)")
                return True
        else:
            self._repeat_count = 0
        self._last_user_text = text
        return False

    def _check_limits(self) -> Optional[str]:
        """Check if any limits have been reached. Returns action if so."""
        # Global turn limit
        if self._turn_count >= self._config.max_turns:
            return "max_turns_reached"

        # Time limit
        if self.elapsed_seconds >= self._config.max_duration_seconds:
            return "time_limit_reached"

        # Per-state turn limit
        if self._current_state and self._current_state in self._states:
            state_cfg = self._states[self._current_state]
            if self._state_turn_count >= state_cfg.max_turns:
                return "state_turns_exceeded"

        return None

    def _build_context_injection(self, user_text: str) -> Optional[str]:
        """Build state-aware context to inject before LLM processes."""
        parts = []

        # Check limits
        limit_action = self._check_limits()
        if limit_action == "max_turns_reached":
            parts.append(
                "[SYSTEM: Maximum conversation length reached. Wrap up the conversation "
                "politely. Offer to have someone call them back if needed.]"
            )
        elif limit_action == "time_limit_reached":
            parts.append(
                "[SYSTEM: Call time limit approaching. Summarize what was discussed and "
                "offer to continue via callback.]"
            )
        elif limit_action == "state_turns_exceeded":
            # Auto-advance to next state or escalate
            current = self._states.get(self._current_state)
            if current and current.transitions:
                # Try to find a fallback/timeout transition
                next_state = current.transitions.get(
                    "timeout", current.transitions.get("default", None)
                )
                if next_state:
                    self.transition_to(next_state)
                    parts.append(
                        f"[SYSTEM: Moving conversation forward. Now in {next_state} phase.]"
                    )

        # Check escalation
        if self._check_escalation(user_text):
            if self._call_id and self._call_logger:
                self._call_logger.record_escalation(self._call_id)
            parts.append(
                "[SYSTEM: Caller wants to speak to a human. Use the transfer_to_human "
                "tool immediately. Be empathetic and confirm the transfer.]"
            )

        # Check frustration
        if self._check_frustration(user_text):
            if self._call_id and self._call_logger:
                self._call_logger.record_frustration(self._call_id)
            parts.append(
                "[SYSTEM: Caller sounds frustrated. Acknowledge their frustration sincerely. "
                "Offer to transfer to a human if they prefer.]"
            )

        # Check repeats
        if self._check_repeat(user_text):
            parts.append(
                "[SYSTEM: Caller is repeating themselves. They may not have understood your "
                "response. Try a different approach or simpler language.]"
            )

        # Add current state context
        if self._current_state and self._current_state in self._states:
            state = self._states[self._current_state]
            parts.append(f"[STATE: {state.name} | Turn {self._state_turn_count + 1}/{state.max_turns}]")

        return " ".join(parts) if parts else None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frames passing through the pipeline.

        CRITICAL: We must forward ALL frames via push_frame(). The base class
        process_frame() only handles internal bookkeeping and does NOT forward.
        """
        # Let base class handle internal bookkeeping (metrics, interruption state)
        await super().process_frame(frame, direction)

        # For downstream TranscriptionFrames, inject state-aware context BEFORE
        # forwarding the transcription itself
        if direction == FrameDirection.DOWNSTREAM and isinstance(frame, TranscriptionFrame):
            self._turn_count += 1
            self._state_turn_count += 1

            # Log user speech to call transcript
            logger.info(f"🎤 User said: '{frame.text}' | call_id={self._call_id} | logger={'yes' if self._call_logger else 'NO'}")
            if self._call_id and self._call_logger and frame.text.strip():
                self._call_logger.add_transcript(self._call_id, "user", frame.text)

            injection = self._build_context_injection(frame.text)
            if injection:
                logger.debug(f"💉 Injecting context: {injection}")
                inject_frame = LLMMessagesUpdateFrame(
                    messages=[{"role": "user", "content": injection}],
                    run_llm=False,
                )
                # Push the injection BEFORE the transcription frame
                await self.push_frame(inject_frame, direction)

        # ALWAYS forward the original frame — this is the critical fix!
        await self.push_frame(frame, direction)


class StateTransitionFilter(FrameProcessor):
    """Parses LLM output for state transition tags and updates the state machine.

    Sits between LLM and TTS. Strips [TRANSITION: state], [HANGUP], [STATE: ...],
    [SYSTEM: ...], and all other bracket tags from LLM output before passing
    cleaned text to TTS.

    Because LLM output streams token-by-token (each TextFrame is a few characters),
    tags like [TRANSITION: greeting] arrive as multiple fragments: "[", "TRANS",
    "ITION:", " greeting", "]". A simple regex on each chunk would never match.

    Solution: When we encounter a "[", we buffer text until "]" arrives, then
    process the complete tag. Non-bracket text is forwarded immediately.
    """

    def __init__(self, monitor: StateMachineProcessor, call_id: str = None, call_logger=None, **kwargs):
        super().__init__(**kwargs)
        self._monitor = monitor
        self._call_id = call_id
        self._call_logger = call_logger
        self._buffer = ""           # Accumulates text when inside a bracket tag
        self._buffering = False     # True when we've seen "[" but not yet "]"

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Intercept LLM text frames to strip transition/hangup tags.

        CRITICAL: All non-TextFrame frames must be explicitly forwarded via
        push_frame(). The base class process_frame() does NOT forward frames.
        """
        # Only intercept downstream TextFrames; forward everything else
        if not (direction == FrameDirection.DOWNSTREAM and isinstance(frame, TextFrame)):
            await super().process_frame(frame, direction)
            await self.push_frame(frame, direction)
            return

        # --- Handle downstream TextFrames ---
        await super().process_frame(frame, direction)

        text = frame.text

        # Process character-by-character to handle streaming bracket tags
        clean_chunks = []  # Text to forward to TTS
        i = 0
        while i < len(text):
            ch = text[i]

            if self._buffering:
                self._buffer += ch
                if ch == "]":
                    # Complete tag captured — process it
                    await self._handle_tag(self._buffer, direction)
                    self._buffer = ""
                    self._buffering = False
            elif ch == "[":
                # Start buffering a potential tag
                self._buffering = True
                self._buffer = "["
            else:
                clean_chunks.append(ch)

            i += 1

        # Forward any clean (non-tag) text
        clean_text = "".join(clean_chunks)
        if clean_text:
            if self._call_id and self._call_logger:
                self._call_logger.add_transcript(self._call_id, "agent", clean_text)
            await self.push_frame(TextFrame(clean_text), direction)

    async def _handle_tag(self, tag: str, direction: FrameDirection):
        """Process a complete bracketed tag like [TRANSITION: greeting] or [HANGUP]."""
        tag_upper = tag.upper()

        # [HANGUP] — end the call
        if "HANGUP" in tag_upper:
            logger.info("📞 LLM requested hangup via [HANGUP] tag")
            await self.push_frame(EndFrame(), direction)
            return

        # [TRANSITION: state_name] — change state
        match = re.search(r"\[TRANSITION:\s*(\w+)\]", tag, re.IGNORECASE)
        if match:
            new_state = match.group(1)
            logger.info(f"🔄 LLM requested transition to '{new_state}'")
            self._monitor.transition_to(new_state)
            return

        # All other bracket tags ([STATE: ...], [SYSTEM: ...], etc.) — silently drop
        logger.debug(f"🔇 Stripped tag from TTS output: {tag}")


class TranscriptLoggerProcessor(FrameProcessor):
    """Lightweight transcript logger for stateless agents (no state machine).

    Logs user speech from TranscriptionFrames and forwards all frames unchanged.
    """

    def __init__(self, call_id: str, call_logger, **kwargs):
        super().__init__(**kwargs)
        self._call_id = call_id
        self._call_logger = call_logger

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if direction == FrameDirection.DOWNSTREAM and isinstance(frame, TranscriptionFrame):
            if frame.text.strip():
                self._call_logger.add_transcript(self._call_id, "user", frame.text)
        await self.push_frame(frame, direction)


class TranscriptLoggerFilter(FrameProcessor):
    """Lightweight agent speech logger for stateless agents (no state machine).

    Logs agent speech from TextFrames and forwards all frames unchanged.
    """

    def __init__(self, call_id: str, call_logger, **kwargs):
        super().__init__(**kwargs)
        self._call_id = call_id
        self._call_logger = call_logger

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if direction == FrameDirection.DOWNSTREAM and isinstance(frame, TextFrame):
            if frame.text.strip():
                self._call_logger.add_transcript(self._call_id, "agent", frame.text)
        await self.push_frame(frame, direction)
