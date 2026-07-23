"""Controllers for the remaining surfaces: containers, evals, soak,
differential, knowledge, and skills. Qt-free.

Sync, CPU/subprocess-heavy operations (container build, golden run) are
offloaded to a thread so the qasync UI loop never blocks; naturally-async
board and network work runs directly on the loop.
"""

import asyncio
from pathlib import Path
from typing import Any

from deepgent.config import load_settings
from deepgent.containers import ContainerBuilder, load_jp6_spec
from deepgent.evals import GoldenRunResult, run_golden
from deepgent.evals.differential import DifferentialResult, DifferentialRunner
from deepgent.evals.soak import AnomalyRules, SoakResult, SoakRunner, default_phases
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


class SkillsController:
    def packs(self) -> list[SkillPack]:
        return list_skills()
