"""Blender-style main window: a toolbar of surfaces switching a stacked view,
plus a dockable log/console. Panels are built lazily on first activation so
startup stays instant."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QWidget,
)

import deepgent
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
from deepgent.gui.widgets.animations import fade_in

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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"deepgent {deepgent.__version__}")
        self.resize(1180, 760)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Lazy panel slots: a placeholder until first activation.
        self._factories: list[Callable[[], QWidget]] = []
        self._built: list[QWidget | None] = []

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
            if index == 0:
                action.setChecked(True)

        status = QStatusBar()
        status.showMessage(f"deepgent {deepgent.__version__}  |  ready")
        self.setStatusBar(status)

        self._activate(0)

    def _activate(self, index: int) -> None:
        if self._built[index] is None:
            panel = self._factories[index]()
            self._built[index] = panel
            # Replace the placeholder at this index.
            old = self._stack.widget(index)
            self._stack.insertWidget(index, panel)
            if old is not None:
                self._stack.removeWidget(old)
                old.deleteLater()
        self._stack.setCurrentIndex(index)
        current = self._stack.currentWidget()
        if current is not None:
            fade_in(current)
