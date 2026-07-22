"""Subagent definitions match the CLAUDE.md section 8 table."""

from pathlib import Path

import pytest

from deepgent.agents import (
    BOARD_FARM_MCP,
    GENERATORS_MCP,
    KNOWLEDGE_MCP,
    build_agent_definitions,
)
from deepgent.config import DeepgentSettings, load_settings

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def settings() -> DeepgentSettings:
    return load_settings(REPO_ROOT)


@pytest.mark.unit
def test_all_five_subagents_exist(settings: DeepgentSettings) -> None:
    agents = build_agent_definitions(settings)
    assert set(agents) == {
        "architect",
        "implementer",
        "verifier",
        "hardware-runner",
        "researcher",
    }
    for definition in agents.values():
        assert definition.description
        assert definition.prompt


@pytest.mark.unit
def test_tools_per_section_8_table(settings: DeepgentSettings) -> None:
    agents = build_agent_definitions(settings)
    assert agents["architect"].tools == ["Read", "Glob", "Grep", KNOWLEDGE_MCP]
    assert agents["implementer"].tools == [
        "Read",
        "Write",
        "Edit",
        "Bash",
        GENERATORS_MCP,
    ]
    assert agents["verifier"].tools == ["Bash", "Read"]
    assert agents["hardware-runner"].tools == [BOARD_FARM_MCP]
    assert agents["researcher"].tools == [KNOWLEDGE_MCP, "WebSearch"]


@pytest.mark.unit
def test_model_tiers_per_section_8_table(settings: DeepgentSettings) -> None:
    agents = build_agent_definitions(settings)
    assert agents["architect"].model == settings.models.opus
    assert agents["implementer"].model == settings.models.sonnet
    assert agents["verifier"].model == settings.models.sonnet
    assert agents["hardware-runner"].model == settings.models.sonnet
    assert agents["researcher"].model == settings.models.haiku


@pytest.mark.unit
def test_hardware_runner_touches_boards_only(settings: DeepgentSettings) -> None:
    tools = build_agent_definitions(settings)["hardware-runner"].tools
    assert tools is not None
    assert all(tool.startswith(BOARD_FARM_MCP) for tool in tools)
