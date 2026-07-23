"""Terminal activity spinner helper (TUI animations)."""

import asyncio

import pytest

from deepgent.cli.progress import activity, run_async

pytestmark = pytest.mark.unit


def test_activity_is_a_noop_when_disabled() -> None:
    entered = False
    with activity("working", enabled=False):
        entered = True
    assert entered is True


def test_activity_noop_when_not_a_tty() -> None:
    # The test stderr is not a TTY, so the spinner is suppressed but the block
    # still runs and yields normally.
    with activity("working", enabled=True):
        value = 21 * 2
    assert value == 42


def test_run_async_returns_result() -> None:
    async def work() -> str:
        await asyncio.sleep(0)
        return "done"

    # spin=False keeps it a plain asyncio.run under the hood.
    assert run_async(work(), "running", spin=False) == "done"


def test_run_async_propagates_exceptions() -> None:
    async def boom() -> None:
        raise ValueError("nope")

    with pytest.raises(ValueError, match="nope"):
        run_async(boom(), "running", spin=False)
