"""Async SSH runner for target boards (sections 14 and 20).

Key auth only, no agent forwarding, host keys verified against the user's
known_hosts. Every remote command runs under a server-side watchdog
(coreutils timeout) plus a client-side deadline, so a wedged board never
hangs a task and never keeps stray processes.
"""

import asyncio
import shlex
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

import asyncssh
import structlog

from deepgent.boards.registry import BoardConfig
from deepgent.errors import BoardError

_logger = structlog.get_logger(__name__)

_CONNECT_TIMEOUT_S = 15.0
_CLIENT_GRACE_S = 10.0
_WATCHDOG_EXIT = 124  # coreutils timeout's exit status on expiry


@dataclass(frozen=True)
class CommandResult:
    """Outcome of one remote command."""

    command: str
    exit_status: int
    stdout: str
    stderr: str
    timed_out: bool


def watchdog_command(command: str, timeout_s: float) -> str:
    """Wrap a command in a server-side watchdog that kills it on expiry."""
    return f"timeout --kill-after=5 {int(timeout_s)} bash -c {shlex.quote(command)}"


class BoardRunner:
    """One SSH session to a registered board."""

    def __init__(self, board: BoardConfig) -> None:
        self._board = board
        self._conn: asyncssh.SSHClientConnection | None = None

    async def __aenter__(self) -> "BoardRunner":
        key_path = self._board.expanded_key_path
        if not key_path.is_file():
            raise BoardError(
                f"ssh key {key_path} for board '{self._board.id}' does not "
                "exist; fix key_path in the board registry"
            )
        try:
            self._conn = await asyncio.wait_for(
                asyncssh.connect(
                    self._board.host,
                    username=self._board.ssh_user,
                    client_keys=[str(key_path)],
                    agent_path=None,  # section 20: no agent forwarding
                ),
                timeout=_CONNECT_TIMEOUT_S,
            )
        except asyncssh.HostKeyNotVerifiable as exc:
            raise BoardError(
                f"host key for {self._board.host} is not in known_hosts; "
                f"connect once manually (ssh {self._board.ssh_user}@"
                f"{self._board.host}) to trust it, then retry"
            ) from exc
        except (OSError, asyncssh.Error, TimeoutError) as exc:
            raise BoardError(
                f"cannot reach board '{self._board.id}' at "
                f"{self._board.ssh_user}@{self._board.host}: {exc}"
            ) from exc
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._conn is not None:
            self._conn.close()
            await self._conn.wait_closed()
            self._conn = None

    def _connection(self) -> asyncssh.SSHClientConnection:
        if self._conn is None:
            raise BoardError("board connection is not open; use 'async with'")
        return self._conn

    async def run(self, command: str, timeout_s: float = 60.0) -> CommandResult:
        """Run a command under the watchdog and return its result."""
        conn = self._connection()
        wrapped = watchdog_command(command, timeout_s)
        log = _logger.bind(board=self._board.id)
        log.debug("board_exec", command=command, timeout_s=timeout_s)
        try:
            completed = await asyncio.wait_for(
                conn.run(wrapped, check=False),
                timeout=timeout_s + _CLIENT_GRACE_S,
            )
        except TimeoutError as exc:
            raise BoardError(
                f"board '{self._board.id}' did not return within "
                f"{timeout_s + _CLIENT_GRACE_S:.0f}s even after the remote "
                "watchdog; the connection is likely dead"
            ) from exc
        exit_status = completed.exit_status if completed.exit_status is not None else -1
        result = CommandResult(
            command=command,
            exit_status=exit_status,
            stdout=str(completed.stdout or ""),
            stderr=str(completed.stderr or ""),
            timed_out=exit_status == _WATCHDOG_EXIT,
        )
        log.debug("board_exec_done", exit_status=result.exit_status, timed_out=result.timed_out)
        return result

    async def put(self, local: Path, remote: str) -> None:
        """Copy a local file to the board via SFTP."""
        conn = self._connection()
        async with conn.start_sftp_client() as sftp:
            await sftp.put(str(local), remote)

    async def get(self, remote: str, local: Path) -> None:
        """Copy a remote file from the board via SFTP."""
        conn = self._connection()
        async with conn.start_sftp_client() as sftp:
            await sftp.get(remote, str(local))

    async def capture_tegrastats(self, duration_s: float, interval_ms: int = 500) -> str:
        """Run tegrastats for duration_s and return the raw capture text.

        The watchdog doubles as the sampler's stop condition, so tegrastats
        can never outlive the capture window.
        """
        result = await self.run(f"tegrastats --interval {interval_ms}", timeout_s=duration_s)
        # Exit 124 is expected: the watchdog is what stops tegrastats.
        if not result.timed_out and result.exit_status != 0:
            raise BoardError(
                f"tegrastats failed on board '{self._board.id}' "
                f"(exit {result.exit_status}): {result.stderr.strip()}"
            )
        return result.stdout

    async def capture_metrics(self, duration_s: float, interval_ms: int = 500) -> dict[str, float]:
        """Summary metrics from an on-board tegrastats capture.

        The universal counterpart to LocalRunner.capture_metrics so soak,
        differential, and the farm score the same shape regardless of
        transport. A board without tegrastats yields an empty summary rather
        than raising, so non-Jetson SSH targets still run.
        """
        from deepgent.boards.tegrastats import parse_capture

        try:
            raw = await self.capture_tegrastats(duration_s, interval_ms)
        except BoardError:
            _logger.warning("capture_metrics_unavailable", board=self._board.id)
            return {"samples": 0.0}
        return parse_capture(raw).summary_metrics(interval_ms=interval_ms)
