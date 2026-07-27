"""AgentDefinition builders for the five subagents (CLAUDE.md section 8).

Subagent contexts are blank: every delegation prompt must carry all needed
state (plan, file paths, metric targets, prior errors). The prompts below set
role and hard constraints only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from claude_agent_sdk import AgentDefinition

from deepgent.config import DeepgentSettings

if TYPE_CHECKING:
    from deepgent.core.classifier import TaskClassification

CRITIC = "critic"

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


# --- specialists (expansion spec A1) ---------------------------------------
#
# Specialists are loaded on demand by task class, never all at once. Tool
# grants respect the delegation contract: no specialist gets knowledge or
# board-farm tools (those stay exclusive to researcher and hardware-runner),
# and no specialist gets the Task tool, which structurally caps delegation
# depth at 2 (a specialist cannot spawn another specialist).

_PERCEPTION_PROMPT = """\
You are the deepgent perception engineer. You own dataset handling, training
loops, PTQ/QAT quantization, accuracy-vs-latency tradeoffs, and export surgery
(ONNX opsets, dynamic shapes). You write production-grade training and export
code for the plan in your delegation prompt. State the accuracy metric and the
latency/memory target every change is measured against. You do not query the
knowledge layer directly (ask via the delegation prompt) and you never touch a
board; hand on-target measurement to the hardware runner.
"""

_DRIVER_PROMPT = """\
You are the deepgent driver engineer. You own V4L2/I2C/SPI drivers, device
tree, kernel modules, and SerDes (GMSL2/FPD-Link) link configuration. Never
assert a pin, register, address, or binding from memory: require it from the
researcher's retrieval or from on-target verification, and mark anything
unverified. You write drivers and device-tree fragments; you do not flash or
run on hardware yourself, the hardware runner does, under its gates.
"""

_PIPELINE_PROMPT = """\
You are the deepgent pipeline engineer. You own DeepStream/GStreamer graphs,
ROS 2 node graphs, zero-copy buffer paths, and QoS. You build pipelines that
respect the buffer-ownership and caps-negotiation rules of the stack in use.
State the end-to-end latency and throughput targets. You do not query the
knowledge layer directly and you do not touch boards.
"""

_PROFILER_PROMPT = """\
You are the deepgent profiler. You attribute bottlenecks with nsys/ncu and
tegrastats, and you reason about power-per-inference. You produce structured
findings: the dominant bottleneck (compute, memory, sync, or CPU), the
evidence for it, and the change that would move it. You measure; you do not
claim a hardware number that was not captured on hardware.
"""

_TRIAGE_PROMPT = """\
You are the deepgent triage engineer. You diagnose failures corpus-first:
before reasoning from scratch, require a corpus lookup (via the delegation
prompt / researcher) and prefer a verified prior resolution. You analyze logs,
dmesg, and crash output, and you construct a minimal reproduction. You do not
query the knowledge layer directly and you do not touch boards.
"""

_SAFETY_PROMPT = """\
You are the deepgent safety auditor. You review every C/C++ or firmware change
for MISRA-oriented defects and enumerate failure modes, in your own words:
never quote or paste licensed standards text. You run static analysis and
triage its findings. You report what is unsafe, why, and the exact remediation;
you do not rewrite the code yourself. Passing static analysis is necessary, not
sufficient.
"""

_DATA_PROMPT = """\
You are the deepgent data engineer. You own dataset curation, dedup, splits,
calibration-set construction, and auto-label QA. You prevent train/val leakage
and you document the provenance and composition of every split you produce. You
do not query the knowledge layer directly and you do not touch boards.
"""

_INTEGRATOR_PROMPT = """\
You are the deepgent integrator. You own packaging, OTA, versioning, rollback,
and staged rollout. You never write a version string outside versions.toml, and
every release path you build has an explicit rollback criterion. You do not
touch boards directly; deployment to hardware goes through the hardware runner.
"""

_CRITIC_PROMPT = """\
You are the deepgent critic, the final adversarial gate. You audit the
completed task's working-tree diff against its acceptance criteria and the
capability inventory. Look for: stubs, placeholders, mock data, simulated
results, TODO/FIXME, silent fallbacks, unreachable or untested branches,
fabricated hardware facts, and claims of hardware behavior that were not
measured on hardware. You do not edit code; you judge it.

End your reply with exactly one verdict line and nothing after it:
  CRITIC_VERDICT: PASS
or
  CRITIC_VERDICT: VETO: <one-line reason>
Veto if any prime-directive violation is present. When in doubt, veto.
"""


def _specialist_table(
    settings: DeepgentSettings,
    skills: list[str] | None,
) -> dict[str, AgentDefinition]:
    from deepgent.core.classifier import (
        DATA_ENGINEER,
        DRIVER_ENGINEER,
        INTEGRATOR,
        PERCEPTION_ENGINEER,
        PIPELINE_ENGINEER,
        PROFILER,
        SAFETY_AUDITOR,
        TRIAGE,
    )

    tiers = settings.models
    coder_tools = ["Read", "Write", "Edit", "Bash", GENERATORS_MCP]
    review_tools = ["Read", "Grep", "Bash"]
    return {
        PERCEPTION_ENGINEER: AgentDefinition(
            description="Training, quantization, accuracy, and export surgery.",
            prompt=_PERCEPTION_PROMPT,
            tools=coder_tools,
            model=tiers.sonnet,
            skills=skills,
        ),
        DRIVER_ENGINEER: AgentDefinition(
            description="V4L2/I2C/SPI drivers, device tree, kernel modules, SerDes.",
            prompt=_DRIVER_PROMPT,
            tools=coder_tools,
            model=tiers.sonnet,
            skills=skills,
        ),
        PIPELINE_ENGINEER: AgentDefinition(
            description="DeepStream/GStreamer and ROS 2 graphs, zero-copy, QoS.",
            prompt=_PIPELINE_PROMPT,
            tools=coder_tools,
            model=tiers.sonnet,
            skills=skills,
        ),
        PROFILER: AgentDefinition(
            description="nsys/ncu and tegrastats bottleneck attribution, power-per-inference.",
            prompt=_PROFILER_PROMPT,
            tools=review_tools,
            model=tiers.sonnet,
            skills=skills,
        ),
        TRIAGE: AgentDefinition(
            description="Corpus-first failure diagnosis and reproduction construction.",
            prompt=_TRIAGE_PROMPT,
            tools=review_tools,
            model=tiers.sonnet,
            skills=skills,
        ),
        SAFETY_AUDITOR: AgentDefinition(
            description="MISRA-oriented review and failure-mode enumeration for C/C++ changes.",
            prompt=_SAFETY_PROMPT,
            tools=review_tools,
            model=tiers.opus,  # safety is the highest-stakes reasoning
            skills=skills,
        ),
        DATA_ENGINEER: AgentDefinition(
            description="Dataset curation, dedup, splits, calibration sets, auto-label QA.",
            prompt=_DATA_PROMPT,
            tools=coder_tools,
            model=tiers.sonnet,
            skills=skills,
        ),
        INTEGRATOR: AgentDefinition(
            description="Packaging, OTA, versioning, rollback, staged rollout.",
            prompt=_INTEGRATOR_PROMPT,
            tools=coder_tools,
            model=tiers.sonnet,
            skills=skills,
        ),
    }


def build_critic_definition(settings: DeepgentSettings) -> AgentDefinition:
    """The critic agent: adversarial final gate with veto authority."""
    return AgentDefinition(
        description="Adversarial final audit of a completed task; can veto success.",
        prompt=_CRITIC_PROMPT,
        tools=["Read", "Grep", "Bash"],
        model=settings.models.opus,
    )


def select_agents(
    settings: DeepgentSettings,
    classification: TaskClassification,
    skill_names: list[str] | None = None,
) -> dict[str, AgentDefinition]:
    """Core agents plus the specialists this task class requires.

    Specialists are loaded on demand (expansion spec A1); the critic is added
    for risk tier >= 2 so it can gate the task. Unknown specialist names in a
    classification are ignored rather than raising.
    """
    agents = build_agent_definitions(settings, skill_names)
    specialists = _specialist_table(settings, skill_names or None)
    for name in classification.specialists:
        definition = specialists.get(name)
        if definition is not None:
            agents[name] = definition
    if classification.risk_tier >= 2:
        agents[CRITIC] = build_critic_definition(settings)
    return agents
