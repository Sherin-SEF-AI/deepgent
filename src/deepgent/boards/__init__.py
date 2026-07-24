"""Verification layer: board farm client, SSH runner, and on-target metrics capture."""

from deepgent.boards.catalog import (
    BOARD_CATALOG,
    BoardProfile,
    families,
    get_profile,
    list_catalog,
    render_catalog,
    suggest_capabilities,
)
from deepgent.boards.factory import open_runner
from deepgent.boards.farm import (
    SERVER_NAME,
    build_board_farm_server,
    build_board_farm_tools,
)
from deepgent.boards.leases import (
    Lease,
    acquire_lease,
    current_lease,
    new_holder_id,
    release_lease,
    require_lease,
)
from deepgent.boards.local import LocalRunner
from deepgent.boards.metrics import GenericSample, sample_once, summarize_generic
from deepgent.boards.registry import (
    BoardConfig,
    add_board,
    get_board,
    load_registry,
    register_local_target,
    registry_path,
    remove_board,
)
from deepgent.boards.runner import BoardRunner, CommandResult, watchdog_command
from deepgent.boards.tegrastats import (
    TegrastatsCapture,
    TegrastatsSample,
    energy_per_item,
    parse_capture,
    parse_line,
)

__all__ = [
    "BOARD_CATALOG",
    "SERVER_NAME",
    "BoardConfig",
    "BoardProfile",
    "BoardRunner",
    "CommandResult",
    "GenericSample",
    "Lease",
    "LocalRunner",
    "TegrastatsCapture",
    "TegrastatsSample",
    "acquire_lease",
    "add_board",
    "build_board_farm_server",
    "build_board_farm_tools",
    "current_lease",
    "energy_per_item",
    "families",
    "get_board",
    "get_profile",
    "list_catalog",
    "load_registry",
    "new_holder_id",
    "open_runner",
    "parse_capture",
    "parse_line",
    "register_local_target",
    "registry_path",
    "release_lease",
    "remove_board",
    "render_catalog",
    "require_lease",
    "sample_once",
    "suggest_capabilities",
    "summarize_generic",
    "watchdog_command",
]
