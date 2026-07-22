"""gt-0001: build, deploy, and run the trivial CUDA kernel; capture tegrastats.

Deterministic implementation (prime directive: a script does the step when a
script can). The agent-driven path arrives with the board-farm MCP in
Phase 2.
"""

import asyncio
import time
from pathlib import Path

import structlog

from deepgent.boards import BoardRunner, CommandResult, get_board, parse_capture
from deepgent.containers import ContainerBuilder, load_jp6_spec
from deepgent.evals.schema import GoldenTask

_logger = structlog.get_logger(__name__)

_REMOTE_DIR = "/tmp/deepgent-gt0001"
_REMOTE_BINARY = f"{_REMOTE_DIR}/vector_add"
_KERNEL_OK_MARKER = "vector_add ok"
_CAPTURE_PADDING_S = 4.0
_TEGRASTATS_INTERVAL_MS = 500


async def run_gt_0001(task: GoldenTask, run_dir: Path) -> dict[str, float]:
    """Execute gt-0001 end to end and return its metrics."""
    log = _logger.bind(golden=task.id, board=task.board)
    timeout_s = task.timeout_min * 60.0

    builder = ContainerBuilder(load_jp6_spec())
    builder.ensure_image()
    binary = builder.compile_smoke(run_dir)
    log.info("gt0001_binary_built", binary=str(binary))

    board = get_board(task.board)
    async with BoardRunner(board) as runner:
        setup = await runner.run(f"mkdir -p {_REMOTE_DIR}", timeout_s=30)
        if setup.exit_status != 0:
            return {"run_exit_code": float(setup.exit_status), "kernel_ok": 0.0}
        await runner.put(binary, _REMOTE_BINARY)
        await runner.run(f"chmod +x {_REMOTE_BINARY}", timeout_s=30)

        run_timeout = min(timeout_s, 120.0)
        capture_s = run_timeout + 2 * _CAPTURE_PADDING_S

        async def delayed_kernel() -> tuple[float, CommandResult]:
            # Let tegrastats settle before the kernel so the capture brackets
            # the run with idle baselines on both sides.
            await asyncio.sleep(_CAPTURE_PADDING_S)
            started = time.monotonic()
            result = await runner.run(_REMOTE_BINARY, timeout_s=run_timeout)
            return time.monotonic() - started, result

        capture_future = asyncio.create_task(
            runner.capture_tegrastats(capture_s, _TEGRASTATS_INTERVAL_MS)
        )
        wall_s, kernel_result = await delayed_kernel()
        raw_tegrastats = await capture_future

        cleanup = await runner.run(f"rm -rf {_REMOTE_DIR}", timeout_s=30)
        if cleanup.exit_status != 0:
            log.warning("gt0001_cleanup_failed", exit_status=cleanup.exit_status)

    (run_dir / "kernel_stdout.txt").write_text(kernel_result.stdout + kernel_result.stderr)
    (run_dir / "tegrastats_raw.txt").write_text(raw_tegrastats)
    capture = parse_capture(raw_tegrastats)

    metrics: dict[str, float] = {
        "run_exit_code": float(kernel_result.exit_status),
        "kernel_ok": 1.0 if _KERNEL_OK_MARKER in kernel_result.stdout else 0.0,
        "wall_s": wall_s,
    }
    metrics.update(capture.summary_metrics(interval_ms=_TEGRASTATS_INTERVAL_MS))
    log.info("gt0001_metrics", **metrics)
    return metrics
