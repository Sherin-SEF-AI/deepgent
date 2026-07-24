"""Task session persistence for File > Save / Open. Qt-free.

A session is one Run Task run captured as a portable document: the task
prompt, the rendered response, the activity feed, and the diff / review / test
output, plus run metadata. Saved as JSON so a run can be reopened later or
shared, and the response can be exported as Markdown.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

_SCHEMA = "deepgent.task-session/1"


@dataclass
class TaskSession:
    """A saved Run Task run."""

    task: str = ""
    response: str = ""
    activity: str = ""
    diff: str = ""
    review: str = ""
    tests: str = ""
    session_id: str = ""
    total_cost_usd: float | None = None
    num_turns: int = 0

    def to_dict(self) -> dict[str, object]:
        return {"schema": _SCHEMA, **asdict(self)}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "TaskSession":
        fields = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**fields)  # type: ignore[arg-type]


def save_session(path: Path, session: TaskSession) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session.to_dict(), indent=2))


def load_session(path: Path) -> TaskSession:
    return TaskSession.from_dict(json.loads(path.read_text()))


def export_markdown(path: Path, session: TaskSession) -> None:
    """Write just the response as a Markdown document."""
    header = f"# Task\n\n{session.task}\n\n# Response\n\n"
    path.write_text(header + (session.response or "(no response)") + "\n")
