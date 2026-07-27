"""Deterministic task-class intake (CLAUDE.md section 3 lifecycle step 1).

Maps a natural-language task to a task class, a risk tier, the specialist
agents to load, suggested skills, and a model tier. The rules are keyword
based and fully deterministic: no model call is made to classify. When no
domain rule matches, the task is generic and runs on the core agents alone.

This is the machinery CLAUDE.md section 9 ("route by task class") and the
expansion spec A1 ("specialists loaded on demand by task class") depend on.
"""

from dataclasses import dataclass, replace

# Specialist agent names (expansion spec A1). Kept here so the classifier and
# the agent builders agree on one spelling.
PERCEPTION_ENGINEER = "perception-engineer"
DRIVER_ENGINEER = "driver-engineer"
PIPELINE_ENGINEER = "pipeline-engineer"
PROFILER = "profiler"
TRIAGE = "triage"
SAFETY_AUDITOR = "safety-auditor"
DATA_ENGINEER = "data-engineer"
INTEGRATOR = "integrator"

# A task never loads more than this many specialists (expansion spec Part C
# rule 2: more than three agents on one task is a design smell).
MAX_SPECIALISTS = 3


@dataclass(frozen=True)
class TaskClassification:
    """The deterministic routing decision for one task."""

    task_class: str
    risk_tier: int  # 1 trivial, 2 standard, 3 high (C/C++, kernel, hardware, safety)
    specialists: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    model_tier: str = "sonnet"  # "opus" | "sonnet" | "haiku"
    rationale: str = ""


@dataclass(frozen=True)
class _Rule:
    name: str
    task_class: str
    keywords: tuple[str, ...]
    specialists: tuple[str, ...]
    skills: tuple[str, ...]
    risk: int


# Ordered most-specific first; the first matching rule sets the task class.
_RULES: tuple[_Rule, ...] = (
    _Rule(
        "safety-review",
        "safety/review",
        ("misra", "safety review", "iso 26262", "iso26262", "functional safety", "safety-critical"),
        (SAFETY_AUDITOR,),
        ("embedded-c-safety", "functional-safety-process"),
        3,
    ),
    _Rule(
        "driver-bringup",
        "driver/bringup",
        (
            "device tree",
            "devicetree",
            "v4l2",
            "serdes",
            "gmsl",
            "pinmux",
            "kernel module",
            "driver",
            "bringup",
            "bring up",
            "bring-up",
        ),
        (DRIVER_ENGINEER,),
        ("jetson-device-tree", "v4l2-subdev-drivers", "camera-bringup-csi-mipi"),
        3,
    ),
    _Rule(
        "perception/training",
        "perception/training",
        ("train ", "training", "fine-tune", "finetune", "fine tune"),
        (PERCEPTION_ENGINEER, DATA_ENGINEER),
        ("training-pipelines", "dataset-curation"),
        2,
    ),
    _Rule(
        "perception/quantization",
        "perception/quantization",
        (
            "quantize",
            "quantization",
            "int8",
            "ptq",
            "qat",
            "tensorrt",
            "onnx",
            "calibration",
            "mixed precision",
        ),
        (PERCEPTION_ENGINEER,),
        ("tensorrt-quantization", "onnx-export-surgery"),
        2,
    ),
    _Rule(
        "pipeline/streaming",
        "pipeline/streaming",
        ("deepstream", "gstreamer", "pipeline", "ros2 node", "ros 2 node", "nvinfer", "streaming"),
        (PIPELINE_ENGINEER,),
        ("deepstream-pipelines", "ros2-systems"),
        2,
    ),
    _Rule(
        "perf/optimization",
        "perf/optimization",
        ("profile", "optimize", "optimization", "latency", "throughput", "nsight", "bottleneck"),
        (PROFILER,),
        ("profiling-nsight",),
        2,
    ),
    _Rule(
        "debug/incident",
        "debug/incident",
        ("debug", "crash", "hang", "regression", "kernel panic", "incident", "triage", "dmesg"),
        (TRIAGE,),
        (),
        2,
    ),
    _Rule(
        "data/labeling",
        "data/labeling",
        ("labeling", "annotate", "annotation", "auto-label", "curate dataset", "calibration set"),
        (DATA_ENGINEER,),
        ("dataset-curation",),
        2,
    ),
    _Rule(
        "release/deploy",
        "release/deploy",
        ("release", "deploy", "ota", "rollout", "rollback", "staged rollout", "fleet"),
        (INTEGRATOR,),
        ("fleet-deployment",),
        2,
    ),
)

# Adding any of these to a task escalates risk to 3 and pulls in the safety
# auditor: every C/C++ or firmware change gets an adversarial safety pass.
_CPP_MARKERS: tuple[str, ...] = (
    ".c ",
    ".cc",
    ".cpp",
    ".cxx",
    ".h ",
    ".hpp",
    ".cu",
    "firmware",
    "embedded c",
    "cuda kernel",
    "rtos",
    "zephyr",
    "stm32",
    "bare metal",
    "baremetal",
)

# Hardware/board involvement raises risk to at least 2 (a real on-target run).
_HARDWARE_MARKERS: tuple[str, ...] = (
    "flash",
    "board",
    "on target",
    "on-target",
    "jetson",
    "orin",
    "gpio",
    "can bus",
    "can-bus",
    "power rail",
    "tegrastats",
)


def _contains(haystack: str, needles: tuple[str, ...]) -> bool:
    return any(needle in haystack for needle in needles)


def _dedupe(items: tuple[str, ...]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for item in items:
        seen.setdefault(item, None)
    return tuple(seen)


def _model_tier(task_class: str, specialists: tuple[str, ...]) -> str:
    """Route the model tier (CLAUDE.md section 9)."""
    if SAFETY_AUDITOR in specialists:
        return "opus"  # safety review is the highest-stakes reasoning
    if len(specialists) >= 2:
        return "opus"  # cross-component work warrants the strongest tier
    if task_class == "generic":
        return "sonnet"
    return "sonnet"


def classify(task: str) -> TaskClassification:
    """Classify a task deterministically. Never raises; unknown -> generic."""
    text = f" {task.lower().strip()} "

    matched: _Rule | None = None
    for rule in _RULES:
        if _contains(text, rule.keywords):
            matched = rule
            break

    if matched is None:
        task_class = "generic"
        specialists: tuple[str, ...] = ()
        skills: tuple[str, ...] = ()
        risk = 1
        reasons = ["no domain rule matched; core agents only"]
    else:
        task_class = matched.task_class
        specialists = matched.specialists
        skills = matched.skills
        risk = matched.risk
        reasons = [f"matched rule '{matched.name}'"]

    if _contains(text, _CPP_MARKERS):
        specialists = (*specialists, SAFETY_AUDITOR)
        risk = max(risk, 3)
        reasons.append("C/C++ or firmware change -> safety-auditor, risk 3")
    if _contains(text, _HARDWARE_MARKERS):
        risk = max(risk, 2)
        reasons.append("hardware/board involvement -> risk >= 2")

    specialists = _dedupe(specialists)[:MAX_SPECIALISTS]
    tier = _model_tier(task_class, specialists)

    return TaskClassification(
        task_class=task_class,
        risk_tier=risk,
        specialists=specialists,
        skills=skills,
        model_tier=tier,
        rationale="; ".join(reasons),
    )


def with_skills(classification: TaskClassification, extra: tuple[str, ...]) -> TaskClassification:
    """Return a copy with additional suggested skills merged in."""
    return replace(classification, skills=_dedupe((*classification.skills, *extra)))


__all__ = ["MAX_SPECIALISTS", "TaskClassification", "classify", "with_skills"]
