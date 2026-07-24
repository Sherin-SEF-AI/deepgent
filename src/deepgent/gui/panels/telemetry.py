"""Telemetry panel: task records table (tokens, cost, loops, outcome)."""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from deepgent.gui.controllers.telemetry import TelemetryController
from deepgent.gui.widgets.charts import BarChart
from deepgent.gui.widgets.common import toolbar_button

_COLUMNS = ("id", "class", "board", "outcome", "loops", "tokens", "usd", "wall_s")


class TelemetryPanel(QWidget):
    def __init__(self, controller: TelemetryController | None = None) -> None:
        super().__init__()
        self._controller = controller if controller is not None else TelemetryController()

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        actions = QHBoxLayout()
        refresh = toolbar_button("Refresh")
        refresh.clicked.connect(self.refresh)
        self._summary = QLabel("")
        self._summary.setProperty("role", "dim")
        actions.addWidget(refresh)
        actions.addWidget(self._summary, 1)
        root.addLayout(actions)

        self._chart = BarChart("cost per task (recent, oldest -> newest)")
        root.addWidget(self._chart)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        root.addWidget(self._table, 1)

        self.refresh()

    def refresh(self) -> None:
        summary = self._controller.summary()
        self._summary.setText(
            f"{summary.tasks} tasks  |  {summary.success_rate:.0%} ok  |  "
            f"${summary.total_usd:.2f}  |  budget calibration x{summary.budget_calibration:.2f}"
        )
        self._chart.set_values(self._controller.recent_costs())
        records = self._controller.records()
        self._table.setRowCount(len(records))
        for r, rec in enumerate(records):
            usd = f"{rec.usd:.4f}" if rec.usd is not None else "-"
            values = (
                rec.id[:12],
                rec.task_class,
                rec.board or "-",
                rec.outcome,
                str(rec.loops),
                str(rec.tokens),
                usd,
                f"{rec.wall_s:.1f}",
            )
            for c, value in enumerate(values):
                self._table.setItem(r, c, QTableWidgetItem(str(value)))
