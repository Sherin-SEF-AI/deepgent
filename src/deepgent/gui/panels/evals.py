"""Evals & Soak panel: run a golden and score it, or run an endurance soak."""

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from deepgent.evals import GoldenRunResult, create_run_dir
from deepgent.evals.soak import SoakResult
from deepgent.gui.async_bridge import AsyncTask
from deepgent.gui.controllers.operations import EvalsController
from deepgent.gui.widgets.animations import Spinner, bind_spinner
from deepgent.gui.widgets.common import LogView, toolbar_button


class EvalsPanel(QWidget):
    def __init__(self, controller: EvalsController | None = None) -> None:
        super().__init__()
        self._controller = controller if controller is not None else EvalsController()
        self._golden = AsyncTask(self)
        self._golden.finished.connect(self._on_golden)
        self._soak = AsyncTask(self)
        self._soak.finished.connect(self._on_soak)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Golden row.
        golden_row = QHBoxLayout()
        golden_row.setSpacing(4)
        golden_row.addWidget(QLabel("golden"))
        self._golden_pick = QComboBox()
        self._golden_pick.addItems(self._controller.golden_ids() or ["(none found)"])
        run_golden_btn = toolbar_button("Run golden", role="accent")
        run_golden_btn.clicked.connect(self._on_run_golden)
        golden_row.addWidget(self._golden_pick, 1)
        golden_row.addWidget(run_golden_btn)
        root.addLayout(golden_row)

        # Soak row.
        soak_row = QHBoxLayout()
        soak_row.setSpacing(4)
        soak_row.addWidget(QLabel("soak board"))
        self._soak_board = QLineEdit()
        self._soak_board.setPlaceholderText("board id (e.g. local, agx-orin)")
        self._soak_hours = QDoubleSpinBox()
        self._soak_hours.setRange(0.01, 72.0)
        self._soak_hours.setValue(0.05)
        self._soak_hours.setSuffix(" h")
        self._soak_workload = QLineEdit()
        self._soak_workload.setPlaceholderText("optional workload command")
        run_soak_btn = toolbar_button("Run soak")
        run_soak_btn.clicked.connect(self._on_run_soak)
        soak_row.addWidget(self._soak_board, 1)
        soak_row.addWidget(self._soak_hours)
        soak_row.addWidget(self._soak_workload, 1)
        soak_row.addWidget(run_soak_btn)
        root.addLayout(soak_row)

        self._log = LogView()
        root.addWidget(self._log, 1)

        self._spinner = Spinner()
        bind_spinner(self._golden, self._spinner)
        bind_spinner(self._soak, self._spinner)
        root.addWidget(self._spinner)

        self._golden.failed.connect(lambda m: self._log.append_line(f"[error] {m}"))
        self._soak.failed.connect(lambda m: self._log.append_line(f"[error] {m}"))

    def _on_run_golden(self) -> None:
        task_id = self._golden_pick.currentText()
        if task_id == "(none found)" or self._golden.running:
            return
        self._log.append_line(f"running golden {task_id}...")
        self._golden.start(lambda: self._controller.run(task_id))

    def _on_golden(self, result: object) -> None:
        assert isinstance(result, GoldenRunResult)
        for crit in result.criteria:
            self._log.append_line(crit.describe())
        self._log.append_line(f"{result.task.id}: {'PASSED' if result.passed else 'FAILED'}")
        self._log.append_line(f"artifacts: {result.run_dir}")

    def _on_run_soak(self) -> None:
        board = self._soak_board.text().strip()
        if not board or self._soak.running:
            return
        hours = float(self._soak_hours.value())
        workload = self._soak_workload.text().strip() or None
        run_dir = create_run_dir(f"soak-{board}", Path.cwd())
        self._log.append_line(f"soaking {board} for {hours}h (artifacts: {run_dir})...")
        self._soak.start(lambda: self._controller.soak(board, hours, workload, run_dir))

    def _on_soak(self, result: object) -> None:
        assert isinstance(result, SoakResult)
        self._log.append_line(result.render_report())
