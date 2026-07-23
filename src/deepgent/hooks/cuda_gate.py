"""cuda_gate: PostToolUse advisory on CUDA source writes (section 10, #5).

compute-sanitizer is dynamic and needs a GPU plus a compiled binary, so it
cannot run inline on the dev host like misra_gate. This hook instead surfaces
a non-blocking reminder whenever a CUDA source file is written or edited, so
the modified kernel is not marked done until it has passed `deepgent
cuda-check` on a board. The gate itself (evals/cuda_check.py) runs in the
verify/hardware step.
"""

from pathlib import Path
from typing import Any, cast

import structlog
from claude_agent_sdk.types import (
    HookContext,
    HookInput,
    PostToolUseHookInput,
    SyncHookJSONOutput,
)

_logger = structlog.get_logger(__name__)

CUDA_SUFFIXES = frozenset({".cu", ".cuh"})
_WRITE_TOOLS = frozenset({"Write", "Edit"})


def is_cuda_file(file_path: str) -> bool:
    return Path(file_path).suffix in CUDA_SUFFIXES


def make_cuda_gate() -> Any:
    """Build the cuda_gate advisory callback."""

    async def cuda_gate(
        input_data: HookInput,
        tool_use_id: str | None,
        context: HookContext,
    ) -> SyncHookJSONOutput:
        data = cast(PostToolUseHookInput, input_data)
        if data["tool_name"] not in _WRITE_TOOLS:
            return {}
        raw_path = str(data["tool_input"].get("file_path", ""))
        if not raw_path or not is_cuda_file(raw_path):
            return {}
        name = Path(raw_path).name
        _logger.info("cuda_gate_advisory", file=name)
        return {
            "systemMessage": (
                f"{name} is a CUDA source file. compute-sanitizer is dynamic, so it "
                "was not run inline. Before marking this task done, run "
                "'deepgent cuda-check --board <id> --build <cmd> --run <cmd>' on a GPU "
                "target and resolve any memcheck/racecheck errors."
            )
        }

    return cuda_gate
