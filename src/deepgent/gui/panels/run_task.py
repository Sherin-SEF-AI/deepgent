"""Run Task cockpit: run an agent task, watch it edit and run commands live,
then inspect the diff, review, and test results it produced."""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from deepgent.core import CommandRun, TaskEvent, TaskOutcome
from deepgent.gui.async_bridge import AsyncTask
from deepgent.gui.controllers.tasks import TaskController
from deepgent.gui.history import TaskHistory
from deepgent.gui.widgets.animations import Spinner, bind_spinner
from deepgent.gui.widgets.common import LogView, toolbar_button
from deepgent.gui.widgets.response import ResponseView

if TYPE_CHECKING:
    from deepgent.gui.session import TaskSession


class RunTaskPanel(QWidget):
    """Run a task, stream output, and inspect the code / review / tests."""

    def __init__(self, controller: TaskController | None = None) -> None:
        super().__init__()
        self._controller = controller if controller is not None else TaskController()
        self._history = TaskHistory()
        self._task = AsyncTask(self)
        self._task.finished.connect(self._on_finished)
        self._task.failed.connect(self._on_failed)
        self._task.done.connect(self._on_done)
        self._diff = AsyncTask(self)
        self._diff.finished.connect(self._on_diff)
        self._review = AsyncTask(self)
        self._review.finished.connect(self._on_review_done)
        self._test = AsyncTask(self)
        self._test.finished.connect(self._on_test_done)

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

        # Cockpit tabs.
        self._tabs = QTabWidget()
        self._log = ResponseView()  # wrapped, markdown-rendered response
        self._tabs.addTab(self._log, "Output")
        self._activity = LogView(wrap=True)
        self._tabs.addTab(self._activity, "Activity")
        self._tabs.addTab(self._build_diff_tab(), "Diff")
        self._tabs.addTab(self._build_review_tab(), "Review")
        self._tabs.addTab(self._build_test_tab(), "Tests")
        root.addWidget(self._tabs, 1)

        # Status line.
        self._status = QLabel("idle")
        self._status.setProperty("role", "dim")
        self._status.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self._status)

        for task in (self._diff, self._review, self._test):
            task.failed.connect(lambda m: self._status.setText(f"cockpit error: {m}"))

    # --- tab builders -------------------------------------------------------

    def _build_diff_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 6, 0, 0)
        row = QHBoxLayout()
        btn = toolbar_button("Refresh diff")
        btn.clicked.connect(self._refresh_diff)
        row.addWidget(btn)
        row.addStretch(1)
        layout.addLayout(row)
        self._diff_view = LogView()  # keep diff alignment: no wrap
        layout.addWidget(self._diff_view, 1)
        return widget

    def _build_review_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 6, 0, 0)
        row = QHBoxLayout()
        self._review_cmd = QLineEdit(self._controller.default_review_command())
        btn = toolbar_button("Run review", role="accent")
        btn.clicked.connect(self._run_review)
        row.addWidget(QLabel("review"))
        row.addWidget(self._review_cmd, 1)
        row.addWidget(btn)
        layout.addLayout(row)
        self._review_view = LogView()
        layout.addWidget(self._review_view, 1)
        return widget

    def _build_test_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 6, 0, 0)
        row = QHBoxLayout()
        self._test_cmd = QLineEdit(self._controller.default_test_command())
        btn = toolbar_button("Run tests", role="accent")
        btn.clicked.connect(self._run_test)
        row.addWidget(QLabel("tests"))
        row.addWidget(self._test_cmd, 1)
        row.addWidget(btn)
        layout.addLayout(row)
        self._test_view = LogView()
        layout.addWidget(self._test_view, 1)
        return widget

    # --- task run -----------------------------------------------------------

    def set_task(self, task: str) -> None:
        """Fill the task input (used by the menu's Open Recent / New Task)."""
        self._input.setText(task)
        self._input.setFocus()

    def start_run(self) -> None:
        """Public entry so the menu's Run action can start the current task."""
        self._on_run()

    def stop(self) -> None:
        if self._task.running:
            self._on_stop()

    def run_review(self) -> None:
        self._tabs.setCurrentIndex(3)
        self._run_review()

    def run_tests(self) -> None:
        self._tabs.setCurrentIndex(4)
        self._run_test()

    def refresh_diff(self) -> None:
        self._tabs.setCurrentIndex(2)
        self._refresh_diff()

    def clear_output(self) -> None:
        self._log.clear_response()
        self._activity.clear_log()

    # --- session save / open ------------------------------------------------

    def to_session(self) -> "TaskSession":
        """Capture the current run as a portable session."""
        from deepgent.gui.session import TaskSession

        return TaskSession(
            task=self._input.text(),
            response=self._log.markdown(),
            activity=self._activity.toPlainText(),
            diff=self._diff_view.toPlainText(),
            review=self._review_view.toPlainText(),
            tests=self._test_view.toPlainText(),
        )

    def load_session(self, session: "TaskSession") -> None:
        """Restore a saved session into the cockpit."""
        self._input.setText(session.task)
        self._log.render_markdown(session.response)
        self._activity.setPlainText(session.activity)
        self._diff_view.setPlainText(session.diff)
        self._review_view.setPlainText(session.review)
        self._test_view.setPlainText(session.tests)
        self._status.setText(f"opened session ({session.session_id[:8] or 'saved'})")

    def _on_run(self) -> None:
        task = self._input.text().strip()
        if not task or self._task.running:
            return
        self._history.add(task)
        budget = float(self._budget.value())
        self._log.clear_response()
        self._activity.clear_log()
        self._log.append_stream(f"Running (budget ${budget:.2f}): {task}\n")
        self._set_running(True)
        self._status.setText("running...")

        def stream(text: str) -> None:
            self._log.append_stream(text)

        self._task.start(
            lambda: self._controller.run(task, budget, stream, on_event=self._on_event)
        )

    def _on_event(self, event: TaskEvent) -> None:
        if event.kind == "tool_use":
            self._activity.append_line(f"-> {event.name}: {event.detail}")
        else:
            mark = "x" if event.is_error else "ok"
            first = event.detail.splitlines()[0] if event.detail else ""
            self._activity.append_line(f"   [{mark}] {event.name}: {first}")

    def _on_stop(self) -> None:
        self._task.cancel()
        self._log.append_stream("\n[cancelled by user]")
        self._status.setText("cancelled")

    def _on_finished(self, outcome: object) -> None:
        assert isinstance(outcome, TaskOutcome)
        if outcome.result:
            # Replace the streamed plain text with the polished markdown render.
            self._log.render_markdown(outcome.result)
        cost = f"${outcome.total_cost_usd:.4f}" if outcome.total_cost_usd is not None else "n/a"
        verdict = "error" if outcome.is_error else "ok"
        self._status.setText(
            f"{verdict}  |  {outcome.num_turns} turns  |  {cost}  |  "
            f"session {outcome.session_id[:8]}"
        )
        self._status.setProperty("role", "fail" if outcome.is_error else "ok")
        self._restyle(self._status)
        # Show what changed as soon as the task lands.
        self._refresh_diff()

    def _on_failed(self, message: str) -> None:
        self._log.append_stream(f"\n[error] {message}")
        self._status.setText(f"failed: {message}")
        self._status.setProperty("role", "fail")
        self._restyle(self._status)

    def _on_done(self) -> None:
        self._set_running(False)

    # --- cockpit actions ----------------------------------------------------

    def _refresh_diff(self) -> None:
        if self._diff.running:
            return
        self._diff_view.clear_log()
        self._diff_view.append_line("computing diff...")
        self._diff.start(self._controller.diff)

    def _on_diff(self, diff_text: object) -> None:
        self._diff_view.clear_log()
        self._diff_view.append_line(str(diff_text))

    def _run_review(self) -> None:
        command = self._review_cmd.text().strip()
        if not command or self._review.running:
            return
        self._review_view.clear_log()
        self._review_view.append_line(f"$ {command}")
        self._review.start(lambda: self._controller.review(command))

    def _on_review_done(self, run: object) -> None:
        self._render_command(self._review_view, run)

    def _run_test(self) -> None:
        command = self._test_cmd.text().strip()
        if not command or self._test.running:
            return
        self._test_view.clear_log()
        self._test_view.append_line(f"$ {command}")
        self._test.start(lambda: self._controller.test(command))

    def _on_test_done(self, run: object) -> None:
        self._render_command(self._test_view, run)

    @staticmethod
    def _render_command(view: LogView, run: object) -> None:
        assert isinstance(run, CommandRun)
        view.append_line(run.output or "(no output)")
        view.append_line("")
        view.append_line(f"[{'PASS' if run.ok else 'FAIL'}]  exit {run.exit_status}")

    # --- helpers ------------------------------------------------------------

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
