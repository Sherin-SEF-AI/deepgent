"""Knowledge panel: corpus-first triage against the knowledge API."""

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from deepgent.gui.async_bridge import AsyncTask
from deepgent.gui.controllers.operations import KnowledgeController
from deepgent.gui.widgets.common import LogView, toolbar_button
from deepgent.knowledge.products import TriageResult


class KnowledgePanel(QWidget):
    def __init__(self, controller: KnowledgeController | None = None) -> None:
        super().__init__()
        self._controller = controller if controller is not None else KnowledgeController()
        self._task = AsyncTask(self)
        self._task.finished.connect(self._on_result)
        self._premortem = AsyncTask(self)
        self._premortem.finished.connect(self._on_premortem)
        self._reflect = AsyncTask(self)
        self._reflect.finished.connect(self._on_reflect)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        note = QLabel("Corpus-first triage: the failure corpus is checked before any LLM call.")
        note.setProperty("role", "dim")
        root.addWidget(note)

        row = QHBoxLayout()
        row.setSpacing(4)
        self._symptom = QLineEdit()
        self._symptom.setPlaceholderText("failure symptom, e.g. 'nvcc unsupported gpu arch'")
        self._symptom.returnPressed.connect(self._on_triage)
        self._hw = QLineEdit()
        self._hw.setPlaceholderText("hw filter (optional)")
        self._hw.setFixedWidth(160)
        btn = toolbar_button("Triage", role="accent")
        btn.clicked.connect(self._on_triage)
        row.addWidget(self._symptom, 1)
        row.addWidget(self._hw)
        row.addWidget(btn)
        root.addLayout(row)

        hw_row = QHBoxLayout()
        hw_row.setSpacing(4)
        self._hw_config = QLineEdit()
        self._hw_config.setPlaceholderText("hardware config .json path (peripherals, rails)")
        hw_btn = toolbar_button("Check hardware", role="accent")
        hw_btn.clicked.connect(self._on_hw_check)
        hw_row.addWidget(self._hw_config, 1)
        hw_row.addWidget(hw_btn)
        root.addLayout(hw_row)

        pm_row = QHBoxLayout()
        pm_row.setSpacing(4)
        self._pm_symptom = QLineEdit()
        self._pm_symptom.setPlaceholderText("pre-mortem: task/symptom to predict failures for")
        self._pm_hw = QLineEdit()
        self._pm_hw.setPlaceholderText("hw filter (optional)")
        self._pm_hw.setFixedWidth(160)
        pm_btn = toolbar_button("Pre-mortem", role="accent")
        pm_btn.clicked.connect(self._on_premortem_run)
        pm_row.addWidget(self._pm_symptom, 1)
        pm_row.addWidget(self._pm_hw)
        pm_row.addWidget(pm_btn)
        root.addLayout(pm_row)

        reflect_row = QHBoxLayout()
        reflect_row.setSpacing(4)
        self._rf_tool = QLineEdit()
        self._rf_tool.setPlaceholderText("failed tool (e.g. Bash)")
        self._rf_tool.setFixedWidth(150)
        self._rf_error = QLineEdit()
        self._rf_error.setPlaceholderText("reflexion: paste the failure error text")
        rf_btn = toolbar_button("Reflect", role="accent")
        rf_btn.clicked.connect(self._on_reflect_run)
        reflect_row.addWidget(self._rf_tool)
        reflect_row.addWidget(self._rf_error, 1)
        reflect_row.addWidget(rf_btn)
        root.addLayout(reflect_row)

        self._log = LogView()
        root.addWidget(self._log, 1)

        self._task.failed.connect(lambda m: self._log.append_line(f"[error] {m}"))
        self._premortem.failed.connect(lambda m: self._log.append_line(f"[error] {m}"))
        self._reflect.failed.connect(lambda m: self._log.append_line(f"[error] {m}"))

    def _on_reflect_run(self) -> None:
        tool = self._rf_tool.text().strip()
        error = self._rf_error.text().strip()
        if not (tool and error) or self._reflect.running:
            return
        self._log.append_line(f"reflexion on {tool} failure...")
        self._reflect.start(lambda: self._controller.reflect(tool, error))

    def _on_reflect(self, result: object) -> None:
        from deepgent.core.reflexion import Reflexion

        assert isinstance(result, Reflexion)
        self._log.append_line(result.render())

    def _on_premortem_run(self) -> None:
        symptom = self._pm_symptom.text().strip()
        if not symptom or self._premortem.running:
            return
        hw = self._pm_hw.text().strip() or None
        self._log.append_line(f"pre-mortem: {symptom}")
        self._premortem.start(lambda: self._controller.premortem(symptom, hw))

    def _on_premortem(self, result: object) -> None:
        from deepgent.knowledge.premortem import PreMortem

        assert isinstance(result, PreMortem)
        self._log.append_line(result.render())

    def _on_hw_check(self) -> None:
        from pathlib import Path

        config = self._hw_config.text().strip()
        if not config:
            return
        try:
            report = self._controller.hardware_check(Path(config))
        except Exception as exc:  # surfaced, not swallowed
            self._log.append_line(f"[error] {exc}")
            return
        self._log.append_line(report.render())

    def _on_triage(self) -> None:
        symptom = self._symptom.text().strip()
        if not symptom or self._task.running:
            return
        hw = self._hw.text().strip() or None
        self._log.append_line(f"triaging: {symptom}")
        self._task.start(lambda: self._controller.triage(symptom, hw))

    def _on_result(self, result: object) -> None:
        assert isinstance(result, TriageResult)
        self._log.append_line(result.render())
