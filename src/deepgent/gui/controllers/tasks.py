"""Task controller: run an agent task with live streaming. Qt-free."""

from collections.abc import Callable
from pathlib import Path

from deepgent.config import load_settings
from deepgent.core import Orchestrator, TaskOutcome


class TaskController:
    """Runs one agent task, streaming assistant text to a callback."""

    def __init__(self, cwd: Path | None = None) -> None:
        self._cwd = cwd if cwd is not None else Path.cwd()

    async def run(
        self,
        task: str,
        budget: float | None,
        on_text: Callable[[str], None],
        ci: bool = True,
    ) -> TaskOutcome:
        """Run task to completion. ci=True auto-denies gated board ops."""
        settings = load_settings().model_copy(update={"ci": ci}, deep=True)
        if budget is not None:
            settings.budget.per_task_usd = budget
        orchestrator = Orchestrator(settings=settings, cwd=self._cwd)
        return await orchestrator.run_task(task, on_text=on_text)
