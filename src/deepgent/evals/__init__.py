"""Golden task runner, mechanical scoring, and the regression gate."""

from deepgent.evals.accuracy import AccuracyGate, AccuracyResult
from deepgent.evals.bench import BenchResult, run_benchmark, run_benchmark_on
from deepgent.evals.latency_trace import (
    LatencyTrace,
    LatencyTracer,
    StageLatency,
    analyze_trace,
    parse_stage_lines,
)
from deepgent.evals.model_selector import (
    Candidate,
    Constraint,
    ModelSelector,
    SelectionResult,
    load_candidates,
)
from deepgent.evals.quant_sweep import (
    QuantSweepResult,
    QuantSweepRunner,
    SweepConfig,
    SweepPoint,
    expand_grid,
    pareto_frontier,
    select_best,
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
    "AccuracyGate",
    "AccuracyResult",
    "BenchResult",
    "Candidate",
    "Constraint",
    "CriterionResult",
    "GoldenRunResult",
    "GoldenTask",
    "LatencyTrace",
    "LatencyTracer",
    "ModeEnvelope",
    "ModelSelector",
    "PowerMode",
    "QuantSweepResult",
    "QuantSweepRunner",
    "SelectionResult",
    "StageLatency",
    "SuccessCriterion",
    "SweepConfig",
    "SweepPoint",
    "ThermalEnvelopeProfiler",
    "ThermalEnvelopeResult",
    "analyze_mode",
    "analyze_throughput",
    "analyze_trace",
    "create_run_dir",
    "expand_grid",
    "find_golden_file",
    "load_candidates",
    "load_golden",
    "pareto_frontier",
    "parse_modes",
    "parse_stage_lines",
    "parse_throughput_series",
    "run_benchmark",
    "run_benchmark_on",
    "run_golden",
    "score",
    "select_best",
]
