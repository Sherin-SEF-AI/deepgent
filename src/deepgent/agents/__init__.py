"""Subagent definitions: AgentDefinition builders for architect, implementer,
verifier, hardware-runner, and researcher."""

from deepgent.agents.definitions import (
    BOARD_FARM_MCP,
    GENERATORS_MCP,
    KNOWLEDGE_MCP,
    build_agent_definitions,
)

__all__ = [
    "BOARD_FARM_MCP",
    "GENERATORS_MCP",
    "KNOWLEDGE_MCP",
    "build_agent_definitions",
]
