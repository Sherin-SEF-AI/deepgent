"""deepgent MCP server: tool wrappers and registration."""

import asyncio
import json
from pathlib import Path

import pytest

from deepgent.mcp_server import (
    accuracy_score,
    boards_catalog,
    build_server,
    facts,
    hw_check,
    matrix_analyze,
    matrix_query,
    reflect,
    skills_eval,
)

pytestmark = pytest.mark.unit


def _tool_names(allow_task: bool) -> set[str]:
    server = build_server(allow_task=allow_task)
    return {t.name for t in asyncio.run(server.list_tools())}


def test_deterministic_tools_registered() -> None:
    names = _tool_names(allow_task=False)
    assert names == {
        "hw_check",
        "boards_catalog",
        "matrix_query",
        "matrix_analyze",
        "accuracy_score",
        "skills_eval",
        "facts",
        "reflect",
    }
    assert "run_task" not in names


def test_run_task_only_when_allowed() -> None:
    assert "run_task" in _tool_names(allow_task=True)


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
