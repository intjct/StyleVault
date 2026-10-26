"""One bar for the whole clip: blue lines = cuts, orange dots = sound effects, click to jump or listen."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QToolTip, QWidget

from . import theme

PAD = 12
BAR_Y = 42


class Timeline(QWidget):
    seek = Signal(float)           # seconds
    play_sfx = Signal(str)         # relative file path inside raw/

    def __init__(self):
        super().__init__()
        self.duration = 0.0
        self.cuts: list[float] = []
        self.sfx: list[dict] = []          # {"t", "file", "label"}
        self.pos = 0.0
        self.setMinimumHeight(78)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_data(self, duration: float, cuts: list[float], sfx: list[dict]):
        self.duration = max(0.0, float(duration or 0))
        self.cuts = [c for c in cuts if isinstance(c, (int, float))]
        self.sfx = [s for s in sfx if isinstance(s.get("t"), (int, float))]
        self.update()

    def set_position(self, sec: float):
        self.pos = sec
        self.update()

    def _x(self, t: float) -> float:
        w = self.width() - 2 * PAD
        return PAD + (w * t / self.duration if self.duration else 0)

    def _t(self, x: float) -> float:
        w = max(1, self.width() - 2 * PAD)
        return max(0.0, min(self.duration, (x - PAD) / w * self.duration))

    def _dot_at(self, pt) -> dict | None:
        best, dist = None, 99.0
        for s in self.sfx:
            dx = abs(self._x(s["t"]) - pt.x())
            if dx <= 8 and abs(pt.y() - BAR_Y) <= 12 and dx < dist:
                best, dist = s, dx
        return best

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        w = self.width()
        p.fillRect(self.rect(), theme.BG)
        if self.duration <= 0:
            return
        # base line
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.LINE)
        p.drawRoundedRect(QRectF(PAD, BAR_Y - 2, w - 2 * PAD, 4), 2, 2)
        # time labels
        step = next((s for s in (1, 2, 5, 10, 15, 30, 60, 120) if (w - 2 * PAD) * s / self.duration >= 56), 120)
        p.setFont(theme.font(11))
        p.setPen(theme.TEXT_SOFT)
        t = 0
        while t <= self.duration + 0.001:
            x = self._x(t)
            p.drawText(QRectF(x - 24, BAR_Y + 18, 48, 16), Qt.AlignmentFlag.AlignCenter, f"{int(t // 60)}:{int(t % 60):02d}")
            t += step
        # cuts (blue lines)
        p.setPen(QPen(theme.ACCENT, 1.6))
        for c in self.cuts:
            x = self._x(c)
            p.drawLine(QPointF(x, BAR_Y - 18), QPointF(x, BAR_Y + 14))
        # sound effects (orange dots)
        p.setPen(QPen(QColor("white"), 1.5))
        p.setBrush(theme.SFX)
        for s in self.sfx:
            p.drawEllipse(QPointF(self._x(s["t"]), BAR_Y), 5.5, 5.5)
        # playhead
        x = self._x(min(self.pos, self.duration))
        p.setPen(QPen(theme.TEXT, 1.6))
        p.drawLine(QPointF(x, BAR_Y - 24), QPointF(x, BAR_Y + 14))
        p.setBrush(theme.TEXT)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPolygon(QPolygonF([QPointF(x - 5, BAR_Y - 28), QPointF(x + 5, BAR_Y - 28), QPointF(x, BAR_Y - 21)]))

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or self.duration <= 0:
            return
        dot = self._dot_at(e.position())
        if dot:
            self.play_sfx.emit(dot.get("file") or "")
            self.seek.emit(float(dot["t"]))
        else:
            self.seek.emit(self._t(e.position().x()))

    def mouseMoveEvent(self, e):
        dot = self._dot_at(e.position())
        if dot:
            label = dot.get("label") or "เสียงเอฟเฟกต์"
            QToolTip.showText(e.globalPosition().toPoint(), f"{label} ที่ {dot['t']:.2f} วินาที (คลิกเพื่อฟัง)", self)
        else:
            QToolTip.hideText()
