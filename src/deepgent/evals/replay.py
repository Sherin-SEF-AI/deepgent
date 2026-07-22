"""deepgent replay: record real sensor streams on-target, replay as fixtures.

Recording pulls a bounded stream file off the board (rosbag, raw capture, or
any command-produced artifact) and stores it content-addressed with a
manifest. Replay pushes the fixture back and runs the consumer under it, so
perception changes regression-test against captured reality deterministically.

The fixture format is transport-agnostic: deepgent records whatever the
record command writes and replays it through whatever the replay command
reads. Determinism comes from the fixture bytes being identical run to run
(verified by hash), not from deepgent understanding the sensor protocol.
"""

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import structlog

from deepgent.boards import BoardRunner, get_board
from deepgent.errors import BoardError

_logger = structlog.get_logger(__name__)

FIXTURES_RELPATH = Path(".deepgent") / "fixtures"
MANIFEST_NAME = "fixture.json"


@dataclass(frozen=True)
class FixtureManifest:
    """Provenance for one recorded stream."""

    name: str
    board: str
    record_command: str
    remote_path: str
    sha256: str
    size_bytes: int
    recorded_at: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def fixtures_dir(project_root: Path) -> Path:
    return project_root / FIXTURES_RELPATH


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(project_root: Path, name: str) -> FixtureManifest | None:
    manifest_path = fixtures_dir(project_root) / name / MANIFEST_NAME
    if not manifest_path.is_file():
        return None
    data = json.loads(manifest_path.read_text())
    return FixtureManifest(**data)


def list_fixtures(project_root: Path) -> list[FixtureManifest]:
    root = fixtures_dir(project_root)
    if not root.is_dir():
        return []
    manifests = []
    for entry in sorted(root.iterdir()):
        manifest = load_manifest(project_root, entry.name)
        if manifest is not None:
            manifests.append(manifest)
    return manifests


class ReplayRecorder:
    """Records and replays sensor-stream fixtures against a board."""

    def __init__(self, board_id: str, project_root: Path) -> None:
        self._board_id = board_id
        self._project_root = project_root

    async def record(
        self,
        name: str,
        record_command: str,
        remote_path: str,
        duration_s: float = 30.0,
    ) -> FixtureManifest:
        """Run record_command on the board, pull remote_path into the fixture
        store, and write a manifest."""
        board = get_board(self._board_id)
        target = fixtures_dir(self._project_root) / name
        target.mkdir(parents=True, exist_ok=True)
        local = target / "stream.bin"

        async with BoardRunner(board) as runner:
            capture = await runner.run(record_command, timeout_s=duration_s)
            if capture.exit_status != 0 and not capture.timed_out:
                raise BoardError(
                    f"record command failed on '{self._board_id}' "
                    f"(exit {capture.exit_status}): {capture.stderr.strip()}"
                )
            await runner.get(remote_path, local)

        manifest = FixtureManifest(
            name=name,
            board=self._board_id,
            record_command=record_command,
            remote_path=remote_path,
            sha256=_sha256(local),
            size_bytes=local.stat().st_size,
            recorded_at=time.time(),
        )
        (target / MANIFEST_NAME).write_text(json.dumps(manifest.to_dict(), indent=2))
        _logger.info("fixture_recorded", name=name, sha256=manifest.sha256)
        return manifest

    async def replay(
        self, name: str, replay_command: str, remote_path: str, timeout_s: float = 120.0
    ) -> tuple[int, str]:
        """Push the fixture back and run replay_command against it.

        Verifies the local fixture still matches its manifest hash before
        deploying, so a corrupted fixture can never silently change results.
        Returns (exit_status, output).
        """
        manifest = load_manifest(self._project_root, name)
        if manifest is None:
            raise BoardError(f"fixture '{name}' not found under {fixtures_dir(self._project_root)}")
        local = fixtures_dir(self._project_root) / name / "stream.bin"
        actual = _sha256(local)
        if actual != manifest.sha256:
            raise BoardError(
                f"fixture '{name}' hash mismatch (manifest {manifest.sha256[:12]}, "
                f"file {actual[:12]}); the fixture is corrupt, refusing to replay"
            )
        board = get_board(self._board_id)
        async with BoardRunner(board) as runner:
            await runner.put(local, remote_path)
            result = await runner.run(replay_command, timeout_s=timeout_s)
        _logger.info("fixture_replayed", name=name, exit_status=result.exit_status)
        return result.exit_status, result.stdout + result.stderr
