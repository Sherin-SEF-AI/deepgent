"""Blank-context delegation prompt assembly (expansion spec A1).

Subagent contexts are blank (CLAUDE.md section 7): a specialist knows only
what its delegation prompt carries. This module assembles that prompt from the
mandatory fields of the delegation contract, so nothing is left implicit and
every delegation is auditable.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DelegationContext:
    """Everything a subagent needs, since it shares nothing implicitly.

    task is the one required field; the rest default to empty and are omitted
    from the rendered prompt when absent, so a trivial delegation stays short.
    """

    task: str
    plan_ref: str = ""
    file_paths: tuple[str, ...] = ()
    target_metrics: tuple[str, ...] = ()
    prior_failures: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.task.strip():
            raise ValueError("delegation task must be a non-empty statement")


def _bullets(items: tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items)


def assemble_delegation_prompt(ctx: DelegationContext) -> str:
    """Render the delegation prompt. Sections with no content are omitted."""
    sections: list[str] = [f"# Task\n{ctx.task.strip()}"]
    if ctx.plan_ref:
        sections.append(f"# Approved plan\n{ctx.plan_ref.strip()}")
    if ctx.file_paths:
        sections.append(f"# Files in scope\n{_bullets(ctx.file_paths)}")
    if ctx.target_metrics:
        sections.append(f"# Target metrics (definition of done)\n{_bullets(ctx.target_metrics)}")
    if ctx.prior_failures:
        sections.append(f"# Prior failure context\n{_bullets(ctx.prior_failures)}")
    if ctx.skills:
        sections.append(f"# Load these skills first\n{_bullets(ctx.skills)}")
    sections.append(
        "# Contract\n"
        "Your context is blank apart from this prompt. Do not assume shared "
        "state. Produce production-grade work only: no stubs, placeholders, "
        "mock data, or deferred TODOs. If something cannot be completed, say so "
        "explicitly and stop rather than faking it."
    )
    return "\n\n".join(sections)


__all__ = ["DelegationContext", "assemble_delegation_prompt"]
