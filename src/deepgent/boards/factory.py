"""Runner factory: pick the execution transport for a target.

A registered target is either SSH-attached (BoardRunner) or the local host
(LocalRunner). Both expose run/put/get and capture_metrics, so every caller
(farm, soak, differential, evals) works uniformly across transports.
"""

from deepgent.boards.local import LocalRunner
from deepgent.boards.registry import BoardConfig
from deepgent.boards.runner import BoardRunner


def open_runner(board: BoardConfig) -> BoardRunner | LocalRunner:
    """The runner for a target, chosen by its transport."""
    if board.transport == "local":
        return LocalRunner(board.id)
    return BoardRunner(board)
