"""Differential panel: run one artifact across boards and compare."""

from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from deepgent.evals.differential import DifferentialResult
from deepgent.gui.async_bridge import AsyncTask
from deepgent.gui.controllers.operations import EvalsController
from deepgent.gui.widgets.common import LogView, toolbar_button


class DifferentialPanel(QWidget):
    def __init__(self, controller: EvalsController | None = None) -> None:
        super().__init__()
        self._controller = controller if controller is not None else EvalsController()
        self._task = AsyncTask(self)
        self._task.finished.connect(self._on_result)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        note = QLabel("Run one artifact across boards; compare latency, power, energy, cost.")
        note.setProperty("role", "dim")
        root.addWidget(note)

        row = QHBoxLayout()
        row.setSpacing(4)
        self._artifact = QLineEdit()
        self._artifact.setPlaceholderText("local artifact path")
        self._boards = QLineEdit()
        self._boards.setPlaceholderText("board ids, comma-separated")
        self._command = QLineEdit()
        self._command.setPlaceholderText("run command")
        btn = toolbar_button("Run differential", role="accent")
        btn.clicked.connect(self._on_run)
        row.addWidget(self._artifact, 1)
        row.addWidget(self._boards, 1)
        row.addWidget(self._command, 1)
        row.addWidget(btn)
        root.addLayout(row)

        self._log = LogView()
        root.addWidget(self._log, 1)

        self._task.failed.connect(lambda m: self._log.append_line(f"[error] {m}"))

    def _on_run(self) -> None:
        artifact = self._artifact.text().strip()
        boards = [b.strip() for b in self._boards.text().split(",") if b.strip()]
        command = self._command.text().strip()
        if not (artifact and boards and command) or self._task.running:
            return
        self._log.append_line(f"running {artifact} across {', '.join(boards)}...")
        self._task.start(lambda: self._controller.differential(Path(artifact), boards, command))

    def _on_result(self, result: object) -> None:
        assert isinstance(result, DifferentialResult)
        self._log.append_line(result.render_table())
