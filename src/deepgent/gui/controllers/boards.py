"""Boards/targets controller. Qt-free."""

from dataclasses import dataclass
from pathlib import Path

from deepgent.boards import (
    BoardConfig,
    add_board,
    get_board,
    load_registry,
    open_runner,
    remove_board,
)


@dataclass(frozen=True)
class BoardRow:
    """One target as flat display data."""

    id: str
    transport: str
    where: str
    type: str
    caps: str
    leased_by: str | None


class BoardsController:
    def rows(self) -> list[BoardRow]:
        from deepgent.boards import current_lease

        rows: list[BoardRow] = []
        for board in load_registry().values():
            where = (
                "this machine" if board.transport == "local" else f"{board.ssh_user}@{board.host}"
            )
            lease = current_lease(board.id)
            rows.append(
                BoardRow(
                    id=board.id,
                    transport=board.transport,
                    where=where,
                    type=board.type,
                    caps=",".join(board.capabilities) or "-",
                    leased_by=lease.holder if lease else None,
                )
            )
        return rows

    def add_ssh(
        self,
        board_id: str,
        host: str,
        ssh_user: str,
        key_path: str,
        board_type: str,
        l4t: str | None,
        capabilities: list[str],
    ) -> None:
        add_board(
            BoardConfig(
                id=board_id,
                host=host,
                ssh_user=ssh_user,
                key_path=Path(key_path),
                type=board_type,
                l4t=l4t or None,
                capabilities=capabilities,
            )
        )

    def remove(self, board_id: str) -> None:
        remove_board(board_id)

    async def test(self, board_id: str) -> str:
        board = get_board(board_id)
        async with open_runner(board) as runner:
            result = await runner.run("uname -m && uname -r", timeout_s=15)
        if result.exit_status != 0:
            raise RuntimeError(
                f"probe failed on '{board_id}' (exit {result.exit_status}): {result.stderr.strip()}"
            )
        return result.stdout.strip().replace("\n", " / ")
