"""Example tool: returns a greeting message.

This is a minimal tool to demonstrate the conventions used in this repository.
Replace it with your own tool logic.
"""

from __future__ import annotations

from ibm_watsonx_orchestrate.agent_builder.tools import tool


@tool()
def hello_world(name: str) -> str:
    """Generate a friendly greeting for the given name.

    Args:
        name (str): The name of the person to greet.

    Returns:
        str: A greeting message.
    """
    if not name or not name.strip():
        return "Hello, World!"
    return f"Hello, {name.strip()}! Welcome to watsonx Orchestrate."
