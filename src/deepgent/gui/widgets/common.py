"""Small reusable Blender-style components."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# A log can stream for hours (soak, container builds); cap retained blocks so
# memory stays bounded no matter how much scrolls past.
_MAX_LOG_BLOCKS = 5000


class LogView(QPlainTextEdit):
    """Append-only, read-only, monospace log with bounded memory.

    wrap=True wraps long lines to the widget width (for prose/streamed output);
    the default keeps no-wrap so fixed-width tables and reports stay aligned.
    """

    def __init__(self, parent: QWidget | None = None, *, wrap: bool = False) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setProperty("role", "log")
        self.setMaximumBlockCount(_MAX_LOG_BLOCKS)
        self.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth if wrap else QPlainTextEdit.LineWrapMode.NoWrap
        )

    def append_line(self, text: str) -> None:
        for line in text.rstrip("\n").split("\n"):
            self.appendPlainText(line)
        self.moveCursor(QTextCursor.MoveOperation.End)

    def clear_log(self) -> None:
        self.clear()


class StatTile(QFrame):
    """A compact labelled value tile (metric readout)."""

    def __init__(self, label: str, value: str = "-", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(1)
        self._caption = QLabel(label)
        self._caption.setProperty("role", "dim")
        self._value = QLabel(value)
        self._value.setProperty("role", "h1")
        layout.addWidget(self._caption)
        layout.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class CheckRow(QWidget):
    """One diagnostics check: colored status chip + name + detail."""

    def __init__(self, name: str, ok: bool, detail: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(6)
        chip = QLabel("OK" if ok else "FAIL")
        chip.setProperty("role", "ok" if ok else "fail")
        chip.setFixedWidth(34)
        name_label = QLabel(name)
        name_label.setFixedWidth(130)
        detail_label = QLabel(detail)
        detail_label.setProperty("role", "mono")
        detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(chip)
        layout.addWidget(name_label)
        layout.addWidget(detail_label, 1)


def toolbar_button(text: str, role: str | None = None) -> QPushButton:
    """A compact button, optionally styled 'accent' or 'danger'.

    Accent and danger buttons get a soft glow that animates in on hover.
    """
    button = QPushButton(text)
    if role:
        button.setProperty("role", role)
        if role in ("accent", "danger"):
            from deepgent.gui.widgets.animations import attach_hover_glow

            attach_hover_glow(button)
    return button


def section(title: str) -> tuple[QFrame, QVBoxLayout]:
    """A titled card frame with an inner vertical layout."""
    frame = QFrame()
    frame.setProperty("role", "card")
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(8, 6, 8, 8)
    outer.setSpacing(5)
    heading = QLabel(title)
    heading.setProperty("role", "h1")
    outer.addWidget(heading)
    return frame, outer
