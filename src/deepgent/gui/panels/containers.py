"""Containers panel: build the jp6 toolchain image with optional smoke."""

from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from deepgent.gui.async_bridge import AsyncTask
from deepgent.gui.controllers.operations import ContainersController
from deepgent.gui.widgets.animations import Spinner, bind_spinner
from deepgent.gui.widgets.common import LogView, toolbar_button


class ContainersPanel(QWidget):
    def __init__(self, controller: ContainersController | None = None) -> None:
        super().__init__()
        self._controller = controller if controller is not None else ContainersController()
        self._task = AsyncTask(self)
        self._task.finished.connect(self._on_built)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        info = QLabel(f"target image: {self._safe_tag()}")
        info.setProperty("role", "mono")
        root.addWidget(info)

        actions = QHBoxLayout()
        self._smoke = QCheckBox("CUDA smoke check")
        self._smoke.setChecked(True)
        self._build_btn = toolbar_button("Build jp6", role="accent")
        self._build_btn.clicked.connect(self._on_build)
        actions.addWidget(self._build_btn)
        actions.addWidget(self._smoke)
        actions.addStretch(1)
        root.addLayout(actions)

        self._log = LogView()
        root.addWidget(self._log, 1)

        self._spinner = Spinner()
        bind_spinner(self._task, self._spinner)
        root.addWidget(self._spinner)

        self._task.failed.connect(lambda m: self._log.append_line(f"[error] {m}"))
        self._task.done.connect(lambda: self._build_btn.setEnabled(True))

    def _safe_tag(self) -> str:
        try:
            return self._controller.image_tag()
        except Exception as exc:
            return f"(unresolved: {exc})"

    def _on_build(self) -> None:
        if self._task.running:
            return
        self._build_btn.setEnabled(False)
        self._log.clear_log()
        self._log.append_line(f"building {self._safe_tag()} (smoke={self._smoke.isChecked()})...")
        self._log.append_line("this runs in a background thread; the UI stays responsive.")
        smoke = self._smoke.isChecked()
        self._task.start(lambda: self._controller.build(smoke))

    def _on_built(self, tag: object) -> None:
        self._log.append_line(f"built {tag}")
