"""Fleet compatibility + performance matrix (#7).

Runs the same benchmark across a heterogeneous board fleet and produces a
per-board compatibility (does it build/run) and performance (latency/fps/power)
matrix, plus matrix-claim candidates the owner can ingest server-side. Wired
into CI, this turns "does the artifact work across our boards" into a gate and
feeds the compatibility matrix flywheel.

Each board's stack (type, l4t) is read from the registry; nothing is assumed.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from deepgent.boards import get_board, open_runner
from deepgent.errors import BoardError, DeepgentError
from deepgent.evals.bench import run_benchmark_on
from deepgent.knowledge.matrix import Claim

_logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class FleetEntry:
    """One board's result for the fleet run."""

    board: str
    stack: dict[str, str]
    ok: bool
    latency_ms: float | None
    fps: float | None
    power_w: float | None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "board": self.board,
            "stack": self.stack,
            "ok": self.ok,
            "latency_ms": self.latency_ms,
            "fps": self.fps,
            "power_w": self.power_w,
            "error": self.error,
        }


@dataclass
class FleetResult:
    """The fleet matrix plus the claim candidates it produces."""

    artifact: str
    run_id: str
    entries: list[FleetEntry] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return bool(self.entries) and all(e.ok for e in self.entries)

    @property
    def ranking(self) -> list[FleetEntry]:
        """Passing boards first, fastest (highest fps) first within each group."""
        return sorted(self.entries, key=lambda e: (0 if e.ok else 1, -(e.fps or 0.0)))

    @property
    def winner(self) -> FleetEntry | None:
        """The best-performing board that passed (highest fps), or None."""
        passing = [e for e in self.entries if e.ok and e.fps is not None]
        return max(passing, key=lambda e: e.fps or 0.0) if passing else None

    def claims(self) -> list[Claim]:
        """A verified compatibility claim per board, keyed by its stack."""
        return [
            Claim(
                stack=dict(entry.stack),
                component=self.artifact,
                works=entry.ok,
                confidence=1.0,
                source=self.run_id,
            )
            for entry in self.entries
        ]

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact": self.artifact,
            "run_id": self.run_id,
            "all_ok": self.all_ok,
            "winner": None if self.winner is None else self.winner.board,
            "entries": [e.to_dict() for e in self.entries],
            "claims": [
                {"stack": c.stack, "component": c.component, "works": c.works}
                for c in self.claims()
            ],
        }

    def render_table(self) -> str:
        header = f"{'board':<14} {'stack':<22} {'ok':>3} {'lat_ms':>8} {'fps':>7} {'power_w':>8}"
        rows = [header, "-" * len(header)]
        for e in self.entries:
            stack = ",".join(f"{k}={v}" for k, v in sorted(e.stack.items())) or "-"
            rows.append(
                f"{e.board:<14} {stack:<22} {'y' if e.ok else 'n':>3} "
                f"{_fmt(e.latency_ms):>8} {_fmt(e.fps):>7} {_fmt(e.power_w):>8}"
            )
        rows.append("-" * len(header))
        rows.append(f"fleet: {'ALL OK' if self.all_ok else 'REGRESSIONS PRESENT'}")
        if self.winner is not None:
            rows.append(f"fastest passing board: {self.winner.board} ({_fmt(self.winner.fps)} fps)")
        return "\n".join(rows) + "\n"

    def persist(self, run_dir: Path) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "fleet-matrix.json").write_text(json.dumps(self.to_dict(), indent=2))
        (run_dir / "fleet-matrix.txt").write_text(self.render_table())
        (run_dir / "matrix-claims.json").write_text(
            json.dumps([c.__dict__ for c in self.claims()], indent=2)
        )


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def _stack_str(stack: dict[str, str]) -> str:
    return ",".join(f"{k}={v}" for k, v in sorted(stack.items()))


def _board_stack(board_type: str, l4t: str | None) -> dict[str, str]:
    stack = {"board": board_type}
    if l4t:
        stack["l4t"] = l4t
    return stack


class FleetRunner:
    """Runs one benchmark across a fleet and builds the matrix."""

    def __init__(self, run_id: str, run_dir: Path) -> None:
        self._run_id = run_id
        self._run_dir = run_dir

    async def run(self, command: str, board_ids: list[str], capture_s: float = 30.0) -> FleetResult:
        result = FleetResult(artifact=command, run_id=self._run_id)
        for board_id in board_ids:
            board = get_board(board_id)
            stack = _board_stack(board.type, board.l4t)
            _logger.info("fleet_board", board=board_id, stack=_stack_str(stack))
            try:
                async with open_runner(board) as runner:
                    bench = await run_benchmark_on(runner, command, capture_s)
                entry = FleetEntry(
                    board=board_id,
                    stack=stack,
                    ok=bench.ok,
                    latency_ms=bench.latency_ms,
                    fps=bench.fps,
                    power_w=bench.power_mean_w,
                    error=None if bench.ok else f"exit {bench.exit_status}",
                )
            except DeepgentError as exc:
                # An unreachable or failing board is a compatibility datapoint,
                # not a reason to abort the whole fleet sweep.
                if not isinstance(exc, BoardError):
                    raise
                entry = FleetEntry(
                    board=board_id,
                    stack=stack,
                    ok=False,
                    latency_ms=None,
                    fps=None,
                    power_w=None,
                    error=str(exc),
                )
            result.entries.append(entry)
        result.persist(self._run_dir)
        return result


def new_run_id() -> str:
    """A run id stamped from the wall clock (callers may override for tests)."""
    return f"fleet-{int(time.time())}"
