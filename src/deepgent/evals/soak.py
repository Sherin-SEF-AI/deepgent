"""deepgent soak: endurance orchestration on a target board (Tier 1).

Runs a phased workload schedule for hours to days while sampling tegrastats
in windows. The first anomaly triggers a snapshot (dmesg tail, the offending
tegrastats window, workload output) into the run directory; the run then
either stops (default) or continues collecting. Ends with a survival report.

Anomaly rules are deterministic thresholds; nothing here is judged by a
model. "Thermal cycling" is exercised as alternating load/idle phases; a
climate chamber, when present, is driven externally and reflected in the
tj ceiling.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from deepgent.boards import BoardRunner, get_board, parse_capture
from deepgent.errors import BoardError

_logger = structlog.get_logger(__name__)

_WINDOW_S = 60.0
_TEGRASTATS_INTERVAL_MS = 1000
_DMESG_TAIL_LINES = 200


@dataclass(frozen=True)
class SoakPhase:
    """One schedule entry: a workload (or idle) held for a duration."""

    name: str
    duration_s: float
    command: str | None = None  # None = idle observation phase


@dataclass(frozen=True)
class AnomalyRules:
    """Deterministic thresholds that end a healthy soak."""

    tj_max_c: float = 95.0
    ram_used_max_mb: float | None = None
    min_samples_per_window: int = 10
    workload_must_succeed: bool = True


@dataclass(frozen=True)
class Anomaly:
    """First detected rule violation."""

    ts: float
    phase: str
    rule: str
    detail: str


@dataclass
class SoakResult:
    """Survival report data for one soak run."""

    board: str
    started_ts: float
    planned_s: float
    survived_s: float = 0.0
    windows: int = 0
    phases_completed: list[str] = field(default_factory=list)
    tj_max_c: float | None = None
    power_max_w: float | None = None
    ram_used_max_mb: float | None = None
    anomaly: Anomaly | None = None

    @property
    def survived(self) -> bool:
        return self.anomaly is None

    def to_dict(self) -> dict[str, object]:
        return {
            "board": self.board,
            "planned_s": self.planned_s,
            "survived_s": self.survived_s,
            "windows": self.windows,
            "phases_completed": self.phases_completed,
            "tj_max_c": self.tj_max_c,
            "power_max_w": self.power_max_w,
            "ram_used_max_mb": self.ram_used_max_mb,
            "survived": self.survived,
            "anomaly": None
            if self.anomaly is None
            else {
                "phase": self.anomaly.phase,
                "rule": self.anomaly.rule,
                "detail": self.anomaly.detail,
                "at_s": self.anomaly.ts - self.started_ts,
            },
        }

    def render_report(self) -> str:
        lines = [
            "# soak survival report",
            "",
            f"board: {self.board}",
            f"planned: {self.planned_s / 3600.0:.1f}h",
            f"survived: {self.survived_s / 3600.0:.2f}h "
            f"({self.survived_s / self.planned_s:.0%} of plan)"
            if self.planned_s
            else "survived: 0h",
            f"windows sampled: {self.windows}",
            f"phases completed: {', '.join(self.phases_completed) or 'none'}",
            f"tj max: {self.tj_max_c:.1f}C" if self.tj_max_c is not None else "tj max: n/a",
            f"power max: {self.power_max_w:.1f}W"
            if self.power_max_w is not None
            else "power max: n/a",
        ]
        if self.anomaly is None:
            lines.append("")
            lines.append("RESULT: SURVIVED")
        else:
            lines += [
                "",
                "RESULT: ANOMALY",
                f"phase: {self.anomaly.phase}",
                f"rule: {self.anomaly.rule}",
                f"detail: {self.anomaly.detail}",
                f"at: {(self.anomaly.ts - self.started_ts) / 3600.0:.2f}h into the run",
            ]
        return "\n".join(lines) + "\n"


def check_window(
    metrics: dict[str, float], rules: AnomalyRules, phase: str, ts: float
) -> Anomaly | None:
    """Apply anomaly rules to one window's summary metrics."""
    samples = metrics.get("tegrastats_samples", 0.0)
    if samples < rules.min_samples_per_window:
        return Anomaly(
            ts=ts,
            phase=phase,
            rule="telemetry_gap",
            detail=f"only {samples:g} tegrastats samples in the window "
            f"(minimum {rules.min_samples_per_window}); board may have hung",
        )
    tj = metrics.get("tj_max_c")
    if tj is not None and tj > rules.tj_max_c:
        return Anomaly(
            ts=ts,
            phase=phase,
            rule="thermal_ceiling",
            detail=f"tj reached {tj:.1f}C (ceiling {rules.tj_max_c:.1f}C)",
        )
    ram = metrics.get("ram_used_max_mb")
    if rules.ram_used_max_mb is not None and ram is not None and ram > rules.ram_used_max_mb:
        return Anomaly(
            ts=ts,
            phase=phase,
            rule="ram_ceiling",
            detail=f"RAM reached {ram:.0f}MB (ceiling {rules.ram_used_max_mb:.0f}MB)",
        )
    return None


def default_phases(total_s: float, workload: str | None) -> list[SoakPhase]:
    """Alternating load/idle cycle filling the planned duration."""
    if workload is None:
        return [SoakPhase(name="observe", duration_s=total_s)]
    phases: list[SoakPhase] = []
    cycle = 0
    remaining = total_s
    while remaining > 0:
        load_s = min(1800.0, remaining)
        phases.append(SoakPhase(name=f"load-{cycle}", duration_s=load_s, command=workload))
        remaining -= load_s
        if remaining <= 0:
            break
        idle_s = min(300.0, remaining)
        phases.append(SoakPhase(name=f"cool-{cycle}", duration_s=idle_s))
        remaining -= idle_s
        cycle += 1
    return phases


class SoakRunner:
    """Drives one soak run against a registered board."""

    def __init__(
        self,
        board_id: str,
        run_dir: Path,
        rules: AnomalyRules | None = None,
        window_s: float = _WINDOW_S,
    ) -> None:
        self._board_id = board_id
        self._run_dir = run_dir
        self._rules = rules if rules is not None else AnomalyRules()
        self._window_s = window_s

    async def _snapshot(self, runner: BoardRunner, window_raw: str, label: str) -> None:
        """Persist the anomaly evidence; failures to snapshot never mask the
        anomaly itself."""
        (self._run_dir / f"{label}-tegrastats.txt").write_text(window_raw)
        try:
            dmesg = await runner.run(
                f"dmesg --time-format iso 2>/dev/null | tail -n {_DMESG_TAIL_LINES} "
                f"|| dmesg | tail -n {_DMESG_TAIL_LINES}",
                timeout_s=30,
            )
            (self._run_dir / f"{label}-dmesg.txt").write_text(dmesg.stdout + dmesg.stderr)
        except BoardError as exc:
            (self._run_dir / f"{label}-dmesg.txt").write_text(f"dmesg capture failed: {exc}\n")

    async def run(self, phases: list[SoakPhase]) -> SoakResult:
        board = get_board(self._board_id)
        planned_s = sum(phase.duration_s for phase in phases)
        result = SoakResult(board=self._board_id, started_ts=time.time(), planned_s=planned_s)
        log = _logger.bind(board=self._board_id, planned_s=planned_s)
        log.info("soak_started", phases=len(phases))

        async with BoardRunner(board) as runner:
            for phase in phases:
                log.info("soak_phase", phase=phase.name, duration_s=phase.duration_s)
                workload_task: asyncio.Task[object] | None = None
                if phase.command is not None:
                    workload_task = asyncio.create_task(
                        runner.run(phase.command, timeout_s=phase.duration_s + 60)
                    )
                phase_end = time.time() + phase.duration_s
                while time.time() < phase_end:
                    window = min(self._window_s, max(phase_end - time.time(), 1.0))
                    raw = await runner.capture_tegrastats(window, _TEGRASTATS_INTERVAL_MS)
                    metrics = parse_capture(raw).summary_metrics(
                        interval_ms=_TEGRASTATS_INTERVAL_MS
                    )
                    result.windows += 1
                    result.survived_s = time.time() - result.started_ts
                    tj = metrics.get("tj_max_c")
                    if tj is not None:
                        result.tj_max_c = max(result.tj_max_c or 0.0, tj)
                    power = metrics.get("power_max_w")
                    if power is not None:
                        result.power_max_w = max(result.power_max_w or 0.0, power)
                    ram = metrics.get("ram_used_max_mb")
                    if ram is not None:
                        result.ram_used_max_mb = max(result.ram_used_max_mb or 0.0, ram)

                    anomaly = check_window(metrics, self._rules, phase.name, time.time())
                    if anomaly is not None:
                        result.anomaly = anomaly
                        log.warning("soak_anomaly", rule=anomaly.rule, detail=anomaly.detail)
                        await self._snapshot(runner, raw, "anomaly")
                        if workload_task is not None:
                            workload_task.cancel()
                        self._persist(result)
                        return result

                if workload_task is not None:
                    workload_result = await workload_task
                    exit_status = getattr(workload_result, "exit_status", 0)
                    timed_out = bool(getattr(workload_result, "timed_out", False))
                    stdout = str(getattr(workload_result, "stdout", ""))
                    stderr = str(getattr(workload_result, "stderr", ""))
                    (self._run_dir / f"{phase.name}-workload.txt").write_text(stdout + stderr)
                    # The phase-long watchdog expiring is the expected way a
                    # continuous workload ends; a real failure is nonzero
                    # exit without timeout.
                    if self._rules.workload_must_succeed and not timed_out and exit_status != 0:
                        result.anomaly = Anomaly(
                            ts=time.time(),
                            phase=phase.name,
                            rule="workload_failed",
                            detail=f"workload exited {exit_status}: {stderr[-500:]}",
                        )
                        await self._snapshot(runner, "", "anomaly")
                        self._persist(result)
                        return result
                result.phases_completed.append(phase.name)

        result.survived_s = time.time() - result.started_ts
        self._persist(result)
        log.info("soak_finished", survived=result.survived)
        return result

    def _persist(self, result: SoakResult) -> None:
        (self._run_dir / "soak.json").write_text(json.dumps(result.to_dict(), indent=2))
        (self._run_dir / "survival-report.md").write_text(result.render_report())
