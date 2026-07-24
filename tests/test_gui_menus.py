"""Task history, session save/open, and the application menu bar."""

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from deepgent.gui.history import TaskHistory
from deepgent.gui.session import (
    TaskSession,
    export_markdown,
    load_session,
    save_session,
)

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    return app


# --- history ----------------------------------------------------------------


def test_history_add_dedup_order(tmp_path: Path) -> None:
    h = TaskHistory(tmp_path / "hist.json")
    assert h.recent() == []
    h.add("first task")
    h.add("second task")
    h.add("first task")  # re-adding moves it to front, no duplicate
    assert h.recent() == ["first task", "second task"]


def test_history_ignores_blank_and_persists(tmp_path: Path) -> None:
    path = tmp_path / "hist.json"
    TaskHistory(path).add("  ")
    assert TaskHistory(path).recent() == []
    TaskHistory(path).add("real")
    assert TaskHistory(path).recent() == ["real"]  # reloaded from disk


def test_history_clear(tmp_path: Path) -> None:
    h = TaskHistory(tmp_path / "hist.json")
    h.add("x")
    h.clear()
    assert h.recent() == []


# --- session ----------------------------------------------------------------


def test_session_round_trip(tmp_path: Path) -> None:
    session = TaskSession(
        task="quantize the detector",
        response="# Done\n\nBuilt the engine.",
        activity="-> Edit: a.py",
        diff="+x = 1",
        review="All checks passed!",
        tests="1 passed",
        session_id="abc123",
        total_cost_usd=0.12,
        num_turns=4,
    )
    path = tmp_path / "s.json"
    save_session(path, session)
    loaded = load_session(path)
    assert loaded.task == session.task
    assert loaded.response == session.response
    assert loaded.total_cost_usd == pytest.approx(0.12)


def test_session_from_dict_tolerates_extra_keys() -> None:
    s = TaskSession.from_dict({"schema": "x", "task": "t", "bogus": 1})
    assert s.task == "t"


def test_export_markdown(tmp_path: Path) -> None:
    session = TaskSession(task="do it", response="## Result\n\nok")
    path = tmp_path / "r.md"
    export_markdown(path, session)
    text = path.read_text()
    assert "# Task" in text and "do it" in text and "## Result" in text


# --- menu bar ---------------------------------------------------------------


def test_menu_bar_has_expected_menus(qapp: QApplication) -> None:
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QMenu

    from deepgent.gui.main_window import MainWindow

    window = MainWindow()
    menus = {m.title().replace("&", "") for m in window.findChildren(QMenu)}
    assert {"File", "Edit", "Run", "Go", "Tools", "Help"} <= menus
    actions = {a.text() for a in window.findChildren(QAction)}
    assert {"New Task", "Open...", "Save", "Save As...", "Quit", "Run Task"} <= actions
    window.deleteLater()


def test_new_task_and_session_capture(qapp: QApplication, tmp_path: Path) -> None:
    from deepgent.gui.main_window import MainWindow

    window = MainWindow()
    panel = window._run_task()  # builds + navigates to Run Task
    panel.set_task("profile the pipeline")
    session = panel.to_session()
    assert session.task == "profile the pipeline"
    # New Task clears the input.
    window._new_task()
    assert panel.to_session().task == ""
    window.deleteLater()
