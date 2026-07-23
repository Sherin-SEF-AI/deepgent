"""Local execution runner: run tasks on the machine deepgent runs on.

Mirrors the BoardRunner interface (async context manager; run/put/get and a
metrics capture) but executes through local subprocesses and file copies
instead of SSH. This is what makes deepgent target desktops, laptops, and
the Pi/host it is installed on, not only SSH-attached boards.
"""

import asyncio
import contextlib
import os
import shutil
import signal
from pathlib import Path
from types import TracebackType

import structlog

from deepgent.boards.metrics import sample_once, summarize_generic
from deepgent.boards.runner import CommandResult
from deepgent.errors import BoardError

_logger = structlog.get_logger(__name__)

# Unlike the SSH runner, the local runner has no server-side watchdog, so
# the client deadline is the sole enforcement: keep the grace small.
_CLIENT_GRACE_S = 0.5
_SIGKILL_GRACE_S = 2.0


class LocalRunner:
    """Runs commands on the local host with the BoardRunner interface."""

    def __init__(self, board_id: str = "local") -> None:
        self._board_id = board_id

    async def __aenter__(self) -> "LocalRunner":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def run(self, command: str, timeout_s: float = 60.0) -> CommandResult:
        """Run a shell command locally under a wall-clock timeout.

        The child runs in its own process group so a timeout or a cancelled
        awaiting task terminates the whole tree (the shell and anything it
        spawned), never leaving orphans. On timeout the group gets SIGTERM,
        then SIGKILL after a short grace.
        """
        log = _logger.bind(board=self._board_id)
        log.debug("local_exec", command=command, timeout_s=timeout_s)
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,  # new process group; kill the whole tree
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_s + _CLIENT_GRACE_S
            )
            timed_out = False
        except TimeoutError:
            await self._terminate_group(proc)
            stdout, stderr = b"", b"local command exceeded timeout"
            timed_out = True
        except asyncio.CancelledError:
            # A cancelled task must not leak the child process group.
            await self._terminate_group(proc)
            raise
        exit_status = proc.returncode if proc.returncode is not None else -1
        return CommandResult(
            command=command,
            exit_status=124 if timed_out else exit_status,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
            timed_out=timed_out,
        )

    @staticmethod
    async def _terminate_group(proc: "asyncio.subprocess.Process") -> None:
        """SIGTERM then SIGKILL the child's process group, reaping it."""
        if proc.returncode is not None:
            return
        pid = proc.pid
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        try:
            await asyncio.wait_for(proc.wait(), timeout=_SIGKILL_GRACE_S)
            return
        except TimeoutError:
            pass
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        # Reap the killed process so it does not linger as a zombie. The
        # process is dead after SIGKILL; wait() returns its status promptly.
        await proc.wait()

    async def put(self, local: Path, remote: str) -> None:
        """Copy a file to a local destination (deploy is a copy here)."""
        dest = Path(remote)
        dest.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2, local, dest)

    async def get(self, remote: str, local: Path) -> None:
        source = Path(remote)
        if not source.is_file():
            raise BoardError(f"local source {source} does not exist")
        await asyncio.to_thread(shutil.copy2, source, local)

    async def capture_metrics(self, duration_s: float, interval_ms: int = 500) -> dict[str, float]:
        """Sample generic host metrics for a duration and summarize them."""
        samples = []
        deadline = asyncio.get_event_loop().time() + duration_s
        interval_s = max(interval_ms / 1000.0, 0.05)
        while asyncio.get_event_loop().time() < deadline:
            samples.append(await asyncio.to_thread(sample_once))
            await asyncio.sleep(interval_s)
        return summarize_generic(samples, interval_ms=interval_ms)
