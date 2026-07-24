"""Blender-style main window: a full menu bar plus a toolbar of surfaces
switching a stacked view. Panels are built lazily on first activation so
startup stays instant."""

from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import cast

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QWidget,
)

import deepgent
from deepgent.gui.history import TaskHistory
from deepgent.gui.panels.boards import BoardsPanel
from deepgent.gui.panels.containers import ContainersPanel
from deepgent.gui.panels.dashboard import DashboardPanel
from deepgent.gui.panels.differential import DifferentialPanel
from deepgent.gui.panels.evals import EvalsPanel
from deepgent.gui.panels.knowledge import KnowledgePanel
from deepgent.gui.panels.matrix import MatrixPanel
from deepgent.gui.panels.models import ModelsPanel
from deepgent.gui.panels.profiling import ProfilingPanel
from deepgent.gui.panels.run_task import RunTaskPanel
from deepgent.gui.panels.skills import SkillsPanel
from deepgent.gui.panels.telemetry import TelemetryPanel
from deepgent.gui.session import export_markdown, load_session, save_session
from deepgent.gui.widgets.animations import fade_in

_DOCS_URL = "https://github.com/Sherin-SEF-AI/deepgent"

# (label, factory) for each surface, in toolbar order.
_SURFACES: list[tuple[str, Callable[[], QWidget]]] = [
    ("Dashboard", DashboardPanel),
    ("Run Task", RunTaskPanel),
    ("Boards", BoardsPanel),
    ("Evals & Soak", EvalsPanel),
    ("Differential", DifferentialPanel),
    ("Profiling", ProfilingPanel),
    ("Models", ModelsPanel),
    ("Containers", ContainersPanel),
    ("Knowledge", KnowledgePanel),
    ("Matrix", MatrixPanel),
    ("Skills", SkillsPanel),
    ("Telemetry", TelemetryPanel),
]
_RUN_TASK = next(i for i, (label, _) in enumerate(_SURFACES) if label == "Run Task")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"deepgent {deepgent.__version__}")
        self.resize(1180, 760)
        self._history = TaskHistory()
        self._session_path: Path | None = None

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Lazy panel slots: a placeholder until first activation.
        self._factories: list[Callable[[], QWidget]] = []
        self._built: list[QWidget | None] = []
        self._surface_actions: list[QAction] = []

        toolbar = QToolBar("surfaces")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)
        group = QActionGroup(self)
        group.setExclusive(True)

        for index, (label, factory) in enumerate(_SURFACES):
            placeholder = QWidget()
            self._stack.addWidget(placeholder)
            self._factories.append(factory)
            self._built.append(None)
            action = QAction(label, self)
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, i=index: self._activate(i))
            group.addAction(action)
            toolbar.addAction(action)
            self._surface_actions.append(action)
            if index == 0:
                action.setChecked(True)

        self._build_menus()

        status = QStatusBar()
        status.showMessage(f"deepgent {deepgent.__version__}  |  ready")
        self.setStatusBar(status)

        self._activate(0)

    # --- menu bar -----------------------------------------------------------

    def _build_menus(self) -> None:
        bar = self.menuBar()

        file_menu = bar.addMenu("&File")
        self._add(file_menu, "New Task", self._new_task, "Ctrl+N")
        self._add(file_menu, "Open...", self._open, "Ctrl+O")
        self._recent_menu = file_menu.addMenu("Open Recent")
        self._recent_menu.aboutToShow.connect(self._populate_recent)
        file_menu.addSeparator()
        self._add(file_menu, "Save", self._save, "Ctrl+S")
        self._add(file_menu, "Save As...", self._save_as, "Ctrl+Shift+S")
        export_menu = file_menu.addMenu("Export")
        self._add(export_menu, "Response as Markdown...", self._export_markdown)
        self._add(export_menu, "Session as JSON...", self._save_as)
        file_menu.addSeparator()
        self._add(file_menu, "Open Runs Folder", self._open_runs_folder)
        file_menu.addSeparator()
        self._add(file_menu, "Quit", self.close, "Ctrl+Q")

        edit_menu = bar.addMenu("&Edit")
        self._add(edit_menu, "Clear Output", lambda: self._run_task().clear_output())
        edit_menu.addSeparator()
        self._add(edit_menu, "Open Config File", lambda: self._open_path(_config_path()))
        self._add(edit_menu, "Open Board Registry", lambda: self._open_path(_boards_path()))

        run_menu = bar.addMenu("&Run")
        self._add(run_menu, "Run Task", lambda: self._run_task().start_run(), "Ctrl+R")
        self._add(run_menu, "Stop", lambda: self._run_task().stop(), "Ctrl+.")
        run_menu.addSeparator()
        self._add(run_menu, "Refresh Diff", lambda: self._run_task().refresh_diff())
        self._add(run_menu, "Run Review", lambda: self._run_task().run_review())
        self._add(run_menu, "Run Tests", lambda: self._run_task().run_tests())

        go_menu = bar.addMenu("&Go")
        for index, (label, _) in enumerate(_SURFACES):
            shortcut = f"Ctrl+{(index + 1) % 10}" if index < 10 else ""
            self._add(go_menu, label, partial(self._navigate, index), shortcut)

        tools_menu = bar.addMenu("&Tools")
        self._add(tools_menu, "Host Doctor", lambda: self._navigate(0))
        self._add(tools_menu, "Build jp6 Container", self._go_containers)
        self._add(tools_menu, "Telemetry Report", self._go_telemetry)

        help_menu = bar.addMenu("&Help")
        self._add(help_menu, "Documentation", lambda: QDesktopServices.openUrl(QUrl(_DOCS_URL)))
        self._add(help_menu, "About deepgent", self._about)

    def _add(
        self, menu: QMenu, text: str, slot: Callable[[], object], shortcut: str = ""
    ) -> QAction:
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(lambda _checked=False: slot())
        menu.addAction(action)
        return action

    def _populate_recent(self) -> None:
        self._recent_menu.clear()
        recent = self._history.recent()
        if not recent:
            empty = QAction("(no recent tasks)", self)
            empty.setEnabled(False)
            self._recent_menu.addAction(empty)
            return
        for task in recent:
            label = task if len(task) <= 60 else task[:57] + "..."
            self._add(self._recent_menu, label, partial(self._open_task, task))
        self._recent_menu.addSeparator()
        self._add(self._recent_menu, "Clear History", self._history.clear)

    # --- actions ------------------------------------------------------------

    def _run_task(self) -> RunTaskPanel:
        self._navigate(_RUN_TASK)
        return cast(RunTaskPanel, self._built[_RUN_TASK])

    def _new_task(self) -> None:
        self._session_path = None
        panel = self._run_task()
        panel.clear_output()
        panel.set_task("")

    def _open_task(self, task: str) -> None:
        self._run_task().set_task(task)

    def _open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open task session", str(Path.home()), "deepgent session (*.json)"
        )
        if not path:
            return
        try:
            session = load_session(Path(path))
        except (OSError, ValueError) as exc:
            self.statusBar().showMessage(f"open failed: {exc}")
            return
        self._session_path = Path(path)
        self._run_task().load_session(session)
        self.statusBar().showMessage(f"opened {path}")

    def _save(self) -> None:
        if self._session_path is None:
            self._save_as()
            return
        save_session(self._session_path, self._run_task().to_session())
        self.statusBar().showMessage(f"saved {self._session_path}")

    def _save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save task session",
            str(Path.home() / "session.json"),
            "deepgent session (*.json)",
        )
        if not path:
            return
        self._session_path = Path(path)
        save_session(self._session_path, self._run_task().to_session())
        self.statusBar().showMessage(f"saved {path}")

    def _export_markdown(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export response", str(Path.home() / "response.md"), "Markdown (*.md)"
        )
        if not path:
            return
        export_markdown(Path(path), self._run_task().to_session())
        self.statusBar().showMessage(f"exported {path}")

    def _open_runs_folder(self) -> None:
        self._open_path(Path.cwd() / ".deepgent" / "runs")

    def _open_path(self, path: Path) -> None:
        target = path if path.exists() else path.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _go_containers(self) -> None:
        self._navigate(next(i for i, (label, _) in enumerate(_SURFACES) if label == "Containers"))

    def _go_telemetry(self) -> None:
        self._navigate(next(i for i, (label, _) in enumerate(_SURFACES) if label == "Telemetry"))

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "deepgent",
            f"deepgent {deepgent.__version__}\n\n"
            "Domain-locked autonomous engineering agent for AV, CV, and\n"
            "embedded systems. Personal project of Sherin Joseph Roy.",
        )

    # --- navigation ---------------------------------------------------------

    def _navigate(self, index: int) -> None:
        self._surface_actions[index].setChecked(True)
        self._activate(index)

    def _activate(self, index: int) -> None:
        if self._built[index] is None:
            panel = self._factories[index]()
            self._built[index] = panel
            old = self._stack.widget(index)
            self._stack.insertWidget(index, panel)
            if old is not None:
                self._stack.removeWidget(old)
                old.deleteLater()
        self._stack.setCurrentIndex(index)
        current = self._stack.currentWidget()
        if current is not None:
            fade_in(current)


def _config_path() -> Path:
    return Path.home() / ".deepgent" / "config.toml"


def _boards_path() -> Path:
    return Path.home() / ".deepgent" / "boards.toml"
