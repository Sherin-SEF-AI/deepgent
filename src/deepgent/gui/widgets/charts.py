"""Lightweight painted charts for the GUI (no external plotting deps)."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from deepgent.gui.theme import ACCENT, BG_EDITOR, TEXT_DIM


class BarChart(QWidget):
    """A compact vertical-bar chart for a numeric series (e.g. cost per task)."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._values: list[float] = []
        self._title = title
        self.setMinimumHeight(90)

    def set_values(self, values: list[float]) -> None:
        self._values = list(values)
        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QColor(BG_EDITOR))
        pad = 8
        top = pad + (14 if self._title else 0)
        if self._title:
            painter.setPen(QColor(TEXT_DIM))
            painter.drawText(pad, pad + 10, self._title)
        if not self._values:
            painter.setPen(QColor(TEXT_DIM))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "no data yet")
            return
        peak = max(self._values) or 1.0
        n = len(self._values)
        area_w = rect.width() - 2 * pad
        area_h = rect.height() - top - pad
        gap = 2.0
        bar_w = max(1.0, (area_w - gap * (n - 1)) / n)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(ACCENT))
        for i, value in enumerate(self._values):
            h = area_h * (value / peak)
            x = pad + i * (bar_w + gap)
            y = top + (area_h - h)
            painter.drawRect(QRectF(x, y, bar_w, h))
