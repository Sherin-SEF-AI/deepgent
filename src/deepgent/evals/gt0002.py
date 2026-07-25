"""gt-0002: build and run the trivial CUDA kernel on a local discrete GPU.

The x86 counterpart to gt-0001. Where gt-0001 cross-compiles for aarch64 and
deploys to a Jetson over SSH, gt-0002 compiles and runs the same kernel in a
CUDA container on the host GPU (docker --gpus all) and captures generic
nvidia-smi telemetry with the same summary shape as the tegrastats parser.

The kernel is compiled to PTX (a virtual arch) so the host driver JITs it to
whatever GPU is installed, including archs newer than the toolkit image. This
is a real on-hardware golden: it runs the kernel on the actual GPU and scores
measured metrics, never simulated ones.
"""

import asyncio
import time
from pathlib import Path

import structlog

from deepgent.boards.metrics import sample_once, summarize_generic
from deepgent.containers.build import SMOKE_DIR, SMOKE_SOURCE
from deepgent.errors import GoldenError
from deepgent.evals.schema import GoldenTask

_logger = structlog.get_logger(__name__)

_KERNEL_OK_MARKER = "vector_add ok"
_SAMPLE_INTERVAL_S = 0.5
_HOLD_S = 5.0  # sustain the kernel long enough for several telemetry samples
# PTX virtual archs; the host driver JITs the highest usable one to the GPU.
_GENCODE = [
    "-gencode",
    "arch=compute_75,code=compute_75",
    "-gencode",
    "arch=compute_90,code=compute_90",
]


def _cuda_image() -> str:
    from deepgent.config import load_versions

    return str(load_versions()["local"]["cuda_image"])


async def _docker(args: list[str], timeout_s: float) -> tuple[int, str]:
    """Run `docker <args>`, returning (exit_code, combined output)."""
    proc = await asyncio.create_subprocess_exec(
        "docker",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except TimeoutError:
        proc.kill()
        cmd = " ".join(args)
        raise GoldenError(f"docker timed out after {timeout_s:g}s: docker {cmd}") from None
    return proc.returncode or 0, stdout.decode(errors="replace")


async def _compile(image: str, run_dir: Path, timeout_s: float) -> tuple[int, str]:
    """Compile vector_add.cu to /out/vector_add inside the CUDA image."""
    nvcc = " ".join(["nvcc", *_GENCODE, "-o", "/out/vector_add", f"/src/{SMOKE_SOURCE}"])
    return await _docker(
        [
            "run",
            "--rm",
            "-v",
            f"{SMOKE_DIR}:/src:ro",
            "-v",
            f"{run_dir}:/out",
            image,
            "bash",
            "-lc",
            f"{nvcc} && echo BUILD_OK",
        ],
        timeout_s,
    )


async def _run_loop(image: str, run_dir: Path, hold_s: float, timeout_s: float) -> tuple[int, str]:
    """Run the compiled kernel on the GPU in a loop for hold_s seconds."""
    loop = (
        f"end=$((SECONDS+{int(hold_s)})); n=0; "
        "while [ $SECONDS -lt $end ]; do "
        "/out/vector_add >/out/kernel_stdout.txt 2>&1 || exit $?; n=$((n+1)); done; "
        'echo "runs=$n"'
    )
    return await _docker(
        [
            "run",
            "--rm",
            "--gpus",
            "all",
            "-v",
            f"{run_dir}:/out",
            image,
            "bash",
            "-lc",
            loop,
        ],
        timeout_s,
    )


async def run_gt_0002(task: GoldenTask, run_dir: Path) -> dict[str, float]:
    """Execute gt-0002 end to end and return its measured metrics."""
    log = _logger.bind(golden=task.id, board=task.board)
    timeout_s = task.timeout_min * 60.0
    image = _cuda_image()

    build_rc, build_log = await _compile(image, run_dir, timeout_s=min(timeout_s, 300.0))
    (run_dir / "build.txt").write_text(build_log)
    if build_rc != 0 or "BUILD_OK" not in build_log:
        log.error("gt0002_build_failed", exit_status=build_rc)
        return {"run_exit_code": float(build_rc or 1), "kernel_ok": 0.0, "build_ok": 0.0}

    # Run the kernel on the GPU while sampling host telemetry concurrently.
    run_future = asyncio.ensure_future(
        _run_loop(image, run_dir, _HOLD_S, timeout_s=min(timeout_s, _HOLD_S + 60.0))
    )
    started = time.monotonic()
    samples = []
    while not run_future.done():
        samples.append(sample_once(cpu_window_s=0.05))
        await asyncio.sleep(_SAMPLE_INTERVAL_S)
    run_rc, run_out = await run_future
    wall_s = time.monotonic() - started
    (run_dir / "run.txt").write_text(run_out)

    kernel_out = ""
    stdout_path = run_dir / "kernel_stdout.txt"
    if stdout_path.is_file():
        kernel_out = stdout_path.read_text(errors="replace")

    metrics: dict[str, float] = {
        "run_exit_code": float(run_rc),
        "kernel_ok": 1.0 if _KERNEL_OK_MARKER in kernel_out else 0.0,
        "build_ok": 1.0,
        "wall_s": wall_s,
    }
    metrics.update(summarize_generic(samples, interval_ms=int(_SAMPLE_INTERVAL_S * 1000)))
    log.info("gt0002_metrics", **metrics)
    return metrics
