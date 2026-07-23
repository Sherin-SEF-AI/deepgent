"""Matrix panel: fleet compat+perf matrix (#7) and matrix reasoning (#14)."""

from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from deepgent.evals.fleet import FleetResult
from deepgent.gui.async_bridge import AsyncTask
from deepgent.gui.controllers.operations import MatrixController
from deepgent.gui.widgets.animations import Spinner, bind_spinner
from deepgent.gui.widgets.common import LogView, toolbar_button


class MatrixPanel(QWidget):
    """Run a fleet sweep and reason over compatibility claims."""

    def __init__(self, controller: MatrixController | None = None) -> None:
        super().__init__()
        self._controller = controller if controller is not None else MatrixController()
        self._fleet = AsyncTask(self)
        self._fleet.finished.connect(self._on_fleet)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        fleet_note = QLabel("Fleet: run one benchmark across boards; build a compat+perf matrix.")
        fleet_note.setProperty("role", "dim")
        root.addWidget(fleet_note)

        fleet_row = QHBoxLayout()
        fleet_row.setSpacing(4)
        self._f_command = QLineEdit()
        self._f_command.setPlaceholderText("benchmark command")
        self._f_boards = QLineEdit()
        self._f_boards.setPlaceholderText("board ids, comma-separated")
        f_btn = toolbar_button("Run fleet", role="accent")
        f_btn.clicked.connect(self._on_run_fleet)
        fleet_row.addWidget(self._f_command, 1)
        fleet_row.addWidget(self._f_boards, 1)
        fleet_row.addWidget(f_btn)
        root.addLayout(fleet_row)

        analyze_note = QLabel("Analyze: contradictions and the next cell worth verifying.")
        analyze_note.setProperty("role", "dim")
        root.addWidget(analyze_note)

        analyze_row = QHBoxLayout()
        analyze_row.setSpacing(4)
        self._a_claims = QLineEdit()
        self._a_claims.setPlaceholderText("claims .json path")
        self._a_component = QLineEdit()
        self._a_component.setPlaceholderText("component")
        self._a_universe = QLineEdit()
        self._a_universe.setPlaceholderText("universe .json path (optional)")
        a_btn = toolbar_button("Analyze", role="accent")
        a_btn.clicked.connect(self._on_analyze)
        analyze_row.addWidget(self._a_claims, 1)
        analyze_row.addWidget(self._a_component)
        analyze_row.addWidget(self._a_universe, 1)
        analyze_row.addWidget(a_btn)
        root.addLayout(analyze_row)

        self._log = LogView()
        root.addWidget(self._log, 1)

        self._spinner = Spinner()
        bind_spinner(self._fleet, self._spinner)
        root.addWidget(self._spinner)

        self._fleet.failed.connect(lambda m: self._log.append_line(f"[error] {m}"))

    def _on_run_fleet(self) -> None:
        command = self._f_command.text().strip()
        boards = [b.strip() for b in self._f_boards.text().split(",") if b.strip()]
        if not (command and boards) or self._fleet.running:
            return
        self._log.append_line(f"fleet across {', '.join(boards)}...")
        self._fleet.start(lambda: self._controller.fleet(command, boards))

    def _on_fleet(self, result: object) -> None:
        assert isinstance(result, FleetResult)
        self._log.append_line(result.render_table())

    def _on_analyze(self) -> None:
        claims = self._a_claims.text().strip()
        component = self._a_component.text().strip()
        if not (claims and component):
            return
        universe = self._a_universe.text().strip()
        try:
            result = self._controller.analyze(
                Path(claims), component, Path(universe) if universe else None
            )
        except Exception as exc:  # surfaced, not swallowed
            self._log.append_line(f"[error] {exc}")
            return
        self._log.append_line(result.render())
