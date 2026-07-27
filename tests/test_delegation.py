"""Blank-context delegation prompt assembly."""

import pytest

from deepgent.agents import DelegationContext, assemble_delegation_prompt

pytestmark = pytest.mark.unit


def test_full_prompt_carries_every_field() -> None:
    prompt = assemble_delegation_prompt(
        DelegationContext(
            task="Implement the CSI camera bring-up",
            plan_ref=".deepgent/runs/plan-42.md",
            file_paths=("src/driver.c", "boot/overlay.dts"),
            target_metrics=("stream at 30 fps", "link lock within 2 s"),
            prior_failures=("previous attempt: link never locked",),
            skills=("camera-bringup-csi-mipi",),
        )
    )
    assert "# Task" in prompt and "CSI camera bring-up" in prompt
    assert "# Approved plan" in prompt and "plan-42" in prompt
    assert "src/driver.c" in prompt and "boot/overlay.dts" in prompt
    assert "30 fps" in prompt
    assert "link never locked" in prompt
    assert "camera-bringup-csi-mipi" in prompt
    # The contract clause is always appended.
    assert "context is blank" in prompt


def test_minimal_prompt_omits_absent_sections() -> None:
    prompt = assemble_delegation_prompt(DelegationContext(task="Add a config flag"))
    assert "# Task" in prompt
    assert "# Approved plan" not in prompt
    assert "# Files in scope" not in prompt
    assert "# Target metrics" not in prompt
    # The contract is still present on even the smallest delegation.
    assert "production-grade" in prompt


def test_empty_task_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        DelegationContext(task="   ")
