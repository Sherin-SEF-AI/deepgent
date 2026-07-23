"""Terminal activity animations for long-running CLI commands.

A rich spinner shown on stderr while work runs, so results on stdout stay
clean and pipeable. The spinner is automatically suppressed when stderr is not
a TTY (CI, pipes, redirects) and when debug logging is on, so machine-readable
and log-heavy runs are never garbled.
"""

import asyncio
from collections.abc import Coroutine, Iterator
from contextlib import contextmanager
from typing import Any

from rich.console import Console

_console = Console(stderr=True)


@contextmanager
def activity(message: str, enabled: bool = True) -> Iterator[None]:
    """Show an animated spinner with a message while the block runs."""
    if not enabled or not _console.is_terminal:
        yield
        return
    with _console.status(f"[bold cyan]{message}", spinner="dots"):
        yield


def run_async[T](coro: Coroutine[Any, Any, T], message: str, *, spin: bool = True) -> T:
    """Run a coroutine to completion under a terminal activity spinner."""
    with activity(message, enabled=spin):
        return asyncio.run(coro)
