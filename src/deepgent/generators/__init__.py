"""Execution layer: deterministic template generators, preferred over LLM
synthesis wherever possible."""

from deepgent.generators.driver_scaffold import (
    DriverSpec,
    RegisterFact,
    ScaffoldOutput,
    scaffold_driver,
    spec_from_chunks,
)

__all__ = [
    "DriverSpec",
    "RegisterFact",
    "ScaffoldOutput",
    "scaffold_driver",
    "spec_from_chunks",
]
