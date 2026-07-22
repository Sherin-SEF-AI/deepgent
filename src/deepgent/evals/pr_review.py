"""Hardware-verified PR review: comments carry on-target measurements (Tier 3).

Runs the golden suite (or a named subset) against the PR's changes on real
hardware, diffs the metrics against the recorded baselines, and renders a
review comment where every line is a measurement, not an opinion. The GitHub
Actions workflow posts it; this module produces the deterministic body.
"""

from dataclasses import dataclass, field
from pathlib import Path

from deepgent.evals.runner import GoldenRunResult, diff_against_baseline


@dataclass
class ReviewFinding:
    """One golden's on-hardware result for the PR."""

    task_id: str
    passed: bool
    metrics: dict[str, float]
    regressions: list[str] = field(default_factory=list)


@dataclass
class HardwareReview:
    """A full hardware-verified review body."""

    findings: list[ReviewFinding] = field(default_factory=list)

    @property
    def has_regressions(self) -> bool:
        return any(f.regressions or not f.passed for f in self.findings)

    def render_markdown(self) -> str:
        lines = ["## deepgent hardware-verified review", ""]
        if not self.findings:
            lines.append("No goldens ran for this change.")
            return "\n".join(lines) + "\n"
        verdict = "changes requested" if self.has_regressions else "measurements pass"
        lines.append(f"**Verdict: {verdict}** (every number below was measured on target)")
        lines.append("")
        for finding in self.findings:
            status = "PASS" if finding.passed and not finding.regressions else "FAIL"
            lines.append(f"### {finding.task_id}: {status}")
            metric_bits = []
            for key in ("wall_s", "p99_latency_ms", "power_mean_w", "energy_j", "tj_max_c"):
                if key in finding.metrics:
                    metric_bits.append(f"{key}={finding.metrics[key]:.2f}")
            if metric_bits:
                lines.append("measured: " + ", ".join(metric_bits))
            for regression in finding.regressions:
                lines.append(f"- {regression}")
            lines.append("")
        return "\n".join(lines) + "\n"


def build_review(results: list[GoldenRunResult], project_root: Path) -> HardwareReview:
    """Assemble a review from golden run results, diffing each against its
    baseline."""
    review = HardwareReview()
    for result in results:
        regressions = diff_against_baseline(result, project_root)
        # A missing baseline is informational, not a regression, on a PR.
        regressions = [r for r in regressions if "no baseline" not in r]
        review.findings.append(
            ReviewFinding(
                task_id=result.task.id,
                passed=result.passed,
                metrics=result.metrics,
                regressions=regressions,
            )
        )
    return review
