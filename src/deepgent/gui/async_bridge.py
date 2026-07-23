"""Bridge between deepgent's async core and the Qt event loop.

The whole GUI runs on a single qasync event loop, so coroutines (task runs,
board ops, container builds, soak) execute cooperatively without a worker
thread and without ever blocking the UI. AsyncTask wraps one coroutine as a
cancellable unit that emits Qt signals on completion or failure; callers
connect to the signals and never await.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from PySide6.QtCore import QObject, Signal


class AsyncTask(QObject):
    """Runs one coroutine on the running event loop and reports via signals.

    finished(object): emitted with the coroutine's result on success.
    failed(str): emitted with the exception message on error.
    done(): emitted after either outcome (success, failure, or cancel).
    """

    finished = Signal(object)
    failed = Signal(str)
    done = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._task: asyncio.Task[Any] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self, coro_factory: Callable[[], Awaitable[Any]]) -> None:
        """Schedule coro_factory() on the loop. A prior run must be finished."""
        if self.running:
            raise RuntimeError("AsyncTask is already running")
        self._task = asyncio.ensure_future(self._runner(coro_factory))

    def cancel(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()

    async def _runner(self, coro_factory: Callable[[], Awaitable[Any]]) -> None:
        try:
            result = await coro_factory()
        except asyncio.CancelledError:
            self.done.emit()
            raise
        except Exception as exc:  # surfaced to the UI, never swallowed
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            self.done.emit()
            return
        self.finished.emit(result)
        self.done.emit()


def run_soon(coro: Awaitable[Any]) -> asyncio.Task[Any]:
    """Schedule a fire-and-forget coroutine on the running loop."""
    return asyncio.ensure_future(coro)
