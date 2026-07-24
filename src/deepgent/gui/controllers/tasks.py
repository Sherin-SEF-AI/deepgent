"""Task controller: run an agent task and inspect the resulting code. Qt-free."""

import asyncio
from collections.abc import Callable
from pathlib import Path

from deepgent.config import load_settings
from deepgent.core import CommandRun, Orchestrator, TaskEvent, TaskOutcome
from deepgent.core.workcapture import (
    default_review_command,
    default_test_command,
    git_diff,
    run_check,
)


class TaskController:
    """Runs one agent task and surfaces its code, review, and test evidence."""

    def __init__(self, cwd: Path | None = None) -> None:
        self._cwd = cwd if cwd is not None else Path.cwd()

    async def run(
        self,
        task: str,
        budget: float | None,
        on_text: Callable[[str], None],
        on_event: Callable[[TaskEvent], None] | None = None,
        ci: bool = True,
    ) -> TaskOutcome:
        """Run task to completion. ci=True auto-denies gated board ops."""
        settings = load_settings().model_copy(update={"ci": ci}, deep=True)
        if budget is not None:
            settings.budget.per_task_usd = budget
        orchestrator = Orchestrator(settings=settings, cwd=self._cwd)
        return await orchestrator.run_task(task, on_text=on_text, on_event=on_event)

    # --- code cockpit (post-run inspection, off the UI thread) --------------

    def default_review_command(self) -> str:
        return default_review_command(self._cwd)

    def default_test_command(self) -> str:
        return default_test_command(self._cwd)

    async def diff(self) -> str:
        """The git diff of what the task changed."""
        return await asyncio.to_thread(git_diff, self._cwd)

    async def review(self, command: str) -> CommandRun:
        """Run a review command (default: ruff) over the workspace."""
        return await asyncio.to_thread(run_check, self._cwd, command)

    async def test(self, command: str) -> CommandRun:
        """Run the project's test command and capture pass/fail."""
        return await asyncio.to_thread(run_check, self._cwd, command)
