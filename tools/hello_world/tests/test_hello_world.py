"""Tests for the hello_world example tool."""

from __future__ import annotations

import importlib
import sys
import types
from unittest.mock import MagicMock

import pytest

# Provide a lightweight stub for ibm_watsonx_orchestrate if not installed.
try:
    import ibm_watsonx_orchestrate.agent_builder.tools  # noqa: F401
except ImportError:
    mock_ibm = MagicMock()

    def _tool_decorator(*args, **kwargs):
        def wrapper(func):
            return func
        return wrapper

    mock_ibm.agent_builder.tools.tool = _tool_decorator
    sys.modules["ibm_watsonx_orchestrate"] = mock_ibm
    sys.modules["ibm_watsonx_orchestrate.agent_builder"] = mock_ibm.agent_builder
    sys.modules["ibm_watsonx_orchestrate.agent_builder.tools"] = mock_ibm.agent_builder.tools

from tools.hello_world.hello_world import hello_world


class TestHelloWorld:
    """Tests for the hello_world tool function."""

    def test_greets_by_name(self):
        result = hello_world("Alice")
        assert result == "Hello, Alice! Welcome to watsonx Orchestrate."

    def test_strips_whitespace(self):
        result = hello_world("  Bob  ")
        assert result == "Hello, Bob! Welcome to watsonx Orchestrate."

    def test_empty_string_returns_default(self):
        result = hello_world("")
        assert result == "Hello, World!"

    def test_whitespace_only_returns_default(self):
        result = hello_world("   ")
        assert result == "Hello, World!"
