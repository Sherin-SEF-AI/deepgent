"""Shared test fixtures."""

from collections.abc import Iterator

import pytest
import structlog


@pytest.fixture(autouse=True)
def _reset_structlog() -> Iterator[None]:
    """CLI tests configure structlog against CliRunner's captured (and later
    closed) stderr; reset so other tests log to a live stream."""
    yield
    structlog.reset_defaults()
