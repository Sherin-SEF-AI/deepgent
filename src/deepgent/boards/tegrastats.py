"""Deterministic tegrastats parser for L4T r36-family output.

A line looks like:
  11-14-2024 12:34:56 RAM 3162/30536MB (lfb 6x4MB) SWAP 0/15268MB (cached 0MB)
  CPU [1%@729,0%@729,off,...] EMC_FREQ 0%@2133 GR3D_FREQ 0%@[305]
  cpu@47.968C soc0@46.906C gpu@46.343C tj@47.968C VDD_GPU_SOC 3175mW/3175mW

Unparseable lines are skipped and counted, never silently mis-parsed.
"""

import re
from dataclasses import dataclass, field
from statistics import mean

_RAM = re.compile(r"\bRAM (\d+)/(\d+)MB\b")
_GR3D = re.compile(r"\bGR3D_FREQ (\d+)%")
_CPU = re.compile(r"\bCPU \[([^\]]+)\]")
_CPU_CORE = re.compile(r"^(\d+)%@\d+$")
_TEMP = re.compile(r"\b([a-zA-Z][a-zA-Z0-9_]*)@([\d.]+)C\b")
# Power rails print "<RAIL> <inst>mW/<avg>mW" (r36 TegrastatsUtility docs);
# instantaneous first, average-since-start second.
_RAIL = re.compile(r"\b(V[A-Z0-9_]+)\s+(\d+)mW/(\d+)mW\b")


@dataclass(frozen=True)
class TegrastatsSample:
    """One parsed tegrastats line."""

    ram_used_mb: int
    ram_total_mb: int
    gr3d_pct: int | None
    cpu_pcts: tuple[int | None, ...]
    temps_c: dict[str, float] = field(default_factory=dict)
    rails_mw: dict[str, tuple[int, int]] = field(default_factory=dict)

    @property
    def total_power_mw(self) -> int | None:
        """Sum of instantaneous rail power, when any rails were reported."""
        if not self.rails_mw:
            return None
        return sum(inst for inst, _avg in self.rails_mw.values())


def parse_line(line: str) -> TegrastatsSample | None:
    """Parse one tegrastats line; None when it is not a tegrastats sample."""
    ram = _RAM.search(line)
    if ram is None:
        return None

    gr3d_match = _GR3D.search(line)
    gr3d = int(gr3d_match.group(1)) if gr3d_match else None

    cpu_pcts: tuple[int | None, ...] = ()
    cpu_match = _CPU.search(line)
    if cpu_match:
        cores: list[int | None] = []
        for entry in cpu_match.group(1).split(","):
            core = _CPU_CORE.match(entry.strip())
            cores.append(int(core.group(1)) if core else None)
        cpu_pcts = tuple(cores)

    temps = {name: float(value) for name, value in _TEMP.findall(line)}
    rails = {name: (int(inst), int(avg)) for name, inst, avg in _RAIL.findall(line)}
    return TegrastatsSample(
        ram_used_mb=int(ram.group(1)),
        ram_total_mb=int(ram.group(2)),
        gr3d_pct=gr3d,
        cpu_pcts=cpu_pcts,
        temps_c=temps,
        rails_mw=rails,
    )


@dataclass(frozen=True)
class TegrastatsCapture:
    """All samples parsed from one capture."""

    samples: tuple[TegrastatsSample, ...]
    skipped_lines: int

    def summary_metrics(self, interval_ms: int | None = None) -> dict[str, float]:
        """Mechanical summary metrics for golden scoring.

        With the capture interval, rail power integrates into energy_j via
        a left Riemann sum over instantaneous rail totals.
        """
        metrics: dict[str, float] = {
            "tegrastats_samples": float(len(self.samples)),
            "tegrastats_skipped_lines": float(self.skipped_lines),
        }
        if self.samples:
            metrics["ram_used_max_mb"] = float(max(s.ram_used_mb for s in self.samples))
            gr3d = [s.gr3d_pct for s in self.samples if s.gr3d_pct is not None]
            if gr3d:
                metrics["gr3d_max_pct"] = float(max(gr3d))
                metrics["gr3d_mean_pct"] = float(mean(gr3d))
            temps = [s.temps_c["tj"] for s in self.samples if "tj" in s.temps_c]
            if temps:
                metrics["tj_max_c"] = max(temps)
            powers = [s.total_power_mw for s in self.samples if s.total_power_mw is not None]
            if powers:
                metrics["power_mean_w"] = float(mean(powers)) / 1000.0
                metrics["power_max_w"] = float(max(powers)) / 1000.0
                if interval_ms is not None:
                    metrics["energy_j"] = sum(powers) / 1000.0 * (interval_ms / 1000.0)
        return metrics


def energy_per_item(metrics: dict[str, float], items: int) -> float | None:
    """Joules per inference/iteration from captured energy, or None."""
    energy = metrics.get("energy_j")
    if energy is None or items <= 0:
        return None
    return energy / items


def parse_capture(text: str) -> TegrastatsCapture:
    """Parse a raw tegrastats capture into samples plus a skip count."""
    samples: list[TegrastatsSample] = []
    skipped = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        sample = parse_line(line)
        if sample is None:
            skipped += 1
        else:
            samples.append(sample)
    return TegrastatsCapture(samples=tuple(samples), skipped_lines=skipped)
