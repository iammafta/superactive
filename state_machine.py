"""
Superactive — Conversation State Machine (v2: Smart Context)

Pipecat FrameProcessor that manages conversation flow, anti-loop guards,
conversation memory, and state-aware context injection.

KEY IMPROVEMENTS (v2):
- Conversation memory: tracks what user has told us → prevents re-asking
- Semantic repeat detection: catches "I already told you" patterns, not just exact matches
- Auto-advance: forces state transition when stuck too long, picking first available transition
- Richer context injection: includes collected facts and anti-loop reminders

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


class ConversationMemory:
    """Tracks facts the user has provided during the conversation.

    This prevents the LLM from re-asking questions the user already answered.
    Facts are stored as key→value pairs, e.g. {"insurance_type": "auto"}.
    """

    def __init__(self):
        self._facts: dict[str, str] = {}
        self._user_statements: list[str] = []  # Raw user utterances (last N)
        self._max_statements = 10

    def record_statement(self, text: str):
        """Record a user statement for context."""
        self._user_statements.append(text.strip())
        if len(self._user_statements) > self._max_statements:
            self._user_statements.pop(0)

        # Auto-extract common facts from user speech
        self._auto_extract(text)

    def _auto_extract(self, text: str):
        """Extract key facts from user text automatically."""
        text_lower = text.lower()

        # Insurance type detection
        insurance_types = {
            "auto": ["auto insurance", "car insurance", "vehicle insurance", "auto"],
            "home": ["home insurance", "homeowner", "house insurance", "property insurance"],
            "life": ["life insurance", "life policy"],
            "health": ["health insurance", "medical insurance", "health coverage"],
            "business": ["business insurance", "commercial insurance", "liability"],
            "renters": ["renter", "renters insurance"],
        }
        for itype, keywords in insurance_types.items():
            if any(kw in text_lower for kw in keywords):
                self.set_fact("insurance_type", itype)

        # Current carrier detection
        carriers = ["progressive", "geico", "state farm", "allstate", "usaa",
                     "liberty mutual", "nationwide", "farmers", "travelers", "aetna",
                     "cigna", "united healthcare", "blue cross", "kaiser"]
        for carrier in carriers:
            if carrier in text_lower:
                self.set_fact("current_carrier", carrier.title())

        # Party size (for restaurant)
        party_match = re.search(r'(\d+)\s*(?:people|guests|persons|of us)', text_lower)
        if party_match:
            self.set_fact("party_size", party_match.group(1))

        # Name detection (simple: "my name is X" or "I'm X")
        name_match = re.search(r"(?:my name is|i'm|i am|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", text)
        if name_match:
            self.set_fact("caller_name", name_match.group(1))

    def set_fact(self, key: str, value: str):
        """Store or update a fact."""
        if key not in self._facts or self._facts[key] != value:
            logger.info(f"🧠 Memory: {key} = {value}")
        self._facts[key] = value

    def get_fact(self, key: str) -> Optional[str]:
        return self._facts.get(key)

    def get_all_facts(self) -> dict[str, str]:
        return dict(self._facts)

    def get_summary(self) -> str:
        """Build a human-readable summary of what we know."""
        if not self._facts:
            return ""
        lines = [f"- {k.replace('_', ' ').title()}: {v}" for k, v in self._facts.items()]
        return "What we already know from this conversation:\n" + "\n".join(lines)


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

        # Conversation memory
        self._memory = ConversationMemory()

        # Repeat/loop detection
        self._last_user_text = ""
        self._repeat_count = 0
        self._user_history: list[str] = []  # Last N user utterances for loop detection

        # Frustration detection — keyword + semantic patterns
        self._frustration_keywords = [
            "this is ridiculous", "waste of time", "terrible",
            "awful", "useless", "stupid", "hate this",
            "not helpful", "worst", "incompetent",
        ]
        # Patterns that indicate the user is annoyed at being re-asked
        self._reask_patterns = [
            r"i already (?:told|said|mentioned)",
            r"i just (?:told|said|mentioned)",
            r"you already asked",
            r"i(?:'ve| have) already (?:answered|said)",
            r"how many times",
            r"are you (?:listening|hearing)",
            r"i said it (?:before|earlier|already)",
            r"as i (?:said|mentioned|told you)",
            r"weren't you listening",
            r"pay attention",
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
            "collected_info": self._memory.get_all_facts(),
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
        """Check if user sounds frustrated (keyword or semantic)."""
        text_lower = text.lower()
        for keyword in self._frustration_keywords:
            if keyword in text_lower:
                logger.info(f"😤 Frustration detected: '{keyword}'")
                return True
        return False

    def _check_reask_complaint(self, text: str) -> bool:
        """Check if user is complaining about being asked the same question.

        This catches phrases like 'I already told you' which indicate the LLM
        is stuck in a loop asking the same question repeatedly.
        """
        text_lower = text.lower()
        for pattern in self._reask_patterns:
            if re.search(pattern, text_lower):
                logger.info(f"🔁 Re-ask complaint detected: '{text[:60]}...'")
                return True
        return False

    def _check_repeat(self, text: str) -> bool:
        """Check if user is repeating themselves (exact or semantic)."""
        text_stripped = text.lower().strip()
        if not text_stripped:
            return False

        # Exact repeat
        if text_stripped == self._last_user_text.lower().strip():
            self._repeat_count += 1
            if self._repeat_count >= 2:
                logger.info(f"🔁 Exact repeat detected ({self._repeat_count}x)")
                return True
        else:
            self._repeat_count = 0

        # Track history for topic-level repeat detection
        self._user_history.append(text_stripped)
        if len(self._user_history) > 8:
            self._user_history.pop(0)

        self._last_user_text = text
        return False

    def _check_limits(self) -> Optional[str]:
        """Check if any limits have been reached. Returns action if so."""
        if self._turn_count >= self._config.max_turns:
            return "max_turns_reached"

        if self.elapsed_seconds >= self._config.max_duration_seconds:
            return "time_limit_reached"

        if self._current_state and self._current_state in self._states:
            state_cfg = self._states[self._current_state]
            if self._state_turn_count >= state_cfg.max_turns:
                return "state_turns_exceeded"

        return None

    def _force_advance_state(self) -> Optional[str]:
        """Force advance to the next state when stuck.

        Unlike the old code which only looked for 'timeout'/'default' keys,
        this picks the FIRST available transition — moving the conversation
        forward no matter what.
        """
        current = self._states.get(self._current_state)
        if not current or not current.transitions:
            return None

        # Priority: look for explicit fallback keys first
        for key in ("timeout", "default", "fallback"):
            if key in current.transitions:
                return current.transitions[key]

        # Otherwise take the first available transition
        first_target = next(iter(current.transitions.values()))
        logger.info(f"⏩ Force-advancing from {self._current_state} → {first_target}")
        return first_target

    def _build_context_injection(self, user_text: str) -> Optional[str]:
        """Build state-aware context to inject before LLM processes.

        This is the brain of the conversation intelligence. It builds a context
        message that guides the LLM with:
        1. System warnings (limits, escalation, frustration)
        2. Conversation memory (what we already know)
        3. Anti-loop reminders
        4. Current state + turn info
        """
        parts = []

        # --- Check limits ---
        limit_action = self._check_limits()
        if limit_action == "max_turns_reached":
            parts.append(
                "(We've been chatting a while — time to wrap up warmly. "
                "Offer to have someone follow up if there's anything else.)"
            )
        elif limit_action == "time_limit_reached":
            parts.append(
                "(Running low on time. Briefly recap what we covered "
                "and suggest continuing later if needed.)"
            )
        elif limit_action == "state_turns_exceeded":
            next_state = self._force_advance_state()
            if next_state:
                self.transition_to(next_state)
                new_state_cfg = self._states.get(next_state)
                instructions = new_state_cfg.instructions if new_state_cfg else ""
                parts.append(
                    f"(Natural moment to shift gears into {next_state}. {instructions})"
                )

        # --- Escalation ---
        if self._check_escalation(user_text):
            if self._call_id and self._call_logger:
                self._call_logger.record_escalation(self._call_id)
            parts.append(
                "(They'd like to talk to a real person — completely understandable. "
                "Use the transfer_to_human tool to connect them warmly.)"
            )

        # --- Frustration ---
        if self._check_frustration(user_text):
            if self._call_id and self._call_logger:
                self._call_logger.record_frustration(self._call_id)
            parts.append(
                "(I can tell they're getting frustrated. Take a breath, acknowledge it "
                "genuinely, and offer to bring in a human if that would help.)"
            )

        # --- Re-ask complaint (semantic loop detection) ---
        if self._check_reask_complaint(user_text):
            parts.append(
                "(Oops — they already told me this. Acknowledge it naturally "
                "and move to the next thing without dwelling on it.)"
            )
            # Force advance if we're deep into a state
            if self._state_turn_count >= 2:  # Reduced from 3 to 2 to be more aggressive on loops
                next_state = self._force_advance_state()
                if next_state:
                    self.transition_to(next_state)
                    parts.append(f"(Shifting naturally to {next_state} now.)")

        # --- Exact repeat ---
        if self._check_repeat(user_text):
            parts.append(
                "(They're repeating themselves — I should try explaining it differently "
                "or in simpler terms. Don't re-ask what I just asked.)"
            )

        # --- Conversation memory summary ---
        # DISABLE REGEX MEMORY INJECTION (v3 change)
        # We rely on the LLM's own context window to remember facts.
        # Injecting "what we verify with regex" often conflicts with what the LLM actually knows.
        # memory = self._memory.get_summary()
        # if memory:
        #    parts.append(f"[MEMORY: {memory}]")

        # --- Current state: conversational coaching ---
        # Written as natural guidance, not a database schema.
        # The LLM mirrors the tone of its instructions — robotic instructions
        # produce robotic speech. Coaching-style instructions produce natural speech.
        if self._current_state and self._current_state in self._states:
            state = self._states[self._current_state]
            lines = []

            # Coaching-style goal (the state instructions are already written
            # in a conversational tone by the agent config author)
            lines.append(f"Right now: {state.instructions}")

            # What to ask about (only if there are required fields)
            if state.required_info:
                lines.append(f"You still need to find out: {', '.join(state.required_info)}. Ask naturally — one at a time, woven into conversation.")

            # Transitions — phrased as natural "if…then" guidance
            if state.transitions:
                trans = []
                for event, target in state.transitions.items():
                    # Convert snake_case event to readable English
                    readable = event.replace("_", " ")
                    trans.append(f"If {readable} → [TRANSITION: {target}]")
                lines.append("Move on when ready: " + " | ".join(trans))
            else:
                lines.append("This is the last step. When you're done, say [HANGUP].")

            # Gentle turn reminder only when running low
            if state.max_turns and self._state_turn_count + 1 >= state.max_turns - 1:
                lines.append("(Wrap this up soon — you've been on this topic a while.)")

            parts.append("\n".join(lines))

        return "\n".join(parts) if parts else None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process frames passing through the pipeline.

        CRITICAL: We must forward ALL frames via push_frame(). The base class
        process_frame() only handles internal bookkeeping and does NOT forward.
        """
        await super().process_frame(frame, direction)

        if direction == FrameDirection.DOWNSTREAM and isinstance(frame, TranscriptionFrame):
            self._turn_count += 1
            self._state_turn_count += 1

            # Log user speech to call transcript
            logger.info(f"🎤 User said: '{frame.text}' | call_id={self._call_id} | "
                        f"logger={'yes' if self._call_logger else 'NO'} | "
                        f"memory={self._memory.get_all_facts()}")
            if self._call_id and self._call_logger and frame.text.strip():
                self._call_logger.add_transcript(self._call_id, "user", frame.text)

            injection = self._build_context_injection(frame.text)
            if injection:
                logger.debug(f"💉 Injecting context: {injection[:200]}...")
                inject_frame = LLMMessagesUpdateFrame(
                    messages=[{"role": "user", "content": injection}],
                    run_llm=False,
                )
                await self.push_frame(inject_frame, direction)

        # ALWAYS forward the original frame
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
        self._transcript_buffer = ""  # Accumulates agent text fragments for clean transcript logging

    def _flush_transcript_buffer(self):
        """Flush accumulated agent text to transcript as a single entry."""
        if self._transcript_buffer.strip() and self._call_id and self._call_logger:
            self._call_logger.add_transcript(self._call_id, "agent", self._transcript_buffer.strip())
        self._transcript_buffer = ""

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Intercept LLM text frames to strip transition/hangup tags.

        CRITICAL: All non-TextFrame frames must be explicitly forwarded via
        push_frame(). The base class process_frame() does NOT forward frames.
        """
        # Flush agent transcript buffer when a new user utterance arrives or call ends
        # (this coalesces streaming token fragments into complete utterances)
        if direction == FrameDirection.DOWNSTREAM and isinstance(frame, (TranscriptionFrame, EndFrame)):
            self._flush_transcript_buffer()

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
            # Buffer agent text fragments for clean transcript logging
            # (streaming produces 2-5 word chunks — we coalesce into sentences)
            self._transcript_buffer += clean_text
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

    Buffers agent speech fragments and logs complete utterances when the next
    user turn arrives or the call ends.
    """

    def __init__(self, call_id: str, call_logger, **kwargs):
        super().__init__(**kwargs)
        self._call_id = call_id
        self._call_logger = call_logger
        self._transcript_buffer = ""

    def _flush_transcript_buffer(self):
        if self._transcript_buffer.strip():
            self._call_logger.add_transcript(self._call_id, "agent", self._transcript_buffer.strip())
        self._transcript_buffer = ""

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if direction == FrameDirection.DOWNSTREAM:
            if isinstance(frame, (TranscriptionFrame, EndFrame)):
                self._flush_transcript_buffer()
            elif isinstance(frame, TextFrame) and frame.text:
                self._transcript_buffer += frame.text
        await self.push_frame(frame, direction)
