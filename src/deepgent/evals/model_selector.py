"""Power-budget-constrained model selector (#6).

Given a constraint - "<=15W, >=30fps, mAP>=0.4" - benchmark each candidate
model on the target and return only those that provably meet it, each with
evidence, ranked best-first. Turns "which model fits this board" from opinion
into a measured, reproducible answer.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from deepgent.boards import get_board, open_runner
from deepgent.errors import TaskExecutionError
from deepgent.evals.bench import run_benchmark_on

_logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Candidate:
    """One model to evaluate: a name and a benchmark command."""

    name: str
    command: str


@dataclass(frozen=True)
class Constraint:
    """Deployment envelope a candidate must satisfy."""

    max_power_w: float | None = None
    min_fps: float | None = None
    max_latency_ms: float | None = None
    min_accuracy: float | None = None


@dataclass(frozen=True)
class ModelEvaluation:
    """One candidate's measured signals and the pass/fail reasons."""

    name: str
    ok: bool
    latency_ms: float | None
    fps: float | None
    power_w: float | None
    accuracy: float | None
    violations: tuple[str, ...]

    @property
    def meets(self) -> bool:
        return self.ok and not self.violations

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "ok": self.ok,
            "latency_ms": self.latency_ms,
            "fps": self.fps,
            "power_w": self.power_w,
            "accuracy": self.accuracy,
            "meets": self.meets,
            "violations": list(self.violations),
        }


def check_constraint(
    ok: bool,
    latency_ms: float | None,
    fps: float | None,
    power_w: float | None,
    accuracy: float | None,
    constraint: Constraint,
) -> tuple[str, ...]:
    """List every way a measurement violates the constraint (empty = meets)."""
    violations: list[str] = []
    if not ok:
        violations.append("benchmark failed")
    if constraint.max_power_w is not None:
        if power_w is None:
            violations.append("power not measured")
        elif power_w > constraint.max_power_w:
            violations.append(f"power {power_w:.1f}W > {constraint.max_power_w:.1f}W")
    if constraint.min_fps is not None:
        if fps is None:
            violations.append("fps not measured")
        elif fps < constraint.min_fps:
            violations.append(f"fps {fps:.1f} < {constraint.min_fps:.1f}")
    if constraint.max_latency_ms is not None:
        if latency_ms is None:
            violations.append("latency not measured")
        elif latency_ms > constraint.max_latency_ms:
            violations.append(f"latency {latency_ms:.1f}ms > {constraint.max_latency_ms:.1f}ms")
    if constraint.min_accuracy is not None:
        if accuracy is None:
            violations.append("accuracy not measured")
        elif accuracy < constraint.min_accuracy:
            violations.append(f"accuracy {accuracy:.3f} < {constraint.min_accuracy:.3f}")
    return tuple(violations)


def load_candidates(path: Path) -> list[Candidate]:
    """Load a candidate manifest: JSON array of {name, command}."""
    parsed = json.loads(path.read_text())
    if not isinstance(parsed, list):
        raise TaskExecutionError(f"candidate manifest {path} must be a JSON array")
    candidates: list[Candidate] = []
    for item in parsed:
        if "name" not in item or "command" not in item:
            raise TaskExecutionError(f"candidate in {path} missing 'name' or 'command'")
        candidates.append(Candidate(name=str(item["name"]), command=str(item["command"])))
    return candidates


@dataclass
class SelectionResult:
    """All candidate evaluations, ranked meeting-first."""

    constraint: Constraint
    evaluations: list[ModelEvaluation] = field(default_factory=list)

    @property
    def ranked(self) -> list[ModelEvaluation]:
        """Meeting candidates first (by fps desc), then the rest."""

        def key(e: ModelEvaluation) -> tuple[int, float]:
            fps = e.fps if e.fps is not None else 0.0
            return (0 if e.meets else 1, -fps)

        return sorted(self.evaluations, key=key)

    @property
    def winner(self) -> ModelEvaluation | None:
        meeting = [e for e in self.ranked if e.meets]
        return meeting[0] if meeting else None

    def to_dict(self) -> dict[str, object]:
        return {
            "constraint": {
                "max_power_w": self.constraint.max_power_w,
                "min_fps": self.constraint.min_fps,
                "max_latency_ms": self.constraint.max_latency_ms,
                "min_accuracy": self.constraint.min_accuracy,
            },
            "winner": None if self.winner is None else self.winner.name,
            "evaluations": [e.to_dict() for e in self.ranked],
        }

    def render_table(self) -> str:
        header = (
            f"{'model':<20} {'meets':>5} {'lat_ms':>8} {'fps':>7} "
            f"{'power_w':>8} {'acc':>7}  reasons"
        )
        rows = [header, "-" * len(header)]
        for e in self.ranked:
            rows.append(
                f"{e.name:<20} {'yes' if e.meets else 'no':>5} "
                f"{_fmt(e.latency_ms):>8} {_fmt(e.fps):>7} {_fmt(e.power_w):>8} "
                f"{_fmt(e.accuracy):>7}  {'; '.join(e.violations)}"
            )
        rows.append("-" * len(header))
        rows.append(f"winner: {self.winner.name if self.winner else 'none meet the constraint'}")
        return "\n".join(rows) + "\n"

    def persist(self, run_dir: Path) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "model-selection.json").write_text(json.dumps(self.to_dict(), indent=2))
        (run_dir / "model-selection.txt").write_text(self.render_table())


class ModelSelector:
    """Benchmarks candidates on a target and filters by constraint."""

    def __init__(self, board_id: str, run_dir: Path) -> None:
        self._board_id = board_id
        self._run_dir = run_dir

    async def run(
        self,
        candidates: list[Candidate],
        constraint: Constraint,
        capture_s: float = 30.0,
        accuracy_metric: str | None = None,
    ) -> SelectionResult:
        board = get_board(self._board_id)
        result = SelectionResult(constraint=constraint)
        async with open_runner(board) as runner:
            for candidate in candidates:
                _logger.info("model_eval", model=candidate.name)
                bench = await run_benchmark_on(runner, candidate.command, capture_s)
                accuracy = bench.named.get(accuracy_metric) if accuracy_metric else None
                violations = check_constraint(
                    bench.ok, bench.latency_ms, bench.fps, bench.power_mean_w, accuracy, constraint
                )
                result.evaluations.append(
                    ModelEvaluation(
                        name=candidate.name,
                        ok=bench.ok,
                        latency_ms=bench.latency_ms,
                        fps=bench.fps,
                        power_w=bench.power_mean_w,
                        accuracy=accuracy,
                        violations=violations,
                    )
                )
        result.persist(self._run_dir)
        return result


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"
