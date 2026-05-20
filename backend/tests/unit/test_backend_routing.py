"""Unit tests for route_coder() function and AgentState.coding_backend field (T022)."""

from __future__ import annotations

import pytest

from app.agent.graph import route_coder
from app.agent.state import AgentState


class TestRouteCoder:
    def test_claude_code_routes_to_cli_node(self):
        assert route_coder({"coding_backend": "claude_code"}) == "cli_coder_node"

    def test_gemini_routes_to_cli_node(self):
        assert route_coder({"coding_backend": "gemini"}) == "cli_coder_node"

    def test_groq_routes_to_coder_node(self):
        assert route_coder({"coding_backend": "groq"}) == "coder_node"

    def test_openai_routes_to_coder_node(self):
        assert route_coder({"coding_backend": "openai"}) == "coder_node"

    def test_missing_backend_defaults_to_coder_node(self):
        assert route_coder({}) == "coder_node"

    def test_unknown_backend_defaults_to_coder_node(self):
        assert route_coder({"coding_backend": "unknown_llm"}) == "coder_node"


class TestAgentStateHasCodingBackend:
    def test_coding_backend_key_exists_in_typeddict(self):
        annotations = AgentState.__annotations__
        assert "coding_backend" in annotations

    def test_coding_backend_type_is_str(self):
        assert AgentState.__annotations__["coding_backend"] is str
