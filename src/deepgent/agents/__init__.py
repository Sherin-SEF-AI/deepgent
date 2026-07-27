"""Subagent definitions: AgentDefinition builders for architect, implementer,
verifier, hardware-runner, and researcher."""

from deepgent.agents.definitions import (
    BOARD_FARM_MCP,
    CRITIC,
    GENERATORS_MCP,
    KNOWLEDGE_MCP,
    build_agent_definitions,
    build_critic_definition,
    select_agents,
)
from deepgent.agents.delegation import DelegationContext, assemble_delegation_prompt

__all__ = [
    "BOARD_FARM_MCP",
    "CRITIC",
    "GENERATORS_MCP",
    "KNOWLEDGE_MCP",
    "DelegationContext",
    "assemble_delegation_prompt",
    "build_agent_definitions",
    "build_critic_definition",
    "select_agents",
]
