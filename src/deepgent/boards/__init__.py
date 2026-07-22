"""Verification layer: board farm client, SSH runner, and on-target metrics capture."""

from deepgent.boards.registry import (
    BoardConfig,
    add_board,
    get_board,
    load_registry,
    registry_path,
    remove_board,
)
from deepgent.boards.runner import BoardRunner, CommandResult, watchdog_command
from deepgent.boards.tegrastats import (
    TegrastatsCapture,
    TegrastatsSample,
    parse_capture,
    parse_line,
)

__all__ = [
    "BoardConfig",
    "BoardRunner",
    "CommandResult",
    "TegrastatsCapture",
    "TegrastatsSample",
    "add_board",
    "get_board",
    "load_registry",
    "parse_capture",
    "parse_line",
    "registry_path",
    "remove_board",
    "watchdog_command",
]
