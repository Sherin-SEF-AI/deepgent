"""Boards/targets panel: list, add SSH targets, remove, and test."""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from deepgent.gui.async_bridge import AsyncTask
from deepgent.gui.controllers.boards import BoardsController
from deepgent.gui.widgets.common import toolbar_button

_COLUMNS = ("id", "transport", "where", "type", "caps", "leased by")


class BoardsPanel(QWidget):
    def __init__(self, controller: BoardsController | None = None) -> None:
        super().__init__()
        self._controller = controller if controller is not None else BoardsController()
        self._probe = AsyncTask(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        actions = QHBoxLayout()
        refresh = toolbar_button("Refresh")
        test = toolbar_button("Test selected")
        remove = toolbar_button("Remove selected", role="danger")
        refresh.clicked.connect(self.refresh)
        test.clicked.connect(self._on_test)
        remove.clicked.connect(self._on_remove)
        actions.addWidget(refresh)
        actions.addWidget(test)
        actions.addWidget(remove)
        actions.addStretch(1)
        root.addLayout(actions)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        root.addWidget(self._table, 1)

        # Add-SSH-target row.
        add_row = QHBoxLayout()
        add_row.setSpacing(4)
        self._f_id = self._field("id")
        self._f_host = self._field("host")
        self._f_user = self._field("user")
        self._f_key = self._field("key path")
        self._f_type = self._field("type")
        add_btn = toolbar_button("Add SSH target", role="accent")
        add_btn.clicked.connect(self._on_add)
        for field in (self._f_id, self._f_host, self._f_user, self._f_key, self._f_type):
            add_row.addWidget(field)
        add_row.addWidget(add_btn)
        root.addLayout(add_row)

        self._status = QLabel("")
        self._status.setProperty("role", "dim")
        root.addWidget(self._status)

        self._probe.finished.connect(lambda r: self._status.setText(f"probe: {r}"))
        self._probe.failed.connect(lambda m: self._status.setText(f"probe failed: {m}"))

        self.refresh()

    @staticmethod
    def _field(placeholder: str) -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        return edit

    def refresh(self) -> None:
        rows = self._controller.rows()
        self._table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = (row.id, row.transport, row.where, row.type, row.caps, row.leased_by or "-")
            for c, value in enumerate(values):
                self._table.setItem(r, c, QTableWidgetItem(str(value)))

    def _selected_id(self) -> str | None:
        items = self._table.selectedItems()
        if not items:
            return None
        cell = self._table.item(items[0].row(), 0)
        return cell.text() if cell is not None else None

    def _on_add(self) -> None:
        try:
            self._controller.add_ssh(
                self._f_id.text().strip(),
                self._f_host.text().strip(),
                self._f_user.text().strip(),
                self._f_key.text().strip(),
                self._f_type.text().strip() or "jetson-agx-orin",
                None,
                [],
            )
        except Exception as exc:
            self._status.setText(f"add failed: {exc}")
            return
        for field in (self._f_id, self._f_host, self._f_user, self._f_key, self._f_type):
            field.clear()
        self._status.setText("target added")
        self.refresh()

    def _on_remove(self) -> None:
        board_id = self._selected_id()
        if board_id is None:
            return
        try:
            self._controller.remove(board_id)
        except Exception as exc:
            self._status.setText(f"remove failed: {exc}")
            return
        self._status.setText(f"removed {board_id}")
        self.refresh()

    def _on_test(self) -> None:
        board_id = self._selected_id()
        if board_id is None or self._probe.running:
            return
        self._status.setText(f"testing {board_id}...")
        self._probe.start(lambda: self._controller.test(board_id))
