"""Controllers for the remaining surfaces: containers, evals, soak,
differential, knowledge, and skills. Qt-free.

Sync, CPU/subprocess-heavy operations (container build, golden run) are
offloaded to a thread so the qasync UI loop never blocks; naturally-async
board and network work runs directly on the loop.
"""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from deepgent.evals.accuracy import AccuracyResult
    from deepgent.evals.model_selector import Constraint, SelectionResult
    from deepgent.evals.quant_sweep import QuantSweepResult

from deepgent.config import load_settings
from deepgent.containers import ContainerBuilder, load_jp6_spec
from deepgent.evals import GoldenRunResult, create_run_dir, run_golden
from deepgent.evals.differential import DifferentialResult, DifferentialRunner
from deepgent.evals.latency_trace import LatencyTrace, LatencyTracer
from deepgent.evals.soak import AnomalyRules, SoakResult, SoakRunner, default_phases
from deepgent.evals.thermal_envelope import (
    ThermalEnvelopeProfiler,
    ThermalEnvelopeResult,
    parse_modes,
)
from deepgent.knowledge import SkillPack, build_rag_client, list_skills, triage
from deepgent.knowledge.products import TriageResult


class ContainersController:
    async def build(self, smoke: bool, on_status: Any = None) -> str:
        """Build the jp6 image (and optionally smoke-check) off the UI loop."""
        builder = ContainerBuilder(load_jp6_spec())

        def _work() -> str:
            builder.build()
            if smoke:
                builder.cuda_smoke()
            return builder.spec.image_tag

        return await asyncio.to_thread(_work)

    def image_tag(self) -> str:
        return ContainerBuilder(load_jp6_spec()).spec.image_tag


class EvalsController:
    def golden_ids(self, project_root: Path | None = None) -> list[str]:
        root = project_root if project_root is not None else Path.cwd()
        golden_dir = root / "golden"
        if not golden_dir.is_dir():
            return []
        return sorted(p.stem for p in golden_dir.glob("*.yaml"))

    async def run(self, task_id: str, project_root: Path | None = None) -> GoldenRunResult:
        root = project_root if project_root is not None else Path.cwd()
        return await run_golden(task_id, root)

    async def soak(
        self, board: str, hours: float, workload: str | None, run_dir: Path, tj_max: float = 95.0
    ) -> SoakResult:
        runner = SoakRunner(board, run_dir, rules=AnomalyRules(tj_max_c=tj_max))
        return await runner.run(default_phases(hours * 3600.0, workload))

    async def differential(
        self,
        artifact: Path,
        board_ids: list[str],
        command: str,
        project_root: Path | None = None,
    ) -> DifferentialResult:
        root = project_root if project_root is not None else Path.cwd()
        return await DifferentialRunner(root).run(artifact, board_ids, command)


class KnowledgeController:
    async def triage(self, symptom: str, hw: str | None = None) -> TriageResult:
        client = build_rag_client(load_settings())
        try:
            return await triage(client, symptom, hw=hw)
        finally:
            await client.aclose()


class ProfilingController:
    """Thermal-envelope (#3) and glass-to-glass latency (#4) profiling."""

    async def thermal(
        self,
        board: str,
        workload: str,
        hold_s: float,
        modes: str | None,
        tj_max: float,
        window_s: float,
        project_root: Path | None = None,
    ) -> ThermalEnvelopeResult:
        root = project_root if project_root is not None else Path.cwd()
        mode_list = parse_modes(modes) if modes else None
        run_dir = create_run_dir(f"thermal-{board}", root)
        profiler = ThermalEnvelopeProfiler(board, run_dir, window_s=window_s)
        return await profiler.run(workload, hold_s, mode_list, tj_ceiling_c=tj_max)

    async def latency(
        self,
        board: str,
        command: str,
        budget_ms: float | None,
        capture_s: float,
        project_root: Path | None = None,
    ) -> LatencyTrace:
        root = project_root if project_root is not None else Path.cwd()
        run_dir = create_run_dir(f"latency-{board}", root)
        tracer = LatencyTracer(board, run_dir)
        return await tracer.run(command, budget_ms=budget_ms, capture_s=capture_s)


class ModelsController:
    """Quantization sweep (#1), accuracy gate (#2), model selection (#6)."""

    async def quant_sweep(
        self,
        board: str,
        command: str,
        precisions: list[str],
        batches: list[int],
        devices: list[str],
        accuracy_metric: str | None = None,
        capture_s: float = 30.0,
        project_root: Path | None = None,
    ) -> "QuantSweepResult":
        from deepgent.evals.quant_sweep import QuantSweepRunner, expand_grid

        root = project_root if project_root is not None else Path.cwd()
        configs = expand_grid(precisions, batches, devices)
        run_dir = create_run_dir(f"quant-{board}", root)
        return await QuantSweepRunner(board, run_dir).run(
            command, configs, capture_s, accuracy_metric
        )

    async def accuracy_gate(
        self,
        board: str,
        command: str,
        metric: str,
        baseline: float | None,
        tolerance: float = 0.0,
        capture_s: float = 120.0,
    ) -> "AccuracyResult":
        from deepgent.evals.accuracy import AccuracyGate

        return await AccuracyGate().run(board, command, metric, baseline, tolerance, capture_s)

    async def select_model(
        self,
        board: str,
        manifest: Path,
        constraint: "Constraint",
        accuracy_metric: str | None = None,
        capture_s: float = 30.0,
        project_root: Path | None = None,
    ) -> "SelectionResult":
        from deepgent.evals.model_selector import ModelSelector, load_candidates

        root = project_root if project_root is not None else Path.cwd()
        candidates = load_candidates(manifest)
        run_dir = create_run_dir(f"select-{board}", root)
        return await ModelSelector(board, run_dir).run(
            candidates, constraint, capture_s, accuracy_metric
        )


class SkillsController:
    def packs(self) -> list[SkillPack]:
        return list_skills()
