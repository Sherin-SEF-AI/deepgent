"""Telemetry panel: task records table (tokens, cost, loops, outcome)."""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from deepgent.gui.controllers.telemetry import TelemetryController
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
        actions.addWidget(refresh)
        actions.addStretch(1)
        root.addLayout(actions)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        root.addWidget(self._table, 1)

        self.refresh()

    def refresh(self) -> None:
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
