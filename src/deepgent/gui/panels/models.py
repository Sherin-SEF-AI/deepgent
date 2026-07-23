"""Models panel: quantization sweep (#1), accuracy gate (#2), and
power-budget model selection (#6), each run on a target off the UI loop."""

from pathlib import Path

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from deepgent.evals.accuracy import AccuracyResult
from deepgent.evals.model_selector import Constraint, SelectionResult
from deepgent.evals.quant_sweep import QuantSweepResult, select_best
from deepgent.gui.async_bridge import AsyncTask
from deepgent.gui.controllers.operations import ModelsController
from deepgent.gui.widgets.common import LogView, toolbar_button


class ModelsPanel(QWidget):
    """Sweep, accuracy-gate, and select-model launchers with a shared log."""

    def __init__(self, controller: ModelsController | None = None) -> None:
        super().__init__()
        self._controller = controller if controller is not None else ModelsController()
        self._sweep = AsyncTask(self)
        self._sweep.finished.connect(self._on_sweep)
        self._acc = AsyncTask(self)
        self._acc.finished.connect(self._on_accuracy)
        self._select = AsyncTask(self)
        self._select.finished.connect(self._on_select)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Quant sweep row.
        sweep_row = QHBoxLayout()
        sweep_row.setSpacing(4)
        sweep_row.addWidget(QLabel("sweep"))
        self._s_board = self._field("board id", 110)
        self._s_command = self._field("build+bench template ({precision} {batch} {device})")
        self._s_precisions = self._field("fp16,int8", 130)
        self._s_batches = self._field("1,2", 80)
        s_btn = toolbar_button("Run sweep", role="accent")
        s_btn.clicked.connect(self._on_run_sweep)
        for w in (self._s_board, self._s_command, self._s_precisions, self._s_batches):
            sweep_row.addWidget(w, 1 if w is self._s_command else 0)
        sweep_row.addWidget(s_btn)
        root.addLayout(sweep_row)

        # Accuracy gate row.
        acc_row = QHBoxLayout()
        acc_row.setSpacing(4)
        acc_row.addWidget(QLabel("accuracy"))
        self._a_board = self._field("board id", 110)
        self._a_command = self._field("eval cmd (prints METRIC <name> <v>)")
        self._a_metric = self._field("mAP", 80)
        self._a_baseline = QDoubleSpinBox()
        self._a_baseline.setRange(0.0, 1.0)
        self._a_baseline.setDecimals(4)
        self._a_baseline.setSingleStep(0.01)
        self._a_baseline.setToolTip("Baseline (0 = informational only)")
        a_btn = toolbar_button("Run gate", role="accent")
        a_btn.clicked.connect(self._on_run_accuracy)
        acc_row.addWidget(self._a_board)
        acc_row.addWidget(self._a_command, 1)
        acc_row.addWidget(self._a_metric)
        acc_row.addWidget(QLabel("baseline"))
        acc_row.addWidget(self._a_baseline)
        acc_row.addWidget(a_btn)
        root.addLayout(acc_row)

        # Model selection row.
        sel_row = QHBoxLayout()
        sel_row.setSpacing(4)
        sel_row.addWidget(QLabel("select"))
        self._m_board = self._field("board id", 110)
        self._m_manifest = self._field("candidate manifest .json path")
        self._m_power = QDoubleSpinBox()
        self._m_power.setRange(0.0, 1000.0)
        self._m_power.setSuffix(" W max")
        self._m_fps = QDoubleSpinBox()
        self._m_fps.setRange(0.0, 100000.0)
        self._m_fps.setSuffix(" fps min")
        m_btn = toolbar_button("Select", role="accent")
        m_btn.clicked.connect(self._on_run_select)
        sel_row.addWidget(self._m_board)
        sel_row.addWidget(self._m_manifest, 1)
        sel_row.addWidget(self._m_power)
        sel_row.addWidget(self._m_fps)
        sel_row.addWidget(m_btn)
        root.addLayout(sel_row)

        self._log = LogView()
        root.addWidget(self._log, 1)

        for task in (self._sweep, self._acc, self._select):
            task.failed.connect(lambda m: self._log.append_line(f"[error] {m}"))

    @staticmethod
    def _field(placeholder: str, width: int | None = None) -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        if width is not None:
            edit.setFixedWidth(width)
        return edit

    def _on_run_sweep(self) -> None:
        board = self._s_board.text().strip()
        command = self._s_command.text().strip()
        if not (board and command) or self._sweep.running:
            return
        precisions = [p.strip() for p in self._s_precisions.text().split(",") if p.strip()] or [
            "fp16"
        ]
        try:
            batches = [int(b) for b in self._s_batches.text().split(",") if b.strip()] or [1]
        except ValueError:
            self._log.append_line("[error] batches must be integers")
            return
        self._log.append_line(f"sweeping {board}...")
        self._sweep.start(
            lambda: self._controller.quant_sweep(board, command, precisions, batches, ["gpu"])
        )

    def _on_sweep(self, result: object) -> None:
        assert isinstance(result, QuantSweepResult)
        self._log.append_line(result.render_table())
        best = select_best(result.frontier)
        self._log.append_line(f"best: {best.config.label if best else 'none'}")

    def _on_run_accuracy(self) -> None:
        board = self._a_board.text().strip()
        command = self._a_command.text().strip()
        if not (board and command) or self._acc.running:
            return
        metric = self._a_metric.text().strip() or "mAP"
        baseline = float(self._a_baseline.value()) or None
        self._log.append_line(f"accuracy gate on {board} ({metric})...")
        self._acc.start(lambda: self._controller.accuracy_gate(board, command, metric, baseline))

    def _on_accuracy(self, result: object) -> None:
        assert isinstance(result, AccuracyResult)
        self._log.append_line(result.render())

    def _on_run_select(self) -> None:
        board = self._m_board.text().strip()
        manifest = self._m_manifest.text().strip()
        if not (board and manifest) or self._select.running:
            return
        constraint = Constraint(
            max_power_w=float(self._m_power.value()) or None,
            min_fps=float(self._m_fps.value()) or None,
        )
        self._log.append_line(f"selecting on {board}...")
        self._select.start(lambda: self._controller.select_model(board, Path(manifest), constraint))

    def _on_select(self, result: object) -> None:
        assert isinstance(result, SelectionResult)
        self._log.append_line(result.render_table())
