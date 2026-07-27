"""Deterministic task-class intake classifier."""

import pytest

from deepgent.core.classifier import (
    DATA_ENGINEER,
    DRIVER_ENGINEER,
    MAX_SPECIALISTS,
    PERCEPTION_ENGINEER,
    PROFILER,
    SAFETY_AUDITOR,
    classify,
    with_skills,
)

pytestmark = pytest.mark.unit


def test_generic_task_loads_no_specialists() -> None:
    c = classify("write a helper to sum two numbers")
    assert c.task_class == "generic"
    assert c.risk_tier == 1
    assert c.specialists == ()
    assert c.model_tier == "sonnet"


def test_driver_task_is_high_risk() -> None:
    c = classify("write a v4l2 subdev driver for a new camera")
    assert c.task_class == "driver/bringup"
    assert c.risk_tier == 3
    assert DRIVER_ENGINEER in c.specialists


def test_training_task_loads_two_specialists_and_opus() -> None:
    c = classify("build a training pipeline and fine-tune the detector")
    assert c.task_class == "perception/training"
    assert set(c.specialists) == {PERCEPTION_ENGINEER, DATA_ENGINEER}
    # Two specialists is cross-component -> opus tier (section 9).
    assert c.model_tier == "opus"


def test_quantization_task() -> None:
    c = classify("quantize the model to int8 with tensorrt")
    assert c.task_class == "perception/quantization"
    assert c.specialists == (PERCEPTION_ENGINEER,)
    assert c.model_tier == "sonnet"


def test_perf_task_loads_profiler() -> None:
    c = classify("profile and optimize the inference latency")
    assert c.task_class == "perf/optimization"
    assert c.specialists == (PROFILER,)


def test_cpp_change_pulls_in_safety_auditor_and_risk_3() -> None:
    c = classify("edit the vision.cpp buffer handling")
    assert SAFETY_AUDITOR in c.specialists
    assert c.risk_tier == 3
    # Safety involvement always routes to opus.
    assert c.model_tier == "opus"


def test_hardware_involvement_raises_risk_to_two() -> None:
    c = classify("run the benchmark on the jetson orin board")
    assert c.risk_tier >= 2


def test_specialists_are_capped() -> None:
    # A task hitting a domain rule plus a C/C++ marker still respects the cap.
    c = classify("write a cuda kernel driver for the camera on the jetson board")
    assert len(c.specialists) <= MAX_SPECIALISTS


def test_specialists_are_deduped() -> None:
    c = classify("safety review of the firmware embedded c module")
    # safety-auditor comes from both the rule and the C/C++ escalation.
    assert c.specialists.count(SAFETY_AUDITOR) == 1


def test_classify_never_raises_on_empty() -> None:
    c = classify("")
    assert c.task_class == "generic" and c.risk_tier == 1


def test_with_skills_merges_without_duplicates() -> None:
    c = classify("quantize to int8 with tensorrt")
    merged = with_skills(c, ("tensorrt-quantization", "cuda-kernel-optimization"))
    assert merged.skills.count("tensorrt-quantization") == 1
    assert "cuda-kernel-optimization" in merged.skills
