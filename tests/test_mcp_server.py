"""deepgent MCP server: tool wrappers and registration."""

import asyncio
import json
from pathlib import Path

import pytest

from deepgent.mcp_server import (
    accuracy_score,
    boards_catalog,
    boards_list,
    build_server,
    facts,
    generate_ros2_node,
    generate_systemd,
    host_doctor,
    host_profile,
    hw_check,
    matrix_analyze,
    matrix_query,
    profile_latency,
    reflect,
    skills_eval,
    telemetry_summary,
)

pytestmark = pytest.mark.unit


def _tool_names(allow_task: bool) -> set[str]:
    server = build_server(allow_task=allow_task)
    return {t.name for t in asyncio.run(server.list_tools())}


def test_full_tool_surface_registered() -> None:
    names = _tool_names(allow_task=False)
    # Deterministic + generators + host/telemetry/boards, always exposed.
    assert {
        "hw_check",
        "boards_catalog",
        "matrix_query",
        "matrix_analyze",
        "accuracy_score",
        "skills_eval",
        "facts",
        "reflect",
        "generate_ros2_node",
        "generate_systemd",
        "host_doctor",
        "host_profile",
        "telemetry_summary",
        "boards_list",
    } <= names
    # Knowledge products (degrade gracefully) and on-target runners.
    assert {"premortem", "triage", "upgrade_check", "scaffold_driver"} <= names
    assert {
        "profile_thermal",
        "profile_latency",
        "profile_nsight",
        "cuda_check",
        "fleet",
        "soak",
        "differential",
        "accuracy_gate",
        "quant_sweep",
        "select_model",
        "shadow",
        "replay",
        "bisect",
    } <= names
    # Deterministic knowledge/generator products.
    assert {"errata_scan", "bom_advise"} <= names
    assert "run_task" not in names


def test_run_task_only_when_allowed() -> None:
    assert "run_task" in _tool_names(allow_task=True)


def test_generator_tools() -> None:
    ros2 = generate_ros2_node("perception", "detector")
    assert "package.xml" in ros2 and "detector" in ros2
    unit = generate_systemd("vision", "/usr/bin/vision --run", watchdog=10)
    assert "[Service]" in unit and "ExecStart=/usr/bin/vision --run" in unit


def test_deterministic_knowledge_products() -> None:
    from deepgent.mcp_server import bom_advise, errata_scan

    candidates = json.dumps(
        [
            {
                "board": "agx-orin",
                "stack": {"trt": "10.3"},
                "fps": 60.0,
                "power_w": 20.0,
                "cost_usd": 500.0,
                "evidence_run_id": "run-1",
            },
            {
                "board": "pi5",
                "stack": {"hailo": "8"},
                "fps": 25.0,
                "power_w": 8.0,
                "cost_usd": 120.0,
                "evidence_run_id": "run-2",
            },
        ]
    )
    out = bom_advise(candidates, "min_fps=30")
    assert "agx-orin" in out and "pi5" not in out
    assert "no candidate" in bom_advise(candidates, "min_fps=1000")
    # errata_scan finds no exposure for a chip absent from the tree.
    errata = json.dumps([{"id": "E1", "chip": "x", "patterns": ["zzz_no_match"]}])
    assert isinstance(errata_scan("x", errata), str)


def test_host_and_telemetry_tools() -> None:
    assert "arch=" in host_profile()
    # Diagnostics always render one line per check with an OK/FAIL marker.
    assert "[" in host_doctor()
    # No telemetry db yet -> summary still renders without raising.
    assert isinstance(telemetry_summary(), str)


def test_boards_list_without_registry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert "no boards registered" in boards_list()


def test_hardware_tool_errors_without_board(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # An on-target runner with no such board returns a clean error, never raises.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    out = asyncio.run(profile_latency("no-such-board", "true"))
    assert out.startswith("error:")


def test_hw_check_tool() -> None:
    config = json.dumps(
        {
            "peripherals": [
                {"name": "cam", "i2c_bus": "i2c-1", "i2c_addr": "0x10", "provenance": "ds"},
                {"name": "imu", "i2c_bus": "i2c-1", "i2c_addr": "0x10", "provenance": "ds"},
            ]
        }
    )
    out = hw_check(config)
    assert "i2c" in out and "CONFLICTS" in out


def test_hw_check_reads_a_file(tmp_path: Path) -> None:
    path = tmp_path / "carrier.json"
    path.write_text(json.dumps({"peripherals": [{"name": "x", "pins": ["P1"], "provenance": "d"}]}))
    assert "CLEAN" in hw_check(str(path))


def test_boards_catalog_tool() -> None:
    assert "hailo-8-ai-hat" in boards_catalog("accelerator")
    assert "jetson-agx-orin" in boards_catalog("")


def test_matrix_tools() -> None:
    claims = json.dumps([{"stack": {"l4t": "36.4.3"}, "component": "trt10", "works": True}])
    assert "works" in matrix_query(claims, "l4t=36.4.3", "trt10")
    contradictory = json.dumps(
        [
            {"stack": {"l4t": "36.4.3"}, "component": "x", "works": True},
            {"stack": {"l4t": "36.4.3"}, "component": "x", "works": False},
        ]
    )
    assert "contradiction" in matrix_analyze(contradictory, "x").lower()


def test_accuracy_score_tool() -> None:
    preds = json.dumps([{"label": "car", "score": 0.9, "box": [0, 0, 10, 10]}])
    truth = json.dumps([{"label": "car", "box": [0, 0, 10, 10]}])
    assert "mAP@0.5: 1.0000" in accuracy_score(preds, truth, "detection")
    assert "top-1" in accuracy_score(json.dumps(["a"]), json.dumps(["a"]), "classification")


def test_skills_eval_and_facts_and_reflect() -> None:
    ablation = json.dumps(
        [
            {"skill": "s", "present": p, "passed": pa, "loops": 3}
            for p, pa in [(True, True)] * 4 + [(False, False)] * 4
        ]
    )
    assert "skill lifecycle" in skills_eval(ablation)
    assertions = json.dumps({"addr": [{"value": "0x10", "source": "datasheet_rag"}]})
    assert "0x10" in facts(assertions)
    assert "reflexion" in reflect("Bash", "pytest failed: 1 test failed")


# --- HTTP auth guard --------------------------------------------------------


def test_bearer_guard_rejects_and_allows() -> None:
    import asyncio as _asyncio

    from deepgent.mcp_server import bearer_guard

    async def inner(scope: object, receive: object, send: object) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})

    sent: list[dict] = []

    async def send(msg: dict) -> None:
        sent.append(msg)

    guarded = bearer_guard(inner, "secret")

    # Missing/wrong token -> 401, inner not reached.
    _asyncio.run(guarded({"type": "http", "headers": []}, None, send))
    assert sent[0]["status"] == 401

    # Correct token -> passes through to inner (200).
    sent.clear()
    ok_scope = {"type": "http", "headers": [(b"authorization", b"Bearer secret")]}
    _asyncio.run(guarded(ok_scope, None, send))
    assert sent[0]["status"] == 200
