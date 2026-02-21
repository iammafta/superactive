"""
Tests for tool_registry.py — tool definitions, tool loading, and handler registry.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tool_registry import TOOL_DEFINITIONS, TOOL_HANDLERS, get_tools_for_agent


class TestToolDefinitions:
    """Tests for tool definitions structure."""

    def test_all_definitions_have_required_fields(self):
        for name, defn in TOOL_DEFINITIONS.items():
            assert "name" in defn, f"{name} missing 'name'"
            assert "description" in defn, f"{name} missing 'description'"
            assert "parameters" in defn, f"{name} missing 'parameters'"
            assert defn["name"] == name, f"Key '{name}' doesn't match definition name '{defn['name']}'"

    def test_all_definitions_have_valid_parameters(self):
        for name, defn in TOOL_DEFINITIONS.items():
            params = defn["parameters"]
            assert params.get("type") == "object", f"{name} parameters should be type 'object'"
            assert "properties" in params, f"{name} missing 'properties'"

    def test_known_tools_exist(self):
        expected = ["book_appointment", "check_availability", "transfer_to_human",
                     "send_followup_sms", "log_lead", "lookup_client", "tavily_search"]
        for tool in expected:
            assert tool in TOOL_DEFINITIONS, f"Missing tool definition: {tool}"

    def test_handler_exists_for_each_definition(self):
        """Every defined tool should have a handler (except call_business_api which is special)."""
        for name in TOOL_DEFINITIONS:
            if name != "call_business_api":
                assert name in TOOL_HANDLERS, f"No handler for tool: {name}"


class TestGetToolsForAgent:
    """Tests for get_tools_for_agent function."""

    def test_returns_matching_tools(self, sample_agent_config):
        tools = get_tools_for_agent(sample_agent_config)
        tool_names = [t["name"] for t in tools]
        assert "book_appointment" in tool_names
        assert "tavily_search" in tool_names

    def test_returns_empty_for_no_tools(self, sample_agent_config):
        sample_agent_config.allowed_tools = []
        tools = get_tools_for_agent(sample_agent_config)
        assert tools == []

    def test_ignores_unknown_tools(self, sample_agent_config):
        sample_agent_config.allowed_tools = ["nonexistent_tool", "book_appointment"]
        tools = get_tools_for_agent(sample_agent_config)
        assert len(tools) == 1
        assert tools[0]["name"] == "book_appointment"

    def test_returns_correct_count(self, sample_agent_config):
        tools = get_tools_for_agent(sample_agent_config)
        assert len(tools) == len(sample_agent_config.allowed_tools)
