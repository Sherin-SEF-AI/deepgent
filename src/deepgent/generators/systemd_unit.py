"""Deterministic systemd service-unit generator for on-target deployments.

Emits a hardened .service unit for a deepgent-deployed binary: restart policy,
an optional systemd watchdog, resource limits, and a clean stop, so a target
never sits in a wedged daemon state (section 14 discipline). Values come from
the caller; nothing about the board is assumed.
"""

import re
import shlex
from dataclasses import dataclass, field

from deepgent.generators.driver_scaffold import ScaffoldOutput

_UNIT_NAME = re.compile(r"[^a-zA-Z0-9_.-]")


def _unit_name(name: str) -> str:
    cleaned = _UNIT_NAME.sub("-", name).strip("-")
    return cleaned or "deepgent-service"


@dataclass(frozen=True)
class SystemdUnitSpec:
    """What the service runs and how it is supervised."""

    name: str
    exec_start: str
    description: str = ""
    user: str | None = None
    working_dir: str | None = None
    after: tuple[str, ...] = ("network-online.target",)
    wants: tuple[str, ...] = ("network-online.target",)
    restart: str = "on-failure"
    restart_sec: int = 3
    watchdog_sec: int | None = None
    memory_max: str | None = None
    environment: dict[str, str] = field(default_factory=dict)


def scaffold_systemd_unit(spec: SystemdUnitSpec) -> ScaffoldOutput:
    """Generate a hardened <name>.service unit."""
    if spec.restart not in (
        "no",
        "on-success",
        "on-failure",
        "on-abnormal",
        "on-watchdog",
        "always",
    ):
        raise ValueError(f"invalid Restart= value '{spec.restart}'")
    name = _unit_name(spec.name)

    unit = ["[Unit]", f"Description={spec.description or spec.name}"]
    if spec.after:
        unit.append(f"After={' '.join(spec.after)}")
    if spec.wants:
        unit.append(f"Wants={' '.join(spec.wants)}")

    service = ["", "[Service]", "Type=notify" if spec.watchdog_sec else "Type=simple"]
    if spec.user:
        service.append(f"User={spec.user}")
    if spec.working_dir:
        service.append(f"WorkingDirectory={spec.working_dir}")
    for key, value in sorted(spec.environment.items()):
        service.append(f"Environment={key}={shlex.quote(value)}")
    service.append(f"ExecStart={spec.exec_start}")
    service.append(f"Restart={spec.restart}")
    service.append(f"RestartSec={spec.restart_sec}")
    if spec.watchdog_sec:
        service.append(f"WatchdogSec={spec.watchdog_sec}")
        # A watched service that keeps tripping the dog should give up, not spin.
        service.append("StartLimitIntervalSec=60")
        service.append("StartLimitBurst=4")
    if spec.memory_max:
        service.append(f"MemoryMax={spec.memory_max}")
    service.append("KillSignal=SIGTERM")
    service.append("TimeoutStopSec=10")

    install = ["", "[Install]", "WantedBy=multi-user.target"]
    content = "\n".join(unit + service + install) + "\n"

    todos = [
        f"install: sudo cp {name}.service /etc/systemd/system/ && sudo systemctl daemon-reload",
        f"enable + start: sudo systemctl enable --now {name}.service",
    ]
    if spec.watchdog_sec:
        todos.append(
            "Type=notify requires the process to call sd_notify WATCHDOG=1 within "
            f"{spec.watchdog_sec // 2}s; use the systemd/sdnotify library or drop the watchdog"
        )
    return ScaffoldOutput(files={f"{name}.service": content}, todos=todos)
