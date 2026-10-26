"""Home page: top bar, filter chips, and the grid of equal cards."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from ..library import Library
from . import theme
from .cards import Card, CardGrid


class LibraryPage(QWidget):
    add_link = Signal(str)
    open_clip = Signal(str)
    clip_menu = Signal(str, object)
    open_settings = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.lib: Library | None = None
        self.cards: dict[str, Card] = {}
        self.filter_key = "all"
        self.query = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 0)
        root.setSpacing(16)

        top = QHBoxLayout()
        top.setSpacing(12)
        title = QLabel("คลังสไตล์")
        title.setObjectName("Title")
        top.addWidget(title)
        top.addSpacing(10)
        self.url = QLineEdit()
        self.url.setPlaceholderText("วางลิงก์ TikTok, Shorts, Reels หรือ Facebook")
        self.url.returnPressed.connect(self._submit)
        top.addWidget(self.url, 1)
        self.add_btn = QPushButton("เพิ่ม")
        self.add_btn.setObjectName("Primary")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self._submit)
        top.addWidget(self.add_btn)
        gear = QPushButton("ตั้งค่า")
        gear.setCursor(Qt.CursorShape.PointingHandCursor)
        gear.clicked.connect(self.open_settings)
        top.addWidget(gear)
        root.addLayout(top)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.chip = {}
        for key, name, obj in (("all", "ทั้งหมด", "Chip"), ("effects", "สไตล์เอฟเฟกต์", "Chip"),
                               ("viral", "คลิปไวรัล", "Chip"), ("waiting", "รอวิเคราะห์", "ChipBlue")):
            b = QPushButton(name)
            b.setObjectName(obj)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self._set_filter(k))
            self.group.addButton(b)
            self.chip[key] = (b, name)
            chips.addWidget(b)
        self.chip["all"][0].setChecked(True)
        chips.addStretch(1)
        self.search = QLineEdit()
        self.search.setPlaceholderText("ค้นหาชื่อหรือแท็ก")
        self.search.setFixedWidth(220)
        self.search.textChanged.connect(self._set_query)
        chips.addWidget(self.search)
        root.addLayout(chips)

        self.grid = CardGrid()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        holder = QWidget()
        hl = QVBoxLayout(holder)
        hl.setContentsMargins(0, 4, 0, 28)
        hl.addWidget(self.grid)
        hl.addStretch(1)
        self.scroll.setWidget(holder)
        root.addWidget(self.scroll, 1)

        self.empty = QLabel("ยังไม่มีคลิปในคลัง\nวางลิงก์ด้านบนแล้วกด \"เพิ่ม\" หรือลากไฟล์วิดีโอมาวางตรงนี้ได้เลย")
        self.empty.setObjectName("Soft")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setStyleSheet("font-size: 14px; line-height: 160%;")
        root.addWidget(self.empty, 1)
        self.empty.hide()

    # ---- data
    def set_library(self, lib: Library):
        self.lib = lib
        self.cards.clear()
        self.refresh()

    def _submit(self):
        text = self.url.text().strip()
        if text:
            self.add_link.emit(text)

    def clear_url(self):
        self.url.clear()

    def _set_filter(self, key: str):
        self.filter_key = key
        self.refresh()

    def _set_query(self, text: str):
        self.query = text.strip().lower()
        self.refresh()

    def _matches(self, m: dict, card: dict | None) -> bool:
        k = self.filter_key
        if k in ("effects", "viral") and m.get("kind") != k:
            return False
        if k == "waiting" and m.get("status") not in ("waiting", "downloading", "preparing"):
            return False
        if self.query:
            hay = " ".join([m.get("title") or "", m.get("uploader") or "",
                            (card or {}).get("name_th") or "", " ".join((card or {}).get("tags") or [])]).lower()
            return self.query in hay
        return True

    def refresh(self):
        if not self.lib:
            return
        metas = self.lib.list_meta()
        waiting = sum(1 for m in metas if m.get("status") in ("waiting", "downloading", "preparing"))
        for key, (b, name) in self.chip.items():
            n = {"all": len(metas), "effects": sum(1 for m in metas if m.get("kind") == "effects"),
                 "viral": sum(1 for m in metas if m.get("kind") == "viral"), "waiting": waiting}[key]
            b.setText(f"{name} {n}")
        shown = []
        alive = set()
        for m in metas:
            cid = m["id"]
            alive.add(cid)
            card_data = self.lib.style_card(cid) if m.get("status") == "analyzed" else None
            c = self.cards.get(cid)
            if c is None:
                c = Card(cid)
                c.clicked.connect(self.open_clip)
                c.menu.connect(self.clip_menu)
                self.cards[cid] = c
            c.set_data(m, card_data, self.lib.thumb_path(cid))
            if self._matches(m, card_data):
                shown.append(c)
        for cid in list(self.cards):
            if cid not in alive:
                self.cards.pop(cid).deleteLater()
        self.grid.set_cards(shown)
        has_any = bool(metas)
        self.empty.setVisible(not has_any)
        self.scroll.setVisible(has_any)

    def set_progress(self, clip_id: str, frac: float, text: str):
        c = self.cards.get(clip_id)
        if c:
            c.set_progress(frac, text)
