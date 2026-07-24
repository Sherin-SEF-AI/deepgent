"""Matrix inference engine (#14) and fleet compat+perf matrix (#7).

Reasoning is pure and tested directly; the fleet path uses a runner double so
no boards are required.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, ClassVar

import pytest

import deepgent.evals.fleet as fleet_module
from deepgent.boards import BoardConfig, CommandResult, add_board
from deepgent.evals.fleet import FleetResult, FleetRunner
from deepgent.knowledge.matrix import (
    Claim,
    analyze,
    detect_contradictions,
    hop_distance,
    load_claims,
    load_rules,
    next_to_verify,
    query,
)

pytestmark = pytest.mark.unit


# --- matrix reasoning -------------------------------------------------------


def test_query_direct_verified() -> None:
    claims = [Claim(stack={"l4t": "36.4.3"}, component="trt10", works=True)]
    verdict = query(claims, {"l4t": "36.4.3"}, "trt10")
    assert verdict.works is True and verdict.confidence == pytest.approx(1.0)
    assert verdict.basis.startswith("verified")


def test_query_unknown() -> None:
    verdict = query([], {"l4t": "39.0"}, "trt10")
    assert verdict.works is None and verdict.confidence == 0.0


def test_query_transitive_inference() -> None:
    claims = [Claim(stack={"l4t": "36.4.3"}, component="trt10", works=True)]
    rules = {"l4t": [frozenset({"36.4.3", "36.4.4"})]}
    verdict = query(claims, {"l4t": "36.4.4"}, "trt10", rules, decay=0.7)
    assert verdict.works is True
    assert verdict.confidence == pytest.approx(0.7)
    assert "inferred" in verdict.basis


def test_query_no_inference_without_rule() -> None:
    claims = [Claim(stack={"l4t": "36.4.3"}, component="trt10", works=True)]
    assert query(claims, {"l4t": "36.4.4"}, "trt10").works is None


def test_hop_distance_multi_hop() -> None:
    # Two overlapping groups chain 36.4.3 -> 36.4.4 -> 36.4.5.
    rules = {"l4t": [frozenset({"36.4.3", "36.4.4"}), frozenset({"36.4.4", "36.4.5"})]}
    assert hop_distance(rules, "l4t", "36.4.3", "36.4.3") == 0
    assert hop_distance(rules, "l4t", "36.4.3", "36.4.4") == 1
    assert hop_distance(rules, "l4t", "36.4.3", "36.4.5") == 2
    assert hop_distance(rules, "l4t", "36.4.3", "40.0") is None


def test_query_multi_hop_decays_with_distance() -> None:
    claims = [Claim(stack={"l4t": "36.4.3"}, component="trt10", works=True)]
    rules = {"l4t": [frozenset({"36.4.3", "36.4.4"}), frozenset({"36.4.4", "36.4.5"})]}
    # Two hops away: confidence decays as decay**2.
    verdict = query(claims, {"l4t": "36.4.5"}, "trt10", rules, decay=0.7)
    assert verdict.works is True
    assert verdict.confidence == pytest.approx(0.49)
    assert "2 version-equivalence hop" in verdict.basis


def test_detect_contradictions() -> None:
    claims = [
        Claim(stack={"l4t": "36.4.3"}, component="x", works=True),
        Claim(stack={"l4t": "36.4.3"}, component="x", works=False),
        Claim(stack={"l4t": "36.4.4"}, component="x", works=True),
    ]
    contradictions = detect_contradictions(claims)
    assert len(contradictions) == 1
    assert contradictions[0].stack == {"l4t": "36.4.3"}


def test_next_to_verify_prefers_unknown_connected_cell() -> None:
    claims = [Claim(stack={"l4t": "36.4.3"}, component="x", works=True)]
    rules = {"l4t": [frozenset({"36.4.3", "36.4.4"})]}
    universe = [{"l4t": "36.4.3"}, {"l4t": "36.4.4"}, {"l4t": "40.0"}]
    candidate = next_to_verify(claims, universe, "x", rules)
    assert candidate is not None
    # 36.4.3 is verified (skipped); 40.0 is fully unknown (highest uncertainty).
    assert candidate.stack == {"l4t": "40.0"}


def test_analyze_combines() -> None:
    claims = [
        Claim(stack={"l4t": "36.4.3"}, component="x", works=True),
        Claim(stack={"l4t": "36.4.3"}, component="x", works=False),
    ]
    result = analyze(claims, "x", universe=[{"l4t": "40.0"}])
    assert len(result.contradictions) == 1
    assert result.next_verify is not None
    assert "contradictions" in result.render()


def test_load_claims_and_rules() -> None:
    claims = load_claims(
        json.dumps([{"stack": {"l4t": "36.4.3"}, "component": "x", "works": True}])
    )
    assert claims[0].component == "x" and claims[0].works is True
    rules = load_rules(json.dumps({"l4t": [["36.4.3", "36.4.4"]]}))
    assert rules["l4t"][0] == frozenset({"36.4.3", "36.4.4"})


# --- fleet matrix -----------------------------------------------------------


@pytest.fixture
def fleet_boards(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    for bid, l4t in (("agx", "36.4.3"), ("orin-nx", "36.4.4")):
        add_board(
            BoardConfig(
                id=bid,
                host=f"198.51.100.{len(bid)}",
                ssh_user="nvidia",
                key_path=Path("~/.ssh/k"),
                type="jetson",
                l4t=l4t,
            )
        )


class _FakeFleetRunner:
    results: ClassVar[dict[str, tuple[int, str]]] = {}

    def __init__(self, board: BoardConfig) -> None:
        self._board = board

    async def __aenter__(self) -> "_FakeFleetRunner":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def run(self, command: str, timeout_s: float = 60.0) -> CommandResult:
        exit_status, out = _FakeFleetRunner.results.get(
            self._board.id, (0, "latency 5 ms\n40 fps\n")
        )
        return CommandResult(command, exit_status, out, "", False)

    async def capture_metrics(self, duration_s: float, interval_ms: int = 500) -> dict[str, float]:
        return {"power_mean_w": 10.0}


def test_fleet_matrix_end_to_end(
    fleet_boards: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeFleetRunner.results = {
        "agx": (0, "latency 5 ms\n40 fps\n"),
        "orin-nx": (1, "boom\n"),  # regression on this board
    }
    monkeypatch.setattr(fleet_module, "open_runner", lambda b: _FakeFleetRunner(b))
    runner = FleetRunner("fleet-test", tmp_path / "run")
    result = asyncio.run(runner.run("./bench", ["agx", "orin-nx"], 1.0))
    assert isinstance(result, FleetResult)
    assert result.all_ok is False
    claims = result.claims()
    assert len(claims) == 2
    assert claims[0].stack == {"board": "jetson", "l4t": "36.4.3"}
    assert claims[0].works is True and claims[1].works is False
    assert (tmp_path / "run" / "fleet-matrix.json").is_file()
    assert (tmp_path / "run" / "matrix-claims.json").is_file()


# --- WO-42 fleet winner/ranking ---------------------------------------------


def test_fleet_winner_and_ranking() -> None:
    from deepgent.evals.fleet import FleetEntry, FleetResult

    result = FleetResult(artifact="./b", run_id="r")
    result.entries = [
        FleetEntry("slow", {"board": "a"}, ok=True, latency_ms=20, fps=25, power_w=10),
        FleetEntry("fast", {"board": "b"}, ok=True, latency_ms=10, fps=60, power_w=12),
        FleetEntry("broken", {"board": "c"}, ok=False, latency_ms=None, fps=None, power_w=None),
    ]
    assert result.winner is not None and result.winner.board == "fast"
    assert [e.board for e in result.ranking] == ["fast", "slow", "broken"]
    assert result.to_dict()["winner"] == "fast"
