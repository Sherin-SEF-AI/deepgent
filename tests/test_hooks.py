"""Enforcement hook behavior: scope_lock, safety_gate, budget_guard."""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk.types import HookContext

from deepgent.config import DeepgentSettings, load_settings
from deepgent.core.budget import BudgetTracker
from deepgent.hooks import (
    REFUSAL,
    build_hooks,
    gated_op_tag,
    is_in_scope,
    make_budget_guard,
    make_safety_gate,
    scope_lock,
)

FakeBoardCall = Callable[..., dict[str, Any]]

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def settings() -> DeepgentSettings:
    return load_settings(REPO_ROOT)


def _prompt_input(prompt: str) -> dict[str, Any]:
    return {
        "session_id": "sess-fake",
        "transcript_path": "/tmp/fake-transcript",
        "cwd": str(REPO_ROOT),
        "permission_mode": "default",
        "hook_event_name": "UserPromptSubmit",
        "prompt": prompt,
    }


class TestScopeLock:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        "prompt",
        [
            "quantize the yolo detector to INT8 on the agx orin",
            "debug the CAN bus timeout on the vehicle gateway",
            "bring up the GMSL2 camera on jetpack 6.2",
            "fix the failing unit test",
            "profile p99 latency of the detection model",
        ],
    )
    def test_in_scope_prompts_pass(self, prompt: str, hook_context: HookContext) -> None:
        assert is_in_scope(prompt)
        result = asyncio.run(scope_lock(_prompt_input(prompt), None, hook_context))
        assert result == {}

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "prompt",
        [
            "write me a poem about the ocean",
            "give me a recipe for sourdough",
            "I need relationship advice",
            "tell me a joke",
        ],
    )
    def test_out_of_scope_prompts_blocked(self, prompt: str, hook_context: HookContext) -> None:
        assert not is_in_scope(prompt)
        result = asyncio.run(scope_lock(_prompt_input(prompt), None, hook_context))
        assert result.get("decision") == "block"
        assert result.get("reason") == REFUSAL
        assert result.get("reason", "").count("\n") == 0

    @pytest.mark.unit
    def test_domain_signal_beats_out_of_scope_pattern(self) -> None:
        assert is_in_scope("write a poem about the jetson orin")


class TestSafetyGateTagging:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("tool", "tool_input", "expected"),
        [
            ("power", {}, "power"),
            ("flash", {}, "flash"),
            ("gpio", {}, "gpio"),
            ("exec", {"command": "systemctl restart nvargus-daemon"}, "daemon-restart"),
            ("exec", {"command": "reboot"}, "daemon-restart"),
            ("exec", {"command": "rm -rf /var/log"}, "fs-destructive"),
            ("exec", {"command": "dd if=image.img of=/dev/mmcblk0"}, "fs-destructive"),
            ("exec", {"command": "mkfs.ext4 /dev/sda1"}, "fs-destructive"),
            ("exec", {"command": "echo 1 > /dev/watchdog"}, "fs-destructive"),
            ("exec", {"command": "tegrastats --interval 1000"}, None),
            ("exec", {"command": "ls -la /opt"}, None),
            ("list_boards", {}, None),
            ("lease", {"board": "agx-orin"}, None),
            ("release", {"board": "agx-orin"}, None),
            ("deploy", {"board": "agx-orin"}, None),
            ("capture_metrics", {"board": "agx-orin"}, None),
        ],
    )
    def test_op_tagging(self, tool: str, tool_input: dict[str, Any], expected: str | None) -> None:
        assert gated_op_tag(f"mcp__board_farm__{tool}", tool_input) == expected


def _decision(result: dict[str, Any]) -> str | None:
    output = result.get("hookSpecificOutput")
    return output.get("permissionDecision") if output else None


class TestSafetyGateDecisions:
    @pytest.mark.unit
    def test_gated_op_asks_for_approval(
        self,
        settings: DeepgentSettings,
        fake_board_call: FakeBoardCall,
        hook_context: HookContext,
    ) -> None:
        gate = make_safety_gate(settings)
        call = fake_board_call("power", {"board": "agx-orin", "state": "cycle"})
        result = asyncio.run(gate(call, "toolu-fake", hook_context))
        assert _decision(result) == "ask"

    @pytest.mark.unit
    def test_ci_mode_denies_non_whitelisted(
        self, fake_board_call: FakeBoardCall, hook_context: HookContext
    ) -> None:
        settings = load_settings(REPO_ROOT).model_copy(update={"ci": True})
        gate = make_safety_gate(settings)
        call = fake_board_call("flash", {"board": "agx-orin"})
        result = asyncio.run(gate(call, "toolu-fake", hook_context))
        assert _decision(result) == "deny"

    @pytest.mark.unit
    def test_whitelisted_op_allowed(
        self,
        settings: DeepgentSettings,
        fake_board_call: FakeBoardCall,
        hook_context: HookContext,
        tmp_path: Path,
    ) -> None:
        (tmp_path / ".deepgent").mkdir()
        (tmp_path / ".deepgent" / "gates.toml").write_text('[boards.agx-orin]\nallow = ["power"]\n')
        gate = make_safety_gate(settings)
        call = fake_board_call("power", {"board": "agx-orin"}, cwd=tmp_path)
        result = asyncio.run(gate(call, "toolu-fake", hook_context))
        assert _decision(result) == "allow"

    @pytest.mark.unit
    def test_whitelist_is_per_op(
        self,
        settings: DeepgentSettings,
        fake_board_call: FakeBoardCall,
        hook_context: HookContext,
        tmp_path: Path,
    ) -> None:
        (tmp_path / ".deepgent").mkdir()
        (tmp_path / ".deepgent" / "gates.toml").write_text('[boards.agx-orin]\nallow = ["power"]\n')
        gate = make_safety_gate(settings)
        call = fake_board_call("flash", {"board": "agx-orin"}, cwd=tmp_path)
        result = asyncio.run(gate(call, "toolu-fake", hook_context))
        assert _decision(result) == "ask"

    @pytest.mark.unit
    def test_unknown_board_never_whitelisted(
        self,
        settings: DeepgentSettings,
        fake_board_call: FakeBoardCall,
        hook_context: HookContext,
        tmp_path: Path,
    ) -> None:
        (tmp_path / ".deepgent").mkdir()
        (tmp_path / ".deepgent" / "gates.toml").write_text('[boards.agx-orin]\nallow = ["power"]\n')
        gate = make_safety_gate(settings)
        call = fake_board_call("power", {}, cwd=tmp_path)
        result = asyncio.run(gate(call, "toolu-fake", hook_context))
        assert _decision(result) == "ask"

    @pytest.mark.unit
    def test_ungated_tool_defers_to_normal_flow(
        self,
        settings: DeepgentSettings,
        fake_board_call: FakeBoardCall,
        hook_context: HookContext,
    ) -> None:
        gate = make_safety_gate(settings)
        call = fake_board_call("capture_metrics", {"board": "agx-orin"})
        assert asyncio.run(gate(call, "toolu-fake", hook_context)) == {}


class TestBudgetGuard:
    @pytest.mark.unit
    def test_under_threshold_is_silent(
        self, settings: DeepgentSettings, hook_context: HookContext
    ) -> None:
        tracker = BudgetTracker(settings)
        guard = make_budget_guard(tracker)
        result = asyncio.run(guard(_post_tool_use_input(), "toolu-fake", hook_context))
        assert result == {}

    @pytest.mark.unit
    def test_halts_at_ninety_percent(
        self, settings: DeepgentSettings, hook_context: HookContext
    ) -> None:
        tracker = BudgetTracker(settings)
        tracker.spent_usd = 0.9 * tracker.cap_usd
        guard = make_budget_guard(tracker)
        result = asyncio.run(guard(_post_tool_use_input(), "toolu-fake", hook_context))
        assert result.get("continue_") is False
        assert "cap" in result.get("stopReason", "")


def _post_tool_use_input() -> dict[str, Any]:
    return {
        "session_id": "sess-fake",
        "transcript_path": "/tmp/fake-transcript",
        "cwd": str(REPO_ROOT),
        "permission_mode": "default",
        "agent_id": "agent-fake",
        "agent_type": "implementer",
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "uv run pytest"},
        "tool_response": "ok",
        "tool_use_id": "toolu-fake",
    }


class TestRegistry:
    @pytest.mark.unit
    def test_core_hooks_registered(self, settings: DeepgentSettings) -> None:
        hooks = build_hooks(settings, BudgetTracker(settings))
        # reflexion_tap runs on every session, so PostToolUseFailure is always
        # present even without a telemetry store.
        assert set(hooks) == {
            "UserPromptSubmit",
            "PreToolUse",
            "PostToolUse",
            "PostToolUseFailure",
        }
        # Two PreToolUse matchers: the catch-all tool-exclusivity gate and the
        # board-farm safety gate.
        matchers = [m.matcher for m in hooks["PreToolUse"]]
        assert None in matchers  # exclusivity_gate fires on every tool call
        assert "mcp__board_farm__.*" in matchers  # safety_gate
        for matcher_list in hooks.values():
            assert all(m.hooks for m in matcher_list)
