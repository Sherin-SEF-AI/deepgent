"""gt-0002 local-GPU CUDA smoke golden: wiring, scoring, registration.

The docker/GPU seams are faked here; the live run against a real GPU is
deferred to a host with nvidia-container-toolkit (CLAUDE.md: hardware paths are
built and fake-tested, live runs deferred to the hardware).
"""

import asyncio
from pathlib import Path

import pytest

from deepgent.boards.metrics import GenericSample
from deepgent.evals import gt0002
from deepgent.evals.runner import IMPLEMENTATIONS
from deepgent.evals.schema import load_golden

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parent.parent


def _fake_samples() -> list[GenericSample]:
    return [
        GenericSample(
            cpu_pct=20.0,
            ram_used_mb=1000.0,
            ram_total_mb=32000.0,
            temp_max_c=55.0,
            gpu_pct=90.0,
            power_w=250.0,
        )
        for _ in range(6)
    ]


def test_gt0002_is_registered_and_parses() -> None:
    assert "bringup/cuda-smoke-local" in IMPLEMENTATIONS
    task = load_golden(REPO_ROOT / "golden" / "gt-0002.yaml")
    assert task.board == "local"
    assert task.task_class == "bringup/cuda-smoke-local"


def test_gt0002_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gt0002, "_cuda_image", lambda: "cuda:test")
    monkeypatch.setattr(gt0002, "sample_once", lambda cpu_window_s=0.05: _fake_samples()[0])
    monkeypatch.setattr(gt0002, "_SAMPLE_INTERVAL_S", 0.01)  # fast sampling for the test

    async def fake_compile(image: str, run_dir: Path, timeout_s: float) -> tuple[int, str]:
        return 0, "BUILD_OK\n"

    async def fake_run(image: str, run_dir: Path, hold: float, timeout_s: float) -> tuple[int, str]:
        # Sustain long enough for several sample ticks, then finish.
        await asyncio.sleep(0.05)
        (run_dir / "kernel_stdout.txt").write_text("vector_add ok: 1048576 elements\n")
        return 0, "runs=42\n"

    monkeypatch.setattr(gt0002, "_compile", fake_compile)
    monkeypatch.setattr(gt0002, "_run_loop", fake_run)

    task = load_golden(REPO_ROOT / "golden" / "gt-0002.yaml")
    metrics = asyncio.run(gt0002.run_gt_0002(task, tmp_path))

    assert metrics["build_ok"] == 1.0
    assert metrics["run_exit_code"] == 0.0
    assert metrics["kernel_ok"] == 1.0
    assert metrics["samples"] >= 1.0
    # Generic telemetry summarized into the tegrastats-shaped keys.
    assert metrics["gr3d_max_pct"] == 90.0
    assert metrics["power_mean_w"] == 250.0

    from deepgent.evals.schema import score

    assert all(c.passed for c in score(metrics, task.success))


def test_gt0002_build_failure_short_circuits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gt0002, "_cuda_image", lambda: "cuda:test")

    async def failing_compile(image: str, run_dir: Path, timeout_s: float) -> tuple[int, str]:
        return 1, "nvcc: not found\n"

    async def unreached_run(*a: object, **k: object) -> tuple[int, str]:
        raise AssertionError("run must not start when the build fails")

    monkeypatch.setattr(gt0002, "_compile", failing_compile)
    monkeypatch.setattr(gt0002, "_run_loop", unreached_run)

    task = load_golden(REPO_ROOT / "golden" / "gt-0002.yaml")
    metrics = asyncio.run(gt0002.run_gt_0002(task, tmp_path))

    assert metrics["build_ok"] == 0.0
    assert metrics["kernel_ok"] == 0.0
