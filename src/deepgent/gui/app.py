"""GUI application bootstrap: QApplication on a qasync event loop.

Running Qt on the asyncio loop (via qasync) is what lets the whole UI drive
deepgent's async core cooperatively, with no worker threads for I/O-bound
work and no UI freezes during long runs. Entry point for `deepgent gui` and
the `deepgent-gui` console script.
"""

import asyncio
import sys

import structlog

_logger = structlog.get_logger(__name__)


def launch() -> int:
    """Start the GUI event loop. Returns a process exit code."""
    # Imported lazily so importing this module never hard-requires Qt.
    import qasync
    from PySide6.QtWidgets import QApplication

    from deepgent.gui.main_window import MainWindow
    from deepgent.gui.theme import QSS

    app = QApplication.instance() or QApplication(sys.argv)
    assert isinstance(app, QApplication)
    app.setApplicationName("deepgent")
    app.setStyleSheet(QSS)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    _logger.info("gui_launched")
    with loop:
        return int(loop.run_forever() or 0)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(launch())
