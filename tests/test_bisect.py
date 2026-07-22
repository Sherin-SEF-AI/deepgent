"""Bisect binary search over ordered candidates."""

import asyncio

import pytest

from deepgent.errors import GoldenError
from deepgent.evals.bisect import bisect


def _predicate_with_breakpoint(first_bad_index: int):  # type: ignore[no-untyped-def]
    async def predicate(candidate: str) -> bool:
        # candidate names are "c0".."cN"; good while index < first_bad_index.
        index = int(candidate[1:])
        return index < first_bad_index

    return predicate


class TestBisect:
    @pytest.mark.unit
    def test_finds_first_bad_in_the_middle(self) -> None:
        candidates = [f"c{i}" for i in range(9)]
        result = asyncio.run(bisect(candidates, _predicate_with_breakpoint(5)))
        assert result.first_bad == "c5"
        assert result.last_good == "c4"

    @pytest.mark.unit
    def test_logarithmic_probe_count(self) -> None:
        candidates = [f"c{i}" for i in range(33)]  # 31 interior candidates
        probes: list[str] = []

        async def predicate(candidate: str) -> bool:
            probes.append(candidate)
            return int(candidate[1:]) < 20

        result = asyncio.run(bisect(candidates, predicate))
        assert result.first_bad == "c20"
        # Binary search over 33 candidates probes at most ~5 interior points.
        assert len(probes) <= 6

    @pytest.mark.unit
    def test_two_endpoints_need_no_probes(self) -> None:
        async def never_called(candidate: str) -> bool:
            raise AssertionError("predicate should not run with only endpoints")

        result = asyncio.run(bisect(["good", "bad"], never_called))
        assert result.first_bad == "bad"
        assert result.last_good == "good"
        assert result.steps == []

    @pytest.mark.unit
    def test_breakpoint_right_after_good_endpoint(self) -> None:
        candidates = [f"c{i}" for i in range(6)]
        result = asyncio.run(bisect(candidates, _predicate_with_breakpoint(1)))
        assert result.first_bad == "c1"
        assert result.last_good == "c0"

    @pytest.mark.unit
    def test_too_few_candidates(self) -> None:
        with pytest.raises(GoldenError, match="known-good and a known-bad"):
            asyncio.run(bisect(["only-one"], _predicate_with_breakpoint(0)))

    @pytest.mark.unit
    def test_report_renders(self) -> None:
        candidates = [f"c{i}" for i in range(5)]
        result = asyncio.run(bisect(candidates, _predicate_with_breakpoint(3)))
        report = result.render_report()
        assert "first bad: c3" in report
        assert "last good: c2" in report
