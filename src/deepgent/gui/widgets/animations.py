"""Reusable animation primitives for the GUI.

A ref-counted indeterminate Spinner, a fade-in helper for panel transitions,
and a hover-glow attachment for accent buttons. All are safe offscreen (used
in the test suite): timers only run while a spinner is active, and animations
are parented to the widgets they drive so they are never garbage-collected
mid-run.
"""

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QPushButton,
    QWidget,
)

from deepgent.gui.theme import ACCENT

_TICK_MS = 40
_STEP_DEG = 12


class Spinner(QWidget):
    """A small indeterminate progress arc, ref-counted across bindings.

    start()/stop() nest: multiple concurrent tasks can share one spinner and
    it keeps spinning until the last stops. It paints nothing while idle, so it
    reserves layout space without flicker.
    """

    def __init__(self, size: int = 16, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._count = 0
        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._advance)

    @property
    def spinning(self) -> bool:
        return self._count > 0

    def start(self) -> None:
        self._count += 1
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def stop(self) -> None:
        self._count = max(0, self._count - 1)
        if self._count == 0:
            self._timer.stop()
            self.update()

    def _advance(self) -> None:
        self._angle = (self._angle + _STEP_DEG) % 360
        self.update()

    def paintEvent(self, event: object) -> None:
        if self._count == 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(ACCENT))
        pen.setWidthF(2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        m = 2.0
        rect = QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)
        # A 270-degree arc sweeping around; Qt angles are in 1/16 degree.
        painter.drawArc(rect, -self._angle * 16, 270 * 16)


def bind_spinner(task: QObject, spinner: Spinner) -> None:
    """Spin while an AsyncTask runs: started -> start, done -> stop."""
    task.started.connect(spinner.start)  # type: ignore[attr-defined]
    task.done.connect(spinner.stop)  # type: ignore[attr-defined]


def fade_in(widget: QWidget, duration: int = 170) -> None:
    """Fade a widget from transparent to opaque (panel-switch transition)."""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    # Drop the effect when done so it does not tax later repaints. PySide6
    # accepts None to clear it; the stub is stricter than the runtime.
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))  # type: ignore[arg-type]
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)


class _HoverGlow(QObject):
    """Event filter that animates a drop-shadow glow on hover."""

    def __init__(self, button: QPushButton) -> None:
        super().__init__(button)
        self._effect = QGraphicsDropShadowEffect(button)
        self._effect.setColor(QColor(ACCENT))
        self._effect.setOffset(0, 0)
        self._effect.setBlurRadius(0)
        button.setGraphicsEffect(self._effect)
        self._anim = QPropertyAnimation(self._effect, b"blurRadius", self)
        self._anim.setDuration(140)
        button.installEventFilter(self)

    def _to(self, radius: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._effect.blurRadius())
        self._anim.setEndValue(radius)
        self._anim.start()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Enter:
            self._to(16.0)
        elif event.type() == QEvent.Type.Leave:
            self._to(0.0)
        return False


def attach_hover_glow(button: QPushButton) -> None:
    """Give an accent/danger button a soft glow that animates in on hover."""
    _HoverGlow(button)
