"""Board registry backed by ~/.deepgent/boards.toml (section 14).

Boards are added via `deepgent boards add`, never hardcoded. The registry
file stays outside the repo and is never committed (section 20).
"""

import tomllib
from pathlib import Path
from typing import Any, Literal

import tomli_w
from pydantic import BaseModel, Field, ValidationError

from deepgent.errors import BoardError

REGISTRY_RELPATH = Path(".deepgent") / "boards.toml"


class BoardConfig(BaseModel):
    """One registered target board."""

    id: str
    host: str
    ssh_user: str
    key_path: Path
    type: str
    l4t: str | None = None
    os: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    power_ctl: Literal["none", "smartplug", "pdu"] = "none"

    @property
    def expanded_key_path(self) -> Path:
        return self.key_path.expanduser()


def registry_path() -> Path:
    return Path.home() / REGISTRY_RELPATH


def load_registry() -> dict[str, BoardConfig]:
    """Load all registered boards, keyed by board id."""
    path = registry_path()
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise BoardError(f"invalid TOML in {path}: {exc}") from exc
    boards: dict[str, BoardConfig] = {}
    for board_id, table in raw.get("boards", {}).items():
        try:
            boards[board_id] = BoardConfig(id=board_id, **table)
        except ValidationError as exc:
            raise BoardError(f"invalid board '{board_id}' in {path}: {exc}") from exc
    return boards


def _save_registry(boards: dict[str, BoardConfig]) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tables: dict[str, dict[str, Any]] = {}
    for board_id, board in sorted(boards.items()):
        table = board.model_dump(mode="json", exclude={"id"}, exclude_none=True)
        tables[board_id] = table
    with path.open("wb") as f:
        tomli_w.dump({"boards": tables}, f)


def get_board(board_id: str) -> BoardConfig:
    boards = load_registry()
    if board_id not in boards:
        registered = ", ".join(sorted(boards)) or "none"
        raise BoardError(
            f"board '{board_id}' is not registered (registered: {registered}); "
            "add it with: deepgent boards add"
        )
    return boards[board_id]


def add_board(board: BoardConfig) -> None:
    boards = load_registry()
    if board.id in boards:
        raise BoardError(
            f"board '{board.id}' already exists; remove it first with: "
            f"deepgent boards remove {board.id}"
        )
    boards[board.id] = board
    _save_registry(boards)


def remove_board(board_id: str) -> None:
    boards = load_registry()
    if board_id not in boards:
        raise BoardError(f"board '{board_id}' is not registered")
    del boards[board_id]
    _save_registry(boards)
