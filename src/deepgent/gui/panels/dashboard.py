"""Dashboard panel: host profile, diagnostics, one-click setup."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from deepgent.gui.controllers.host import HostController
from deepgent.gui.widgets.common import CheckRow, StatTile, section, toolbar_button


class DashboardPanel(QWidget):
    """System overview: detected profile, environment checks, setup."""

    def __init__(self, controller: HostController | None = None) -> None:
        super().__init__()
        self._controller = controller if controller is not None else HostController()

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Action row.
        actions = QHBoxLayout()
        self._refresh_btn = toolbar_button("Refresh")
        self._setup_btn = toolbar_button("Run Setup", role="accent")
        self._refresh_btn.clicked.connect(self.refresh)
        self._setup_btn.clicked.connect(self._on_setup)
        actions.addWidget(self._refresh_btn)
        actions.addWidget(self._setup_btn)
        actions.addStretch(1)
        root.addLayout(actions)

        # Stat tiles.
        self._tiles: dict[str, StatTile] = {}
        tiles_row = QGridLayout()
        tiles_row.setSpacing(6)
        for col, key in enumerate(("class", "arch", "accelerator", "cpu", "ram")):
            tile = StatTile(key)
            self._tiles[key] = tile
            tiles_row.addWidget(tile, 0, col)
        root.addLayout(tiles_row)

        # Checks card in a scroll area.
        self._checks_frame, self._checks_layout = section("Environment checks")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._checks_frame)
        root.addWidget(scroll, 1)

        self.refresh()

    def refresh(self) -> None:
        profile = self._controller.detect()
        self._tiles["class"].set_value(profile.device_class)
        self._tiles["arch"].set_value(profile.arch)
        self._tiles["accelerator"].set_value(profile.accelerator)
        self._tiles["cpu"].set_value(str(profile.cpu_count))
        self._tiles["ram"].set_value(f"{profile.ram_mb} MB" if profile.ram_mb else "unknown")
        # Rebuild the checks list.
        while self._checks_layout.count() > 1:  # keep the heading
            item = self._checks_layout.takeAt(1)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        for check in self._controller.checks(profile):
            self._checks_layout.addWidget(CheckRow(check.name, check.ok, check.detail))
        self._checks_layout.addStretch(1)

    def _on_setup(self) -> None:
        try:
            path, written, registered = self._controller.setup(force=True)
        except Exception as exc:  # surfaced, not swallowed
            self._show_status(f"setup failed: {exc}", ok=False)
            return
        msg = f"config {'written' if written else 'kept'} at {path}"
        if registered:
            msg += "; local target registered"
        self._show_status(msg, ok=True)
        self.refresh()

    def _show_status(self, text: str, ok: bool) -> None:
        from PySide6.QtWidgets import QLabel

        label = QLabel(text)
        label.setProperty("role", "ok" if ok else "fail")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._checks_layout.insertWidget(1, label)
