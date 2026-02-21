"""
Tests for state_machine.py — ConversationMemory, repeat detection, state transitions.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from state_machine import StateMachineProcessor, ConversationMemory


class TestConversationMemory:
    """Tests for the ConversationMemory class."""

    def test_set_fact(self):
        mem = ConversationMemory()
        mem.set_fact("name", "John")
        assert mem._facts["name"] == "John"

    def test_set_fact_overwrite(self):
        mem = ConversationMemory()
        mem.set_fact("name", "John")
        mem.set_fact("name", "Jane")
        assert mem._facts["name"] == "Jane"

    def test_get_fact(self):
        mem = ConversationMemory()
        mem.set_fact("phone", "555-1234")
        assert mem.get_fact("phone") == "555-1234"
        assert mem.get_fact("missing") is None

    def test_get_summary_empty(self):
        mem = ConversationMemory()
        assert mem.get_summary() == ""

    def test_get_summary_with_facts(self):
        mem = ConversationMemory()
        mem.set_fact("name", "John")
        mem.set_fact("phone", "555-1234")
        summary = mem.get_summary()
        assert "Name" in summary
        assert "John" in summary

    def test_record_statement(self):
        mem = ConversationMemory()
        mem.record_statement("I need auto insurance")
        assert len(mem._user_statements) == 1
        # Auto-extract should detect insurance type
        assert mem.get_fact("insurance_type") == "auto"

    def test_get_all_facts(self):
        mem = ConversationMemory()
        mem.set_fact("a", "1")
        mem.set_fact("b", "2")
        facts = mem.get_all_facts()
        assert facts == {"a": "1", "b": "2"}


class TestStateMachineProcessor:
    """Tests for the StateMachineProcessor class."""

    def test_initialization(self, sample_agent_config):
        processor = StateMachineProcessor(sample_agent_config)
        assert processor._current_state == "greeting"
        assert len(processor._states) == 3

    def test_get_state_info(self, sample_agent_config):
        processor = StateMachineProcessor(sample_agent_config)
        info = processor.get_state_info()
        assert info["current_state"] == "greeting"
        assert info["turn_count"] == 0
        assert "states_available" in info

    def test_transition(self, sample_agent_config):
        processor = StateMachineProcessor(sample_agent_config)
        processor.transition_to("qualifying")
        assert processor._current_state == "qualifying"

    def test_transition_to_unknown_state(self, sample_agent_config):
        processor = StateMachineProcessor(sample_agent_config)
        processor.transition_to("nonexistent_state")
        # Should stay at greeting (unknown state rejected)
        assert processor._current_state == "greeting"

    def test_repeat_detection(self, sample_agent_config):
        """Repeat detection triggers at repeat_count >= 2 (3rd identical message)."""
        processor = StateMachineProcessor(sample_agent_config)
        text = "I need an appointment please"
        result1 = processor._check_repeat(text)
        assert result1 is False  # 1st time
        result2 = processor._check_repeat(text)
        assert result2 is False  # 2nd time: repeat_count=1, threshold is 2
        result3 = processor._check_repeat(text)
        assert result3 is True   # 3rd time: repeat_count=2, triggers

    def test_repeat_detection_different_text(self, sample_agent_config):
        processor = StateMachineProcessor(sample_agent_config)
        processor._check_repeat("I need an appointment")
        result = processor._check_repeat("What time is available tomorrow?")
        assert result is False

    def test_frustration_detection(self, sample_agent_config):
        processor = StateMachineProcessor(sample_agent_config)
        # Use an exact frustration keyword
        result = processor._check_frustration("this is ridiculous")
        assert result is True

    def test_no_frustration_normal_text(self, sample_agent_config):
        processor = StateMachineProcessor(sample_agent_config)
        result = processor._check_frustration("Yes, that sounds good")
        assert result is False

    def test_turn_count_property(self, sample_agent_config):
        processor = StateMachineProcessor(sample_agent_config)
        assert processor.turn_count == 0
        processor._turn_count = 5
        assert processor.turn_count == 5

    def test_context_injection_returns_string(self, sample_agent_config):
        processor = StateMachineProcessor(sample_agent_config)
        context = processor._build_context_injection("Hello, I need help")
        assert isinstance(context, str)
        assert len(context) > 0

    def test_current_state_property(self, sample_agent_config):
        processor = StateMachineProcessor(sample_agent_config)
        assert processor.current_state == "greeting"
        processor.transition_to("closing")
        assert processor.current_state == "closing"
