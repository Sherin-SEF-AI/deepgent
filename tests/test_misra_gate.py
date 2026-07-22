"""misra_gate behavior: file gating, output parsing, and block decisions."""

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk.types import HookContext

import deepgent.hooks.misra_gate as gate_module
from deepgent.errors import ContainerError
from deepgent.hooks import Finding, is_gated_file, make_misra_gate

REPO_ROOT = Path(__file__).resolve().parent.parent

_CPPCHECK_OUT = """\
/src/bad.c|4|style|misra-c2012-15.5|misra violation (use --rule-texts=<file> to get proper output)
/src/bad.c|9|warning|nullPointer|Possible null pointer dereference: p
/src/bad.c|0|information|checkersReport|Active checkers: 106/592
not a finding line
"""

_CLANG_TIDY_OUT = """\
/src/bad.c:9:5: warning: Dereference of null pointer [clang-analyzer-core.NullDereference]
    9 |     *p = 1;
/src/bad.c:12:3: error: use of undeclared identifier 'x' [clang-diagnostic-error]
random noise
"""


def _post_write_input(file_path: str, tool: str = "Write") -> dict[str, Any]:
    return {
        "session_id": "sess-fake",
        "transcript_path": "/tmp/fake-transcript",
        "cwd": str(REPO_ROOT),
        "permission_mode": "default",
        "agent_id": "agent-fake",
        "agent_type": "implementer",
        "hook_event_name": "PostToolUse",
        "tool_name": tool,
        "tool_input": {"file_path": file_path, "content": ""},
        "tool_response": "ok",
        "tool_use_id": "toolu-fake",
    }


class TestFileGating:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        ("path", "gated"),
        [
            ("src/driver.c", True),
            ("src/pipeline.cc", True),
            ("src/node.cpp", True),
            ("include/api.h", True),
            ("include/api.hpp", True),
            ("src/main.py", False),
            ("kernel.cu", False),
            ("README.md", False),
        ],
    )
    def test_suffixes(self, path: str, gated: bool) -> None:
        assert is_gated_file(path) is gated

    @pytest.mark.unit
    def test_non_write_tools_ignored(self, hook_context: HookContext) -> None:
        gate = make_misra_gate()
        result = asyncio.run(gate(_post_write_input("a.c", tool="Bash"), None, hook_context))
        assert result == {}

    @pytest.mark.unit
    def test_non_c_files_ignored(self, hook_context: HookContext) -> None:
        gate = make_misra_gate()
        result = asyncio.run(gate(_post_write_input("a.py"), None, hook_context))
        assert result == {}

    @pytest.mark.unit
    def test_missing_file_ignored(self, hook_context: HookContext, tmp_path: Path) -> None:
        gate = make_misra_gate()
        call = _post_write_input(str(tmp_path / "ghost.c"))
        assert asyncio.run(gate(call, None, hook_context)) == {}


class TestParsers:
    @pytest.mark.unit
    def test_cppcheck_parsing_skips_meta_and_noise(self) -> None:
        findings = gate_module.parse_cppcheck(_CPPCHECK_OUT)
        assert len(findings) == 2
        assert findings[0].rule == "misra-c2012-15.5"
        assert findings[0].line == 4
        assert findings[1].rule == "nullPointer"

    @pytest.mark.unit
    def test_clang_tidy_parsing(self) -> None:
        findings = gate_module.parse_clang_tidy(_CLANG_TIDY_OUT)
        assert len(findings) == 2
        assert findings[0].rule == "clang-analyzer-core.NullDereference"
        assert findings[1].line == 12

    @pytest.mark.unit
    def test_finding_describe(self) -> None:
        finding = Finding(tool="cppcheck", file="a.c", line=3, rule="r", message="m")
        assert finding.describe() == "a.c:3 [cppcheck:r] m"


class TestDecisions:
    @pytest.mark.unit
    def test_violations_block_with_findings(
        self, hook_context: HookContext, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        bad = tmp_path / "bad.c"
        bad.write_text("int main(void) { return 0; }\n")

        async def fake_analysis(path: Path) -> list[Finding]:
            return [Finding(tool="cppcheck", file=str(path), line=1, rule="r1", message="boom")]

        monkeypatch.setattr(gate_module, "run_analysis", fake_analysis)
        gate = make_misra_gate()
        result = asyncio.run(gate(_post_write_input(str(bad)), None, hook_context))
        assert result.get("decision") == "block"
        assert "r1" in result.get("reason", "")

    @pytest.mark.unit
    def test_clean_file_passes(
        self, hook_context: HookContext, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        good = tmp_path / "good.c"
        good.write_text("int main(void) { return 0; }\n")

        async def fake_analysis(path: Path) -> list[Finding]:
            return []

        monkeypatch.setattr(gate_module, "run_analysis", fake_analysis)
        gate = make_misra_gate()
        assert asyncio.run(gate(_post_write_input(str(good)), None, hook_context)) == {}

    @pytest.mark.unit
    def test_unrunnable_analysis_fails_closed(
        self, hook_context: HookContext, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = tmp_path / "x.c"
        source.write_text("int main(void) { return 0; }\n")

        async def broken_analysis(path: Path) -> list[Finding]:
            raise ContainerError("toolchain image missing")

        monkeypatch.setattr(gate_module, "run_analysis", broken_analysis)
        gate = make_misra_gate()
        result = asyncio.run(gate(_post_write_input(str(source)), None, hook_context))
        assert result.get("decision") == "block"
        assert "toolchain image missing" in result.get("reason", "")


requires_container_env = pytest.mark.skipif(
    shutil.which("docker") is None or os.environ.get("DEEPGENT_CONTAINER_TESTS") != "1",
    reason="needs docker and DEEPGENT_CONTAINER_TESTS=1 (runs analyzers in the jp6 image)",
)


@pytest.mark.integration
@requires_container_env
def test_real_analysis_catches_null_dereference(tmp_path: Path) -> None:
    bad = tmp_path / "bad.c"
    bad.write_text(
        "#include <stddef.h>\nint main(void) {\n    int *p = NULL;\n    *p = 1;\n    return 0;\n}\n"
    )
    findings = asyncio.run(gate_module.run_analysis(bad))
    assert any("null" in f.message.lower() or "misra" in f.rule.lower() for f in findings)
