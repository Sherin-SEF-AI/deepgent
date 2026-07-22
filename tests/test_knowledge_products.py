"""Tier 2 knowledge products: upgrade-check, BOM advisor, triage, errata."""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from deepgent.knowledge.errata import Erratum, scan_errata
from deepgent.knowledge.products import (
    BomCandidate,
    BomConstraints,
    bom_advise,
    triage,
    upgrade_check,
)


class _FakeClient:
    """RagClient double with scripted matrix/corpus answers."""

    def __init__(self, claims: dict[str, dict[str, Any]], tuples: list[dict[str, Any]]) -> None:
        self._claims = claims
        self._tuples = tuples
        self.claim_queries: list[dict[str, str]] = []

    async def query_claim(self, stack: dict[str, str]) -> dict[str, Any]:
        self.claim_queries.append(stack)
        key = stack.get("trt", "") + "|" + stack.get("cuda", "")
        return self._claims.get(key, {"status": "unknown"})

    async def search_symptom(self, text: str, hw: str | None = None) -> list[dict[str, Any]]:
        return self._tuples


class TestUpgradeCheck:
    @pytest.mark.unit
    def test_verified_upgrade_is_safe(self) -> None:
        client = _FakeClient(
            claims={
                "10.16.2|12.6": {
                    "status": "verified_pass",
                    "evidence_run_id": "gt-0007-x",
                    "claim": "INT8 build works",
                }
            },
            tuples=[],
        )
        report = asyncio.run(
            upgrade_check(
                client,  # type: ignore[arg-type]
                current_stack={"trt": "10.3", "cuda": "12.6"},
                proposed={"trt": "10.16.2"},
            )
        )
        assert report.safe
        assert report.impacts[0].evidence_run_id == "gt-0007-x"
        assert "PASS" in report.render()

    @pytest.mark.unit
    def test_unknown_upgrade_warns(self) -> None:
        client = _FakeClient(claims={}, tuples=[])
        report = asyncio.run(
            upgrade_check(
                client,  # type: ignore[arg-type]
                current_stack={"trt": "10.3"},
                proposed={"trt": "10.16.2"},
            )
        )
        assert not report.safe
        assert report.has_unknowns
        assert "run the golden suite" in report.render()

    @pytest.mark.unit
    def test_unchanged_components_skipped(self) -> None:
        client = _FakeClient(claims={}, tuples=[])
        report = asyncio.run(
            upgrade_check(
                client,  # type: ignore[arg-type]
                current_stack={"trt": "10.3", "cuda": "12.6"},
                proposed={"trt": "10.3", "cuda": "12.6"},
            )
        )
        assert report.impacts == []
        assert report.safe


class TestBomAdvisor:
    def _candidates(self) -> list[BomCandidate]:
        return [
            BomCandidate(
                board="agx-orin",
                stack={"l4t": "36.4.3"},
                fps=120.0,
                power_w=28.0,
                cost_usd=1999.0,
                evidence_run_id="r1",
            ),
            BomCandidate(
                board="pi5-hailo",
                stack={"hailo": "8"},
                fps=45.0,
                power_w=9.0,
                cost_usd=200.0,
                evidence_run_id="r2",
            ),
        ]

    @pytest.mark.unit
    def test_filters_and_sorts_by_cost(self) -> None:
        result = bom_advise(self._candidates(), BomConstraints(min_fps=40.0))
        assert [c.board for c in result] == ["pi5-hailo", "agx-orin"]

    @pytest.mark.unit
    def test_fps_constraint_excludes(self) -> None:
        result = bom_advise(self._candidates(), BomConstraints(min_fps=100.0))
        assert [c.board for c in result] == ["agx-orin"]

    @pytest.mark.unit
    def test_power_and_cost_constraints(self) -> None:
        result = bom_advise(
            self._candidates(), BomConstraints(max_power_w=15.0, max_cost_usd=500.0)
        )
        assert [c.board for c in result] == ["pi5-hailo"]

    @pytest.mark.unit
    def test_no_candidate_meets_constraints(self) -> None:
        assert bom_advise(self._candidates(), BomConstraints(min_fps=200.0)) == []


class TestTriage:
    @pytest.mark.unit
    def test_corpus_hit_skips_llm(self) -> None:
        client = _FakeClient(
            claims={},
            tuples=[
                {
                    "symptom": "nvcc unsupported arch",
                    "root_cause": "wrong toolchain",
                    "fix": "use jp6 container",
                    "verification_run_id": "gt-0001-x",
                }
            ],
        )
        result = asyncio.run(triage(client, "nvcc unsupported"))  # type: ignore[arg-type]
        assert result.corpus_hit
        assert not result.escalate
        assert "corpus hit" in result.render()
        assert "use jp6 container" in result.render()

    @pytest.mark.unit
    def test_corpus_miss_escalates(self) -> None:
        client = _FakeClient(claims={}, tuples=[])
        result = asyncio.run(triage(client, "novel symptom"))  # type: ignore[arg-type]
        assert not result.corpus_hit
        assert result.escalate
        assert "corpus miss" in result.render()


class TestErrata:
    def _errata(self) -> list[Erratum]:
        return [
            Erratum(
                id="ERR-ORIN-001",
                chip="agx-orin",
                title="PCIe C5 hang",
                patterns=(r"\bpcie@14180000\b", r"\bPCIE_C5\b"),
                advisory="apply the C5 controller reset workaround",
            ),
            Erratum(
                id="ERR-XAVIER-002",
                chip="xavier",
                title="unrelated",
                patterns=(r"\bxavier_only\b",),
                advisory="n/a",
            ),
        ]

    @pytest.mark.unit
    def test_scan_matches_bom_chips_only(self, tmp_path: Path) -> None:
        (tmp_path / "board.dtsi").write_text('pcie@14180000 {\n    status = "okay";\n};\n')
        (tmp_path / "other.c").write_text("int xavier_only = 1;\n")
        result = scan_errata(tmp_path, self._errata(), bom_chips={"agx-orin"})
        assert result.exposed
        assert len(result.hits) == 1
        assert result.hits[0].erratum_id == "ERR-ORIN-001"
        assert "board.dtsi:1" in result.hits[0].describe()

    @pytest.mark.unit
    def test_no_bom_overlap_means_no_scan(self, tmp_path: Path) -> None:
        (tmp_path / "board.dtsi").write_text("pcie@14180000 { };\n")
        result = scan_errata(tmp_path, self._errata(), bom_chips={"thor"})
        assert not result.exposed
        assert "no exposure" in result.render_advisory()

    @pytest.mark.unit
    def test_ignored_dirs_skipped(self, tmp_path: Path) -> None:
        vendored = tmp_path / ".venv" / "lib"
        vendored.mkdir(parents=True)
        (vendored / "x.c").write_text("PCIE_C5 reg;\n")
        result = scan_errata(tmp_path, self._errata(), bom_chips={"agx-orin"})
        assert not result.exposed

    @pytest.mark.unit
    def test_advisory_lists_hits(self, tmp_path: Path) -> None:
        (tmp_path / "d.c").write_text("volatile int r = PCIE_C5;\n")
        result = scan_errata(tmp_path, self._errata(), bom_chips={"agx-orin"})
        advisory = result.render_advisory()
        assert "errata advisory" in advisory
        assert "C5 controller reset" in advisory
