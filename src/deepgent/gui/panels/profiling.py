"""Profiling panel: sustained thermal envelope (#3) and glass-to-glass
latency trace (#4), both run on a target board off the UI loop."""

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from deepgent.evals.cuda_check import CudaCheckResult
from deepgent.evals.latency_trace import LatencyTrace
from deepgent.evals.nsight import NsightResult
from deepgent.evals.thermal_envelope import ThermalEnvelopeResult
from deepgent.gui.async_bridge import AsyncTask
from deepgent.gui.controllers.operations import ProfilingController
from deepgent.gui.widgets.common import LogView, toolbar_button


class ProfilingPanel(QWidget):
    """Thermal-envelope and latency-trace launchers with a shared log."""

    def __init__(self, controller: ProfilingController | None = None) -> None:
        super().__init__()
        self._controller = controller if controller is not None else ProfilingController()
        self._thermal = AsyncTask(self)
        self._thermal.finished.connect(self._on_thermal)
        self._latency = AsyncTask(self)
        self._latency.finished.connect(self._on_latency)
        self._nsight = AsyncTask(self)
        self._nsight.finished.connect(self._on_nsight)
        self._cuda = AsyncTask(self)
        self._cuda.finished.connect(self._on_cuda)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Thermal row.
        thermal_row = QHBoxLayout()
        thermal_row.setSpacing(4)
        thermal_row.addWidget(QLabel("thermal"))
        self._t_board = QLineEdit()
        self._t_board.setPlaceholderText("board id")
        self._t_board.setFixedWidth(110)
        self._t_workload = QLineEdit()
        self._t_workload.setPlaceholderText("sustained benchmark command (prints fps)")
        self._t_hold = QDoubleSpinBox()
        self._t_hold.setRange(1.0, 86400.0)
        self._t_hold.setValue(300.0)
        self._t_hold.setSuffix(" s")
        self._t_modes = QLineEdit()
        self._t_modes.setPlaceholderText("modes 0:MAXN,1:30W (optional)")
        self._t_modes.setFixedWidth(170)
        t_btn = toolbar_button("Run thermal", role="accent")
        t_btn.clicked.connect(self._on_run_thermal)
        thermal_row.addWidget(self._t_board)
        thermal_row.addWidget(self._t_workload, 1)
        thermal_row.addWidget(self._t_hold)
        thermal_row.addWidget(self._t_modes)
        thermal_row.addWidget(t_btn)
        root.addLayout(thermal_row)

        # Latency row.
        latency_row = QHBoxLayout()
        latency_row.setSpacing(4)
        latency_row.addWidget(QLabel("latency"))
        self._l_board = QLineEdit()
        self._l_board.setPlaceholderText("board id")
        self._l_board.setFixedWidth(110)
        self._l_command = QLineEdit()
        self._l_command.setPlaceholderText("instrumented pipeline (emits STAGE <name> <ms>)")
        self._l_budget = QDoubleSpinBox()
        self._l_budget.setRange(0.0, 100000.0)
        self._l_budget.setValue(0.0)
        self._l_budget.setSuffix(" ms budget")
        self._l_budget.setToolTip("0 disables the budget gate")
        self._l_budget.setFixedWidth(140)
        l_btn = toolbar_button("Run latency", role="accent")
        l_btn.clicked.connect(self._on_run_latency)
        latency_row.addWidget(self._l_board)
        latency_row.addWidget(self._l_command, 1)
        latency_row.addWidget(self._l_budget)
        latency_row.addWidget(l_btn)
        root.addLayout(latency_row)

        # Nsight row.
        nsight_row = QHBoxLayout()
        nsight_row.setSpacing(4)
        nsight_row.addWidget(QLabel("nsight"))
        self._n_board = QLineEdit()
        self._n_board.setPlaceholderText("board id")
        self._n_board.setFixedWidth(110)
        self._n_command = QLineEdit()
        self._n_command.setPlaceholderText("nsys wrapper emitting NSIGHT summary lines")
        n_btn = toolbar_button("Run nsight", role="accent")
        n_btn.clicked.connect(self._on_run_nsight)
        nsight_row.addWidget(self._n_board)
        nsight_row.addWidget(self._n_command, 1)
        nsight_row.addWidget(n_btn)
        root.addLayout(nsight_row)

        # CUDA safety-check row.
        cuda_row = QHBoxLayout()
        cuda_row.setSpacing(4)
        cuda_row.addWidget(QLabel("cuda"))
        self._c_board = QLineEdit()
        self._c_board.setPlaceholderText("board id")
        self._c_board.setFixedWidth(110)
        self._c_build = QLineEdit()
        self._c_build.setPlaceholderText("build command (optional)")
        self._c_run = QLineEdit()
        self._c_run.setPlaceholderText("run command for compute-sanitizer")
        c_btn = toolbar_button("cuda-check", role="accent")
        c_btn.clicked.connect(self._on_run_cuda)
        cuda_row.addWidget(self._c_board)
        cuda_row.addWidget(self._c_build, 1)
        cuda_row.addWidget(self._c_run, 1)
        cuda_row.addWidget(c_btn)
        root.addLayout(cuda_row)

        self._log = LogView()
        root.addWidget(self._log, 1)

        for task in (self._thermal, self._latency, self._nsight, self._cuda):
            task.failed.connect(lambda m: self._log.append_line(f"[error] {m}"))

    def _on_run_thermal(self) -> None:
        board = self._t_board.text().strip()
        workload = self._t_workload.text().strip()
        if not (board and workload) or self._thermal.running:
            return
        modes = self._t_modes.text().strip() or None
        hold = float(self._t_hold.value())
        self._log.append_line(f"thermal envelope on {board} (hold {hold:.0f}s)...")
        self._thermal.start(
            lambda: self._controller.thermal(board, workload, hold, modes, 95.0, 30.0)
        )

    def _on_thermal(self, result: object) -> None:
        assert isinstance(result, ThermalEnvelopeResult)
        self._log.append_line(result.render_table())

    def _on_run_latency(self) -> None:
        board = self._l_board.text().strip()
        command = self._l_command.text().strip()
        if not (board and command) or self._latency.running:
            return
        budget = float(self._l_budget.value()) or None
        self._log.append_line(f"latency trace on {board}...")
        self._latency.start(lambda: self._controller.latency(board, command, budget, 30.0))

    def _on_latency(self, result: object) -> None:
        assert isinstance(result, LatencyTrace)
        self._log.append_line(result.render_report())

    def _on_run_nsight(self) -> None:
        board = self._n_board.text().strip()
        command = self._n_command.text().strip()
        if not (board and command) or self._nsight.running:
            return
        self._log.append_line(f"nsight profile on {board}...")
        self._nsight.start(lambda: self._controller.nsight(board, command))

    def _on_nsight(self, result: object) -> None:
        assert isinstance(result, NsightResult)
        self._log.append_line(result.render())

    def _on_run_cuda(self) -> None:
        board = self._c_board.text().strip()
        run = self._c_run.text().strip()
        if not (board and run) or self._cuda.running:
            return
        build = self._c_build.text().strip() or None
        self._log.append_line(f"cuda-check on {board}...")
        self._cuda.start(
            lambda: self._controller.cuda_check(board, run, build, ["memcheck", "racecheck"])
        )

    def _on_cuda(self, result: object) -> None:
        assert isinstance(result, CudaCheckResult)
        self._log.append_line(result.render())
