"""Recent-task history for the GUI 'Open Recent' menu. Qt-free.

Stores the raw task prompts the user ran (telemetry keeps stats, not the
prompt text) in a small JSON file under ~/.deepgent, most-recent first,
deduplicated and capped.
"""

import json
from pathlib import Path

_RELPATH = Path(".deepgent") / "task_history.json"
_CAP = 30


def default_history_path() -> Path:
    return Path.home() / _RELPATH


class TaskHistory:
    """A capped, deduplicated most-recent-first list of task prompts."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path if path is not None else default_history_path()

    def recent(self, limit: int = 15) -> list[str]:
        if not self._path.is_file():
            return []
        try:
            data = json.loads(self._path.read_text())
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        return [str(item) for item in data[:limit]]

    def add(self, task: str) -> None:
        task = task.strip()
        if not task:
            return
        items = [t for t in self.recent(limit=_CAP) if t != task]
        items.insert(0, task)
        items = items[:_CAP]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(items, indent=2))

    def clear(self) -> None:
        if self._path.is_file():
            self._path.unlink()
