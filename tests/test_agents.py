"""Subagent definitions match the CLAUDE.md section 8 table."""

from pathlib import Path

import pytest

from deepgent.agents import (
    BOARD_FARM_MCP,
    GENERATORS_MCP,
    KNOWLEDGE_MCP,
    build_agent_definitions,
    build_critic_definition,
    select_agents,
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


# --- specialists, critic, and on-demand selection (expansion spec A1) -------


@pytest.mark.unit
def test_select_agents_loads_only_needed_specialists(settings: DeepgentSettings) -> None:
    from deepgent.core.classifier import classify

    agents = select_agents(settings, classify("quantize the model to int8"))
    # Core five are always present; the one relevant specialist is added.
    assert {"architect", "implementer", "verifier", "hardware-runner", "researcher"} <= set(agents)
    assert "perception-engineer" in agents
    # Unrelated specialists are not loaded.
    assert "driver-engineer" not in agents


@pytest.mark.unit
def test_select_agents_adds_critic_for_risk_two_plus(settings: DeepgentSettings) -> None:
    from deepgent.core.classifier import classify

    assert "critic" in select_agents(settings, classify("optimize inference latency"))
    # A trivial generic task stays critic-free.
    assert "critic" not in select_agents(settings, classify("rename a variable"))


@pytest.mark.unit
def test_specialists_cannot_delegate_or_use_exclusive_tools(settings: DeepgentSettings) -> None:
    from deepgent.core.classifier import classify

    agents = select_agents(settings, classify("write a v4l2 driver for the camera"))
    for name, definition in agents.items():
        if name in {"architect", "implementer", "verifier", "hardware-runner", "researcher"}:
            continue  # core agents keep their section 8 grants
        tools = definition.tools or []
        # Depth limit 2: no specialist may spawn another (no Task tool).
        assert "Task" not in tools
        # Exclusivity: no specialist gets knowledge or board tools.
        assert not any(t.startswith((KNOWLEDGE_MCP, BOARD_FARM_MCP)) for t in tools)


@pytest.mark.unit
def test_critic_is_read_only_opus(settings: DeepgentSettings) -> None:
    critic = build_critic_definition(settings)
    assert critic.model == settings.models.opus
    assert critic.tools == ["Read", "Grep", "Bash"]
    assert "Write" not in (critic.tools or [])
