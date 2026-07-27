"""One-shot task orchestration over the Claude Agent SDK."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from deepgent.telemetry import TelemetryStore
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)
from claude_agent_sdk.types import McpServerConfig

from deepgent.agents import build_agent_definitions, select_agents
from deepgent.config import DeepgentSettings
from deepgent.core.budget import BudgetTracker
from deepgent.core.classifier import TaskClassification, classify
from deepgent.errors import TaskExecutionError

_logger = structlog.get_logger(__name__)

# Seam for tests: monkeypatch deepgent.core.orchestrator._run_query.
_run_query = query

MAIN_SESSION_TOOLS = [
    "Task",
    "Read",
    "Glob",
    "Grep",
    "Bash",
    "Write",
    "Edit",
]


@dataclass(frozen=True)
class TaskEvent:
    """One structured activity event during a task (a tool use or result)."""

    kind: str  # "tool_use" | "tool_result"
    name: str  # tool name (Write, Edit, Bash, ...)
    detail: str  # file path / command / truncated output
    is_error: bool = False


def _summarize_tool_input(name: str, tool_input: dict[str, object]) -> str:
    """A one-line summary of a tool call for the activity feed."""
    if name in ("Write", "Edit") and "file_path" in tool_input:
        return str(tool_input["file_path"])
    if name == "Bash" and "command" in tool_input:
        return str(tool_input["command"])[:200]
    if name in ("Read", "Glob", "Grep"):
        target = tool_input.get("file_path") or tool_input.get("pattern") or tool_input.get("path")
        return str(target) if target is not None else ""
    return str(tool_input)[:200]


def _result_text(content: object) -> str:
    """A truncated text summary of a tool result's content."""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        parts = [
            str(block.get("text", "")) if isinstance(block, dict) else str(block)
            for block in content
        ]
        text = "\n".join(p for p in parts if p)
    else:
        text = str(content)
    text = text.strip()
    return text if len(text) <= 500 else text[:500] + " ..."


@dataclass(frozen=True)
class TaskOutcome:
    """Result of a one-shot task run."""

    result: str
    is_error: bool
    num_turns: int
    total_cost_usd: float | None
    session_id: str


@dataclass(frozen=True)
class CriticVerdict:
    """The critic's ruling on a completed task (expansion spec A1)."""

    vetoed: bool
    reason: str


# The critic must terminate its reply with one of these lines.
_VERDICT_RE = re.compile(r"CRITIC_VERDICT:\s*(PASS|VETO)(?::\s*(.*))?", re.IGNORECASE)

_CRITIC_INSTRUCTION = """\
You are the deepgent critic, the final adversarial gate. Audit the working-tree
diff for the task below. Run `git diff` (and `git status`) to see the change,
read any files you need, and judge whether it is production-grade per the prime
directives: no stubs, placeholders, mock data, simulated results, TODO/FIXME,
silent fallbacks, unreachable or untested branches, fabricated hardware facts,
or claims of hardware behavior not measured on hardware. Do not edit anything.

End your reply with exactly one line and nothing after it:
  CRITIC_VERDICT: PASS
or
  CRITIC_VERDICT: VETO: <one-line reason>
When in doubt, veto.

Task under audit:
{task}
"""


def parse_critic_verdict(text: str) -> CriticVerdict:
    """Parse the critic's terminal verdict line.

    A missing or unparseable verdict is treated as PASS (the critic is
    fail-open on parse so a flaky audit never blocks a legitimate task); the
    caller logs the ambiguity. An explicit VETO always blocks.
    """
    matches = list(_VERDICT_RE.finditer(text or ""))
    if not matches:
        return CriticVerdict(vetoed=False, reason="no explicit verdict; treated as pass")
    last = matches[-1]
    if last.group(1).upper() == "VETO":
        reason = (last.group(2) or "").strip() or "critic vetoed without a stated reason"
        return CriticVerdict(vetoed=True, reason=reason)
    return CriticVerdict(vetoed=False, reason="")


class Orchestrator:
    """Runs tasks through query() with explicitly pinned session options."""

    def __init__(
        self,
        settings: DeepgentSettings,
        cwd: Path,
        max_turns: int | None = None,
    ) -> None:
        self._settings = settings
        self._cwd = cwd
        self._max_turns = max_turns if max_turns is not None else settings.max_turns
        self._store: TelemetryStore | None = None

    def _telemetry_store(self) -> "TelemetryStore | None":
        from deepgent.telemetry import TelemetryStore

        if not self._settings.telemetry_enabled:
            return None
        if self._store is None:
            self._store = TelemetryStore()
        return self._store

    def _budget_calibration(self) -> float:
        """Learned billed/estimate ratio for budget_guard; 1.0 without history."""
        store = self._telemetry_store()
        return store.estimate_calibration() if store is not None else 1.0

    async def _with_premortem(self, task: str) -> str:
        """Prepend a corpus/matrix pre-mortem to the task (#11).

        Best-effort: any failure to reach the knowledge layer leaves the task
        unchanged, so a missing or unconfigured server never blocks a run.
        """
        if not self._settings.premortem_enabled:
            return task
        from deepgent.knowledge import build_rag_client
        from deepgent.knowledge.premortem import premortem

        try:
            client = build_rag_client(self._settings)
        except Exception as exc:  # knowledge layer unconfigured or unavailable
            _logger.debug("premortem_skipped", reason=str(exc))
            return task
        try:
            report = await premortem(client, task, hw=self._settings.default_board)
            prelude = report.plan_prelude()
        except Exception as exc:  # best-effort enrichment, never fatal
            _logger.debug("premortem_failed", reason=str(exc))
            return task
        finally:
            await client.aclose()
        if not prelude:
            return task
        _logger.info("premortem_applied", risks=len(report.risks))
        return f"{prelude}\n{task}"

    def _resolve_model(self, tier: str) -> str:
        """Map a classifier model tier to the pinned model id (section 9)."""
        tiers = self._settings.models
        return {"opus": tiers.opus, "sonnet": tiers.sonnet, "haiku": tiers.haiku}.get(
            tier, tiers.sonnet
        )

    def build_options(
        self,
        tracker: BudgetTracker | None = None,
        classification: TaskClassification | None = None,
    ) -> ClaudeAgentOptions:
        """Session options with every field from CLAUDE.md section 7 set
        explicitly; nothing relies on ambient defaults.

        With a classification, specialists are loaded for the task class and
        the model tier is routed accordingly (section 9). Without one, the
        five core agents run on the sonnet tier (the pre-classifier default).
        """
        # Deferred import: hooks depend on core.budget, so a module-level
        # import here would make deepgent.hooks unimportable on its own.
        from deepgent.boards import build_board_farm_server
        from deepgent.hooks import build_hooks
        from deepgent.knowledge import build_knowledge_server, sync_skills

        if tracker is None:
            tracker = BudgetTracker(self._settings)
        # Context assembly (lifecycle step 2): resolve skill packs into the
        # session project so the harness discovers them via setting_sources.
        skill_names = sync_skills(self._cwd)
        # Only hardware-runner touches boards, only researcher/architect get
        # knowledge tools (section 8); safety_gate covers destructive board
        # ops and fact_guard enforces provenance on knowledge answers.
        mcp_servers: dict[str, McpServerConfig] = {"board_farm": build_board_farm_server()}
        knowledge_server = build_knowledge_server(self._settings)
        if knowledge_server is not None:
            mcp_servers["knowledge"] = knowledge_server
        if classification is None:
            agents = build_agent_definitions(self._settings, skill_names)
            model = self._settings.models.sonnet
        else:
            agents = select_agents(self._settings, classification, skill_names)
            model = self._resolve_model(classification.model_tier)
        return ClaudeAgentOptions(
            allowed_tools=list(MAIN_SESSION_TOOLS),
            disallowed_tools=[],
            permission_mode=self._settings.permission_mode,
            mcp_servers=mcp_servers,
            agents=agents,
            hooks=build_hooks(self._settings, tracker, self._telemetry_store()),
            setting_sources=["project"],
            cwd=self._cwd,
            max_turns=self._max_turns,
            skills=skill_names or None,
            model=model,
        )

    async def run_task(
        self,
        task: str,
        on_text: Callable[[str], None] | None = None,
        on_event: Callable[[TaskEvent], None] | None = None,
    ) -> TaskOutcome:
        """Run a single task to completion and return its outcome.

        on_text, when given, is called with each assistant text block as it
        streams. on_event, when given, is called with each tool use and tool
        result, so a UI can show the agent editing files and running commands.
        """
        import time

        tracker = BudgetTracker(self._settings, calibration=self._budget_calibration())
        classification = classify(task)
        options = self.build_options(tracker, classification)
        log = _logger.bind(cwd=str(self._cwd), model=options.model)
        log.info(
            "task_started",
            task=task,
            task_class=classification.task_class,
            risk_tier=classification.risk_tier,
            specialists=list(classification.specialists),
        )
        started = time.monotonic()

        prompt = await self._with_premortem(task)

        result: ResultMessage | None = None
        tool_names: dict[str, str] = {}
        async for message in _run_query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                tracker.record_usage(message.model, message.usage)
                for block in message.content:
                    if isinstance(block, TextBlock):
                        log.debug("assistant_text", text=block.text)
                        if on_text is not None:
                            on_text(block.text)
                    elif isinstance(block, ToolUseBlock):
                        tool_names[block.id] = block.name
                        if on_event is not None:
                            on_event(
                                TaskEvent(
                                    kind="tool_use",
                                    name=block.name,
                                    detail=_summarize_tool_input(block.name, block.input),
                                )
                            )
            elif isinstance(message, UserMessage) and on_event is not None:
                blocks = message.content if isinstance(message.content, list) else []
                for block in blocks:
                    if isinstance(block, ToolResultBlock):
                        on_event(
                            TaskEvent(
                                kind="tool_result",
                                name=tool_names.get(block.tool_use_id, "tool"),
                                detail=_result_text(block.content),
                                is_error=bool(block.is_error),
                            )
                        )
            elif isinstance(message, ResultMessage):
                result = message

        if result is None:
            raise TaskExecutionError(
                "task ended without a result message; the session was likely "
                "interrupted before completion"
            )

        # critic gate (expansion spec A1): a veto on a risk-tier >= 2 task
        # turns a successful run into an error. It never rescues a failed run.
        result_text = result.result or ""
        is_error = result.is_error
        if not result.is_error and self._settings.critic_enabled and classification.risk_tier >= 2:
            verdict = await self._run_critic(task, tracker)
            if verdict.vetoed:
                is_error = True
                result_text = f"{result_text}\n\nCRITIC VETO: {verdict.reason}".strip()
                log.warning("critic_veto", reason=verdict.reason)
            else:
                log.info("critic_pass")

        log.info(
            "task_finished",
            is_error=is_error,
            num_turns=result.num_turns,
            total_cost_usd=result.total_cost_usd,
        )
        self._record_task(
            result,
            tracker,
            time.monotonic() - started,
            task_class=classification.task_class,
            is_error=is_error,
        )
        return TaskOutcome(
            result=result_text,
            is_error=is_error,
            num_turns=result.num_turns,
            total_cost_usd=result.total_cost_usd,
            session_id=result.session_id,
        )

    def _critic_options(self, tracker: BudgetTracker) -> ClaudeAgentOptions:
        """Read-only session for the critic pass: opus tier, no subagents, only
        the tools needed to inspect the working-tree diff."""
        from deepgent.hooks import build_hooks

        return ClaudeAgentOptions(
            allowed_tools=["Read", "Grep", "Bash"],
            disallowed_tools=[],
            permission_mode=self._settings.permission_mode,
            mcp_servers={},
            agents={},
            hooks=build_hooks(self._settings, tracker, self._telemetry_store()),
            setting_sources=["project"],
            cwd=self._cwd,
            max_turns=min(self._max_turns, 12),
            model=self._settings.models.opus,
        )

    async def _run_critic(self, task: str, tracker: BudgetTracker) -> CriticVerdict:
        """Run the adversarial critic pass and parse its verdict."""
        options = self._critic_options(tracker)
        prompt = _CRITIC_INSTRUCTION.format(task=task)
        result: ResultMessage | None = None
        async for message in _run_query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                tracker.record_usage(message.model, message.usage)
            elif isinstance(message, ResultMessage):
                result = message
        if result is None:
            _logger.warning("critic_no_result")
            return CriticVerdict(vetoed=False, reason="critic produced no result; treated as pass")
        return parse_critic_verdict(result.result or "")

    def _record_task(
        self,
        result: ResultMessage,
        tracker: BudgetTracker,
        wall_s: float,
        task_class: str = "task/oneshot",
        is_error: bool | None = None,
    ) -> None:
        """Every task emits telemetry (section 1); best-effort, never fatal."""
        from deepgent.telemetry import TaskRecord

        store = self._telemetry_store()
        if store is None:
            return
        import time

        task_error = result.is_error if is_error is None else is_error
        store.record_task(
            TaskRecord(
                id=result.session_id,
                ts=time.time(),
                # Real class from the deterministic intake classifier; a critic
                # veto is reflected via is_error below.
                task_class=task_class,
                board=self._settings.default_board,
                model_mix=tracker.model_mix,
                tokens=tracker.total_tokens,
                usd=result.total_cost_usd,
                est_usd=tracker.spent_usd,
                wall_s=wall_s,
                loops=result.num_turns,
                outcome="error" if task_error else "success",
            )
        )
