"""Run Task panel: submit an agent task, stream output, watch budget/cost."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from deepgent.core import TaskOutcome
from deepgent.gui.async_bridge import AsyncTask
from deepgent.gui.controllers.tasks import TaskController
from deepgent.gui.widgets.animations import Spinner, bind_spinner
from deepgent.gui.widgets.common import LogView, toolbar_button


class RunTaskPanel(QWidget):
    """Enter a task, run it live, and see streamed output plus cost/turns."""

    def __init__(self, controller: TaskController | None = None) -> None:
        super().__init__()
        self._controller = controller if controller is not None else TaskController()
        self._task = AsyncTask(self)
        self._task.finished.connect(self._on_finished)
        self._task.failed.connect(self._on_failed)
        self._task.done.connect(self._on_done)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Input row.
        input_row = QHBoxLayout()
        input_row.setSpacing(6)
        self._input = QLineEdit()
        self._input.setPlaceholderText(
            "Describe an AV/CV/embedded task, e.g. 'report the CUDA device via nvidia-smi'"
        )
        self._input.returnPressed.connect(self._on_run)
        self._budget = QDoubleSpinBox()
        self._budget.setRange(0.01, 100.0)
        self._budget.setValue(0.50)
        self._budget.setSingleStep(0.25)
        self._budget.setPrefix("$")
        self._budget.setFixedWidth(80)
        self._budget.setToolTip("Per-task budget cap (USD)")
        self._run_btn = toolbar_button("Run", role="accent")
        self._stop_btn = toolbar_button("Stop", role="danger")
        self._stop_btn.setEnabled(False)
        self._run_btn.clicked.connect(self._on_run)
        self._stop_btn.clicked.connect(self._on_stop)
        self._spinner = Spinner()
        bind_spinner(self._task, self._spinner)
        input_row.addWidget(self._input, 1)
        input_row.addWidget(QLabel("budget"))
        input_row.addWidget(self._budget)
        input_row.addWidget(self._spinner)
        input_row.addWidget(self._run_btn)
        input_row.addWidget(self._stop_btn)
        root.addLayout(input_row)

        # Streamed log.
        self._log = LogView()
        root.addWidget(self._log, 1)

        # Status line.
        self._status = QLabel("idle")
        self._status.setProperty("role", "dim")
        self._status.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self._status)

    def _on_run(self) -> None:
        task = self._input.text().strip()
        if not task or self._task.running:
            return
        budget = float(self._budget.value())
        self._log.clear_log()
        self._log.append_line(f"$ deepgent run  (budget ${budget:.2f})")
        self._log.append_line(f"> {task}")
        self._set_running(True)
        self._status.setText("running...")

        def stream(text: str) -> None:
            self._log.append_line(text)

        self._task.start(lambda: self._controller.run(task, budget, stream))

    def _on_stop(self) -> None:
        self._task.cancel()
        self._log.append_line("[cancelled by user]")
        self._status.setText("cancelled")

    def _on_finished(self, outcome: object) -> None:
        assert isinstance(outcome, TaskOutcome)
        if outcome.result:
            self._log.append_line("")
            self._log.append_line(outcome.result)
        cost = f"${outcome.total_cost_usd:.4f}" if outcome.total_cost_usd is not None else "n/a"
        verdict = "error" if outcome.is_error else "ok"
        self._status.setText(
            f"{verdict}  |  {outcome.num_turns} turns  |  {cost}  |  "
            f"session {outcome.session_id[:8]}"
        )
        self._status.setProperty("role", "fail" if outcome.is_error else "ok")
        self._restyle(self._status)

    def _on_failed(self, message: str) -> None:
        self._log.append_line(f"[error] {message}")
        self._status.setText(f"failed: {message}")
        self._status.setProperty("role", "fail")
        self._restyle(self._status)

    def _on_done(self) -> None:
        self._set_running(False)

    def _set_running(self, running: bool) -> None:
        self._run_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)
        self._input.setEnabled(not running)
        self._budget.setEnabled(not running)

    @staticmethod
    def _restyle(widget: QWidget) -> None:
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)
