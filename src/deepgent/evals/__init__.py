"""Golden task runner, mechanical scoring, and the regression gate."""

from deepgent.evals.latency_trace import (
    LatencyTrace,
    LatencyTracer,
    StageLatency,
    analyze_trace,
    parse_stage_lines,
)
from deepgent.evals.runner import GoldenRunResult, create_run_dir, find_golden_file, run_golden
from deepgent.evals.schema import (
    CriterionResult,
    GoldenTask,
    SuccessCriterion,
    load_golden,
    score,
)
from deepgent.evals.thermal_envelope import (
    ModeEnvelope,
    PowerMode,
    ThermalEnvelopeProfiler,
    ThermalEnvelopeResult,
    analyze_mode,
    analyze_throughput,
    parse_modes,
    parse_throughput_series,
)

__all__ = [
    "CriterionResult",
    "GoldenRunResult",
    "GoldenTask",
    "LatencyTrace",
    "LatencyTracer",
    "ModeEnvelope",
    "PowerMode",
    "StageLatency",
    "SuccessCriterion",
    "ThermalEnvelopeProfiler",
    "ThermalEnvelopeResult",
    "analyze_mode",
    "analyze_throughput",
    "analyze_trace",
    "create_run_dir",
    "find_golden_file",
    "load_golden",
    "parse_modes",
    "parse_stage_lines",
    "parse_throughput_series",
    "run_golden",
    "score",
]
