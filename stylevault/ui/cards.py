"""The clip card and the grid that keeps every card the same size (no masonry)."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap, QTextLayout, QTextOption
from PySide6.QtWidgets import QWidget

from ..library import PLATFORM_LABEL, KIND_LABEL, fmt_views
from . import theme

CARD_MIN_W = 200
GAP = 16
INFO_H = 92
RADIUS = 10


def lines_clamped(text: str, font, width: int, max_lines: int = 2) -> list[str]:
    """Wrap text to `width` and keep at most `max_lines` lines (last one ends with …). Works for Thai."""
    if not text:
        return []
    lay = QTextLayout(text, font)
    opt = QTextOption()
    opt.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
    lay.setTextOption(opt)
    lay.beginLayout()
    spans = []
    while True:
        line = lay.createLine()
        if not line.isValid():
            break
        line.setLineWidth(width)
        spans.append((line.textStart(), line.textLength()))
    lay.endLayout()
    out = [text[s:s + n].strip() for s, n in spans][:max_lines]
    if len(spans) > max_lines:
        fm = QFontMetrics(font)
        out[-1] = fm.elidedText(text[spans[max_lines - 1][0]:].strip(), Qt.TextElideMode.ElideRight, width)
    return out


class Card(QWidget):
    clicked = Signal(str)
    menu = Signal(str, object)

    def __init__(self, clip_id: str):
        super().__init__()
        self.clip_id = clip_id
        self.meta: dict = {}
        self.card: dict | None = None
        self.pix: QPixmap | None = None
        self.progress: float | None = None
        self.status_text = ""
        self._hover = False
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_data(self, meta: dict, card: dict | None, thumb: str | None):
        self.meta, self.card = meta, card
        self.pix = QPixmap(thumb) if thumb else None
        if meta.get("status") not in ("downloading", "preparing"):
            self.progress = None
        err = meta.get("error")
        self.setToolTip(err if meta.get("status") == "error" and err else "")
        self.update()

    def set_progress(self, frac: float, text: str):
        self.progress, self.status_text = frac, text
        self.update()

    def image_h(self) -> int:
        return round(self.width() * 4 / 3)

    @staticmethod
    def height_for(width: int) -> int:
        return round(width * 4 / 3) + INFO_H

    # ---- painting
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
                         | QPainter.RenderHint.SmoothPixmapTransform)
        w, ih = self.width(), self.image_h()
        outer = QRectF(0.5, 0.5, w - 1, self.height() - 1)
        path = QPainterPath()
        path.addRoundedRect(outer, RADIUS, RADIUS)
        p.fillPath(path, theme.BG)
        p.save()
        p.setClipPath(path)
        img = QRectF(0, 0, w, ih)
        if self.pix and not self.pix.isNull():
            scaled = self.pix.scaled(int(w), int(ih), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                     Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap(0, 0, scaled, (scaled.width() - w) // 2, (scaled.height() - ih) // 2, int(w), int(ih))
        else:
            p.fillRect(img, theme.SURFACE)
            p.setPen(theme.TEXT_SOFT)
            p.setFont(theme.font(12))
            p.drawText(img, Qt.AlignmentFlag.AlignCenter, "ยังไม่มีภาพปก")
        status = self.meta.get("status")
        busy = status in ("downloading", "preparing")
        if busy:
            p.fillRect(QRectF(0, ih - 4, w, 4), theme.LINE)
            p.fillRect(QRectF(0, ih - 4, w * (self.progress or 0.03), 4), theme.ACCENT)
        p.restore()
        # badges
        self._badge_platform(p)
        self._badge_views(p, ih)
        # info
        pad = 10
        p.setPen(theme.CARD_LINE if not self._hover else QColor("#C5CBD4"))
        p.drawLine(QPointF(0, ih), QPointF(w, ih))
        title, color = self._title()
        p.setFont(theme.font(13, theme.MEDIUM))
        p.setPen(color)
        for i, ln in enumerate(lines_clamped(title, theme.font(13, theme.MEDIUM), w - 2 * pad)):
            p.drawText(QRectF(pad, ih + 8 + i * 19, w - 2 * pad, 19), Qt.AlignmentFlag.AlignVCenter, ln)
        self._tags(p, pad, ih + 8 + 2 * 19 + 8, w)
        p.setPen(QPen(QColor("#C5CBD4") if self._hover else theme.CARD_LINE, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(outer, RADIUS, RADIUS)

    def _title(self):
        s = self.meta.get("status")
        if s in ("downloading", "preparing"):
            return (self.status_text or ("กำลังโหลด…" if s == "downloading" else "กำลังเตรียมข้อมูล…")), theme.TEXT_MID
        if s == "error":
            return (self.meta.get("error") or "โหลดไม่สำเร็จ"), theme.RED
        if s == "analyzed" and self.card and self.card.get("name_th"):
            return str(self.card["name_th"]), theme.TEXT
        if s == "analyzed":
            return "การ์ดสไตล์อ่านไม่ได้ — สั่ง Claude วิเคราะห์ใหม่", theme.RED
        return "รอวิเคราะห์", theme.ACCENT

    def _pill(self, p, x, y, text, bg, fg, size=11, weight=theme.MEDIUM, h=22) -> float:
        f = theme.font(size, weight)
        fm = QFontMetrics(f)
        tw = fm.horizontalAdvance(text)
        r = QRectF(x, y, tw + 18, h)
        path = QPainterPath()
        path.addRoundedRect(r, h / 2, h / 2)
        p.fillPath(path, bg)
        p.setFont(f)
        p.setPen(fg)
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)
        return r.width()

    def _badge_platform(self, p):
        label = PLATFORM_LABEL.get(self.meta.get("platform"), "")
        if label:
            self._pill(p, 8, 8, label, QColor(255, 255, 255, 235), theme.TEXT)

    def _badge_views(self, p, ih):
        v = fmt_views(self.meta.get("view_count"))
        if not v:
            return
        f = theme.font(11, theme.MEDIUM)
        tw = QFontMetrics(f).horizontalAdvance(v)
        r = QRectF(8, ih - 8 - 22 - (4 if self.meta.get("status") in ("downloading", "preparing") else 0), tw + 36, 22)
        path = QPainterPath()
        path.addRoundedRect(r, 11, 11)
        p.fillPath(path, QColor(0, 0, 0, 150))
        # little eye
        cx, cy = r.x() + 13, r.center().y()
        eye = QPainterPath()
        eye.moveTo(cx - 6, cy)
        eye.quadTo(cx, cy - 6, cx + 6, cy)
        eye.quadTo(cx, cy + 6, cx - 6, cy)
        p.setPen(QPen(QColor("white"), 1.3))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(eye)
        p.setBrush(QColor("white"))
        p.drawEllipse(QPointF(cx, cy), 1.8, 1.8)
        p.setFont(f)
        p.setPen(QColor("white"))
        p.drawText(QRectF(r.x() + 24, r.y(), tw + 10, r.height()), Qt.AlignmentFlag.AlignVCenter, v)

    def _tags(self, p, x, y, w):
        s = self.meta.get("status")
        tags = []
        if s == "analyzed" and self.card and isinstance(self.card.get("tags"), list):
            tags = [str(t) for t in self.card["tags"][:2]]
        elif s != "error":
            tags = [KIND_LABEL.get(self.meta.get("kind"), "")]
        first = True
        for t in tags:
            if not t:
                continue
            bg, fg = (theme.ACCENT_SOFT, theme.ACCENT) if (first and s == "analyzed") else (theme.SURFACE, theme.TEXT_MID)
            first = False
            if x + QFontMetrics(theme.font(11, theme.MEDIUM)).horizontalAdvance(t) + 18 > w - 10:
                break
            x += self._pill(p, x, y, t, bg, fg, size=11, weight=theme.NORMAL) + 6

    # ---- mouse
    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit(self.clip_id)

    def contextMenuEvent(self, e):
        self.menu.emit(self.clip_id, e.globalPos())


class CardGrid(QWidget):
    """CSS-grid style: columns = as many 200px+ cards as fit, every card the same width AND height."""

    def __init__(self):
        super().__init__()
        self.cards: list[Card] = []

    def set_cards(self, cards: list[Card]):
        for c in self.cards:
            c.setParent(None)
        self.cards = cards
        for c in cards:
            c.setParent(self)
            c.show()
        self.relayout()

    def relayout(self):
        W = self.width()
        cols = max(1, (W + GAP) // (CARD_MIN_W + GAP))
        cw = (W - GAP * (cols - 1)) // cols
        ch = Card.height_for(cw)
        for i, c in enumerate(self.cards):
            r, k = divmod(i, cols)
            c.setGeometry(k * (cw + GAP), r * (ch + GAP), cw, ch)
        rows = -(-len(self.cards) // cols)
        self.setMinimumHeight(rows * (ch + GAP) if rows else 0)

    def resizeEvent(self, e):
        self.relayout()
