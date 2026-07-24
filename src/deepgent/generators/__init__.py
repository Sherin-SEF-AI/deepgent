"""Execution layer: deterministic template generators, preferred over LLM
synthesis wherever possible."""

from deepgent.generators.driver_scaffold import (
    DriverSpec,
    RegisterFact,
    ScaffoldOutput,
    scaffold_driver,
    spec_from_chunks,
)
from deepgent.generators.ros2_node import Ros2NodeSpec, scaffold_ros2_node
from deepgent.generators.systemd_unit import SystemdUnitSpec, scaffold_systemd_unit

__all__ = [
    "DriverSpec",
    "RegisterFact",
    "Ros2NodeSpec",
    "ScaffoldOutput",
    "SystemdUnitSpec",
    "scaffold_driver",
    "scaffold_ros2_node",
    "scaffold_systemd_unit",
    "spec_from_chunks",
]
