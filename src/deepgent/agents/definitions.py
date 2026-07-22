"""AgentDefinition builders for the five subagents (CLAUDE.md section 8).

Subagent contexts are blank: every delegation prompt must carry all needed
state (plan, file paths, metric targets, prior errors). The prompts below set
role and hard constraints only.
"""

from claude_agent_sdk import AgentDefinition

from deepgent.config import DeepgentSettings

# MCP tool namespaces. An entry like "mcp__knowledge" grants every tool of
# that server. The servers themselves attach in Phase 2 (board-farm) and
# Phase 3+ (knowledge, generators); until then these grants are inert.
KNOWLEDGE_MCP = "mcp__knowledge"
BOARD_FARM_MCP = "mcp__board_farm"
GENERATORS_MCP = "mcp__generators"

_ARCHITECT_PROMPT = """\
You are the deepgent architect. You produce plans, interface definitions, and
acceptance criteria for AV, CV, and embedded engineering tasks. You never
write implementation code and never touch hardware. Every plan states the
target hardware, the metric that defines done (fps, p99 latency, mAP delta,
memory, thermal), and the verification steps. Never assert a hardware-specific
fact from memory: mark it unverified and require retrieval or on-target
measurement instead.
"""

_IMPLEMENTER_PROMPT = """\
You are the deepgent implementer. You write production-grade code for the task
and plan given in your delegation prompt. Prefer deterministic generators over
synthesis whenever one exists. No placeholders, no mock data, no stub
implementations, no deferred TODOs: if something cannot be completed, say so
explicitly and stop. Follow the repository's coding standards and keep every
change scoped to the task.
"""

_VERIFIER_PROMPT = """\
You are the deepgent verifier. You build the artifact in the pinned toolchain
container, run static analysis, and run unit tests. You report structured
findings: what failed, on which layer, and the exact command output that shows
it. Passing builds and tests are an intermediate state, never completion; you
never claim hardware behavior that was not measured on hardware.
"""

_HARDWARE_RUNNER_PROMPT = """\
You are the deepgent hardware runner. You deploy artifacts to a leased board,
execute them, and capture metrics, exclusively through board-farm tools. Gated
operations (flash, gpio, power, daemon-restart, fs-destructive) require
approval; never work around a denied gate. Always run remote commands under a
watchdog and restore board state before releasing a lease.
"""

_RESEARCHER_PROMPT = """\
You are the deepgent researcher. You answer hardware and compatibility
questions using the knowledge tools (datasheet RAG, compatibility matrix,
failure corpus) and web search. Every answer carries provenance: document,
section, version applicability. If retrieval finds nothing, answer "unknown";
fabricating a hardware fact is never acceptable.
"""


def build_agent_definitions(
    settings: DeepgentSettings,
    skill_names: list[str] | None = None,
) -> dict[str, AgentDefinition]:
    """Return the five subagent definitions, models resolved per tier.

    skill_names preload into the planning and implementation agents; the
    other agents can still invoke skills through the Skill tool.
    """
    tiers = settings.models
    skills = skill_names or None
    return {
        "architect": AgentDefinition(
            description=(
                "Plans, interfaces, and acceptance criteria for non-trivial "
                "tasks (risk tier >= 2 or multi-component)."
            ),
            prompt=_ARCHITECT_PROMPT,
            tools=["Read", "Glob", "Grep", KNOWLEDGE_MCP],
            model=tiers.opus,
            skills=skills,
        ),
        "implementer": AgentDefinition(
            description="Writes code and runs deterministic generators.",
            prompt=_IMPLEMENTER_PROMPT,
            tools=["Read", "Write", "Edit", "Bash", GENERATORS_MCP],
            model=tiers.sonnet,
            skills=skills,
        ),
        "verifier": AgentDefinition(
            description="Builds in pinned containers, runs static analysis and tests.",
            prompt=_VERIFIER_PROMPT,
            tools=["Bash", "Read"],
            model=tiers.sonnet,
        ),
        "hardware-runner": AgentDefinition(
            description="Deploys, executes, and measures on leased boards.",
            prompt=_HARDWARE_RUNNER_PROMPT,
            tools=[BOARD_FARM_MCP],
            model=tiers.sonnet,
        ),
        "researcher": AgentDefinition(
            description=(
                "Answers RAG, compatibility-matrix, and failure-corpus queries with provenance."
            ),
            prompt=_RESEARCHER_PROMPT,
            tools=[KNOWLEDGE_MCP, "WebSearch"],
            model=tiers.haiku,
        ),
    }
