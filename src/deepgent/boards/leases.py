"""Board lease model (section 14): one task per board, leases auto-expire.

Leases are JSON files under ~/.deepgent/leases/, created with O_EXCL so two
processes on the same host cannot both win a free board. Expired leases are
reclaimable by anyone; releases require the owning holder.
"""

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import structlog

from deepgent.errors import BoardError

_logger = structlog.get_logger(__name__)

LEASES_RELPATH = Path(".deepgent") / "leases"
DEFAULT_LEASE_TTL_S = 3600.0


def leases_dir() -> Path:
    return Path.home() / LEASES_RELPATH


def new_holder_id() -> str:
    return f"holder-{os.getpid()}-{uuid.uuid4().hex[:8]}"


@dataclass(frozen=True)
class Lease:
    """An active claim on one board."""

    board_id: str
    holder: str
    acquired_at: float
    expires_at: float

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at


def _lease_path(board_id: str) -> Path:
    return leases_dir() / f"{board_id}.json"


def _read_lease(path: Path) -> Lease | None:
    try:
        data = json.loads(path.read_text())
        return Lease(**data)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, TypeError):
        _logger.warning("lease_file_corrupt", path=str(path))
        return None


def current_lease(board_id: str) -> Lease | None:
    """The active (non-expired) lease on a board, if any."""
    lease = _read_lease(_lease_path(board_id))
    if lease is None or lease.expired:
        return None
    return lease


def acquire_lease(board_id: str, holder: str, ttl_s: float = DEFAULT_LEASE_TTL_S) -> Lease:
    """Claim a board, replacing only expired or corrupt leases."""
    path = _lease_path(board_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = _read_lease(path)
    if existing is not None and not existing.expired and existing.holder != holder:
        remaining = existing.expires_at - time.time()
        raise BoardError(
            f"board '{board_id}' is leased by {existing.holder} for another "
            f"{remaining:.0f}s; retry later or wait for expiry"
        )
    if existing is not None or path.exists():
        path.unlink(missing_ok=True)

    now = time.time()
    lease = Lease(board_id=board_id, holder=holder, acquired_at=now, expires_at=now + ttl_s)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise BoardError(f"board '{board_id}' was leased concurrently; retry") from exc
    with os.fdopen(fd, "w") as f:
        json.dump(asdict(lease), f)
    _logger.info("lease_acquired", board=board_id, holder=holder, ttl_s=ttl_s)
    return lease


def release_lease(board_id: str, holder: str) -> None:
    """Release a lease held by this holder; expired leases release freely."""
    path = _lease_path(board_id)
    lease = _read_lease(path)
    if lease is None:
        return
    if not lease.expired and lease.holder != holder:
        raise BoardError(
            f"board '{board_id}' is leased by {lease.holder}, not {holder}; "
            "refusing to release someone else's lease"
        )
    path.unlink(missing_ok=True)
    _logger.info("lease_released", board=board_id, holder=holder)


def require_lease(board_id: str, holder: str) -> Lease:
    """Assert this holder owns an active lease on the board."""
    lease = current_lease(board_id)
    if lease is None or lease.holder != holder:
        raise BoardError(
            f"operation on board '{board_id}' requires an active lease; call the lease tool first"
        )
    return lease
