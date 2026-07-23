"""Datasheet-grounded hardware conflict checker (#8).

Given a carrier board plus a peripheral list - each pin assignment, I2C bus and
address, and power draw grounded in datasheet facts (with provenance) - detect
conflicts before bring-up: pin/mux collisions, I2C address clashes on a shared
bus, and power-rail budget overruns. The conflict logic is deterministic and
pure; the datasheet grounding lives in the provenance each fact carries, so an
ungrounded fact is visible, never silently trusted.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from deepgent.errors import TaskExecutionError


@dataclass(frozen=True)
class Peripheral:
    """One peripheral's resource claims, each ideally datasheet-grounded."""

    name: str
    pins: tuple[str, ...] = ()
    i2c_bus: str | None = None
    i2c_addr: int | None = None
    rail: str | None = None
    current_ma: float = 0.0
    provenance: str | None = None


@dataclass(frozen=True)
class Rail:
    """A power rail and its current budget."""

    name: str
    budget_ma: float


@dataclass(frozen=True)
class Conflict:
    """One detected hardware conflict."""

    kind: str
    detail: str
    parties: tuple[str, ...]

    def describe(self) -> str:
        return f"[{self.kind}] {self.detail}"


@dataclass
class ConflictReport:
    """All conflicts, plus peripherals lacking datasheet provenance."""

    conflicts: list[Conflict] = field(default_factory=list)
    ungrounded: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.conflicts

    def to_dict(self) -> dict[str, object]:
        return {
            "clean": self.clean,
            "ungrounded": self.ungrounded,
            "conflicts": [
                {"kind": c.kind, "detail": c.detail, "parties": list(c.parties)}
                for c in self.conflicts
            ],
        }

    def render(self) -> str:
        lines = ["# hardware conflict check"]
        if self.conflicts:
            lines.append("conflicts:")
            lines += [f"  - {c.describe()}" for c in self.conflicts]
        else:
            lines.append("conflicts: none")
        if self.ungrounded:
            lines.append("")
            lines.append("ungrounded (no datasheet provenance, treat as unverified):")
            lines += [f"  - {name}" for name in self.ungrounded]
        lines.append("")
        lines.append(f"result: {'CLEAN' if self.clean else 'CONFLICTS'}")
        return "\n".join(lines) + "\n"

    def persist(self, run_dir: Path) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "hardware-check.json").write_text(json.dumps(self.to_dict(), indent=2))
        (run_dir / "hardware-check.txt").write_text(self.render())


@dataclass(frozen=True)
class HardwareConfig:
    """A carrier board's peripherals and power rails."""

    peripherals: tuple[Peripheral, ...]
    rails: tuple[Rail, ...] = ()


def _pin_conflicts(peripherals: tuple[Peripheral, ...]) -> list[Conflict]:
    owners: dict[str, list[str]] = {}
    for p in peripherals:
        for pin in p.pins:
            owners.setdefault(pin, []).append(p.name)
    conflicts = []
    for pin, names in sorted(owners.items()):
        if len(names) > 1:
            conflicts.append(
                Conflict(
                    kind="pin",
                    detail=f"pin {pin} claimed by {', '.join(sorted(names))}",
                    parties=tuple(sorted(names)),
                )
            )
    return conflicts


def _i2c_conflicts(peripherals: tuple[Peripheral, ...]) -> list[Conflict]:
    owners: dict[tuple[str, int], list[str]] = {}
    for p in peripherals:
        if p.i2c_bus is not None and p.i2c_addr is not None:
            owners.setdefault((p.i2c_bus, p.i2c_addr), []).append(p.name)
    conflicts = []
    for (bus, addr), names in sorted(owners.items()):
        if len(names) > 1:
            conflicts.append(
                Conflict(
                    kind="i2c",
                    detail=f"address 0x{addr:02x} on {bus} shared by {', '.join(sorted(names))}",
                    parties=tuple(sorted(names)),
                )
            )
    return conflicts


def _power_conflicts(config: HardwareConfig) -> list[Conflict]:
    budgets = {rail.name: rail.budget_ma for rail in config.rails}
    draw: dict[str, float] = {}
    members: dict[str, list[str]] = {}
    for p in config.peripherals:
        if p.rail is not None:
            draw[p.rail] = draw.get(p.rail, 0.0) + p.current_ma
            members.setdefault(p.rail, []).append(p.name)
    conflicts = []
    for rail, total in sorted(draw.items()):
        budget = budgets.get(rail)
        if budget is not None and total > budget:
            conflicts.append(
                Conflict(
                    kind="power",
                    detail=f"rail {rail} draws {total:.0f}mA over its {budget:.0f}mA budget",
                    parties=tuple(sorted(members[rail])),
                )
            )
    return conflicts


def check_conflicts(config: HardwareConfig) -> ConflictReport:
    """Deterministic pin/I2C/power conflict detection over a config."""
    report = ConflictReport()
    report.conflicts.extend(_pin_conflicts(config.peripherals))
    report.conflicts.extend(_i2c_conflicts(config.peripherals))
    report.conflicts.extend(_power_conflicts(config))
    report.ungrounded = [p.name for p in config.peripherals if not p.provenance]
    return report


def load_config(data: str) -> HardwareConfig:
    """Parse a hardware config JSON into a HardwareConfig.

    Schema: {"peripherals": [{name, pins?, i2c_bus?, i2c_addr?, rail?,
    current_ma?, provenance?}], "rails": [{name, budget_ma}]}.
    """
    parsed = json.loads(data)
    if "peripherals" not in parsed:
        raise TaskExecutionError("hardware config must have a 'peripherals' array")
    peripherals = tuple(
        Peripheral(
            name=str(item["name"]),
            pins=tuple(str(pin) for pin in item.get("pins", [])),
            i2c_bus=item.get("i2c_bus"),
            i2c_addr=_parse_addr(item.get("i2c_addr")),
            rail=item.get("rail"),
            current_ma=float(item.get("current_ma", 0.0)),
            provenance=item.get("provenance"),
        )
        for item in parsed["peripherals"]
    )
    rails = tuple(
        Rail(name=str(item["name"]), budget_ma=float(item["budget_ma"]))
        for item in parsed.get("rails", [])
    )
    return HardwareConfig(peripherals=peripherals, rails=rails)


def _parse_addr(value: object) -> int | None:
    """Accept an int or a hex/decimal string I2C address."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return int(str(value), 0)
