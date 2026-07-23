"""Skills panel: list local skill packs and preview a pack's SKILL.md."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from deepgent.gui.controllers.operations import SkillsController
from deepgent.gui.widgets.common import LogView, toolbar_button


class SkillsPanel(QWidget):
    def __init__(self, controller: SkillsController | None = None) -> None:
        super().__init__()
        self._controller = controller if controller is not None else SkillsController()

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        actions = QHBoxLayout()
        refresh = toolbar_button("Refresh")
        refresh.clicked.connect(self.refresh)
        actions.addWidget(refresh)
        actions.addStretch(1)
        root.addLayout(actions)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._list = QListWidget()
        self._list.setMaximumWidth(220)
        self._list.currentItemChanged.connect(self._on_select)
        self._preview = LogView()
        splitter.addWidget(self._list)
        splitter.addWidget(self._preview)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        self.refresh()

    def refresh(self) -> None:
        self._list.clear()
        for pack in self._controller.packs():
            item = QListWidgetItem(pack.name)
            item.setData(Qt.ItemDataRole.UserRole, str(pack.path))
            item.setToolTip(pack.description)
            self._list.addItem(item)

    def _on_select(self, item: QListWidgetItem | None) -> None:
        self._preview.clear_log()
        if item is None:
            return
        from pathlib import Path

        path = Path(item.data(Qt.ItemDataRole.UserRole)) / "SKILL.md"
        try:
            self._preview.append_line(path.read_text())
        except OSError as exc:
            self._preview.append_line(f"[cannot read {path}: {exc}]")
