"""GUI tests: Qt-free controllers plus offscreen construction of every panel
and the main window.

The whole module is skipped when PySide6 is not installed (the ``gui`` extra),
so the core test suite still runs on an install without Qt. Qt is driven with
the ``offscreen`` platform so no display is required.
"""

import asyncio
import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

# The offscreen platform must be selected before the first QApplication.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QWidget

from deepgent.gui.controllers.boards import BoardsController
from deepgent.gui.controllers.host import HostController
from deepgent.gui.controllers.operations import (
    ContainersController,
    EvalsController,
    SkillsController,
)
from deepgent.gui.controllers.telemetry import TelemetryController
from deepgent.telemetry import TelemetryStore

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """One QApplication for the module (Qt allows only a single instance)."""
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    return app


# --- Qt-free controllers (no QApplication needed) ---------------------------


def test_evals_controller_golden_ids(tmp_path: Path) -> None:
    (tmp_path / "golden").mkdir()
    (tmp_path / "golden" / "gt-0002.yaml").write_text("id: gt-0002\n")
    (tmp_path / "golden" / "gt-0001.yaml").write_text("id: gt-0001\n")
    ids = EvalsController().golden_ids(project_root=tmp_path)
    assert ids == ["gt-0001", "gt-0002"]


def test_evals_controller_golden_ids_no_dir(tmp_path: Path) -> None:
    assert EvalsController().golden_ids(project_root=tmp_path) == []


def test_containers_controller_image_tag() -> None:
    tag = ContainersController().image_tag()
    assert isinstance(tag, str) and tag


def test_host_controller_detect_and_checks() -> None:
    controller = HostController()
    profile = controller.detect()
    assert profile.arch
    checks = controller.checks(profile)
    assert checks and all(isinstance(c.ok, bool) for c in checks)


def test_boards_controller_rows_is_list() -> None:
    assert isinstance(BoardsController().rows(), list)


def test_skills_controller_packs_is_list() -> None:
    assert isinstance(SkillsController().packs(), list)


def test_telemetry_controller_records(tmp_path: Path) -> None:
    store = TelemetryStore(tmp_path / "telemetry.db")
    try:
        controller = TelemetryController(store=store)
        assert controller.records() == []
    finally:
        store.close()


# --- Offscreen widget construction ------------------------------------------


def test_common_widgets_construct(qapp: QApplication) -> None:
    from deepgent.gui.widgets.common import (
        CheckRow,
        LogView,
        StatTile,
        section,
        toolbar_button,
    )

    log = LogView()
    log.append_line("line one\nline two")
    log.clear_log()
    tile = StatTile("cpu", "8")
    tile.set_value("16")
    assert isinstance(CheckRow("docker", True, "ok"), QWidget)
    assert toolbar_button("Run", role="accent").text() == "Run"
    _frame, layout = section("Checks")
    assert layout.count() == 1


def test_theme_qss_is_nonempty() -> None:
    from deepgent.gui.theme import QSS

    assert isinstance(QSS, str) and "QWidget" in QSS


def test_every_panel_constructs(qapp: QApplication, tmp_path: Path) -> None:
    """Each panel builds offscreen with its default controller."""
    from deepgent.gui.panels.boards import BoardsPanel
    from deepgent.gui.panels.containers import ContainersPanel
    from deepgent.gui.panels.dashboard import DashboardPanel
    from deepgent.gui.panels.differential import DifferentialPanel
    from deepgent.gui.panels.evals import EvalsPanel
    from deepgent.gui.panels.knowledge import KnowledgePanel
    from deepgent.gui.panels.models import ModelsPanel
    from deepgent.gui.panels.profiling import ProfilingPanel
    from deepgent.gui.panels.run_task import RunTaskPanel
    from deepgent.gui.panels.skills import SkillsPanel
    from deepgent.gui.panels.telemetry import TelemetryPanel

    # Telemetry writes to a store; give it a temp one, not the home db.
    store = TelemetryStore(tmp_path / "telemetry.db")
    try:
        panels: list[QWidget] = [
            DashboardPanel(),
            RunTaskPanel(),
            BoardsPanel(),
            EvalsPanel(),
            DifferentialPanel(),
            ProfilingPanel(),
            ModelsPanel(),
            ContainersPanel(),
            KnowledgePanel(),
            SkillsPanel(),
            TelemetryPanel(TelemetryController(store=store)),
        ]
        for panel in panels:
            assert isinstance(panel, QWidget)
            panel.deleteLater()
    finally:
        store.close()


def test_main_window_activates_every_surface(qapp: QApplication) -> None:
    from deepgent.gui.main_window import MainWindow

    window = MainWindow()
    # Lazily build and switch to every surface.
    for index in range(len(window._built)):
        window._activate(index)
        assert window._built[index] is not None
    window.deleteLater()


# --- Async bridge -----------------------------------------------------------


def test_async_task_emits_finished(qapp: QApplication) -> None:
    from deepgent.gui.async_bridge import AsyncTask

    async def scenario() -> object:
        task = AsyncTask()
        results: list[object] = []
        dones: list[bool] = []
        task.finished.connect(results.append)
        task.done.connect(lambda: dones.append(True))

        async def work() -> str:
            await asyncio.sleep(0)
            return "value"

        task.start(work)
        while task.running:
            await asyncio.sleep(0)
        await asyncio.sleep(0)  # let queued signals flush
        return results, dones

    results, dones = asyncio.run(scenario())
    assert results == ["value"]
    assert dones == [True]


def test_async_task_reports_failure(qapp: QApplication) -> None:
    from deepgent.gui.async_bridge import AsyncTask

    async def scenario() -> list[str]:
        task = AsyncTask()
        errors: list[str] = []
        task.failed.connect(errors.append)

        async def work() -> None:
            raise ValueError("boom")

        task.start(work)
        while task.running:
            await asyncio.sleep(0)
        await asyncio.sleep(0)
        return errors

    errors = asyncio.run(scenario())
    assert errors == ["ValueError: boom"]


def test_async_task_rejects_double_start(qapp: QApplication) -> None:
    from deepgent.gui.async_bridge import AsyncTask

    async def scenario() -> None:
        task = AsyncTask()

        async def work() -> None:
            await asyncio.sleep(0.01)

        task.start(work)
        with pytest.raises(RuntimeError):
            task.start(work)
        while task.running:
            await asyncio.sleep(0)

    asyncio.run(scenario())
