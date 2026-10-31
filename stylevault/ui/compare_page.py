"""Two clips side by side: the numbers the program measured + what Claude wrote, row by row."""
from __future__ import annotations

import html
import os
import re

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from .. import library as L
from .. import stylecard as SC
from ..library import KIND_LABEL, PLATFORM_LABEL, Library, fmt_views
from . import theme

THUMB_W, THUMB_H = 150, 200


def clip_facts(lib: Library, cid: str) -> list[tuple[str, str]]:
    """Rows of (label, value as rich text). Missing values become a dash."""
    m = lib.meta(cid) or {}
    card = lib.style_card(cid) if m.get("status") == "analyzed" else None
    card = card or {}
    raw = os.path.join(lib.clip_dir(cid), "raw")
    cuts = L.read_json(os.path.join(raw, "cuts.json"))
    audio = L.read_json(os.path.join(raw, "audio.json"))
    speech = L.read_json(os.path.join(raw, "transcript.json"))
    cuts = cuts if isinstance(cuts, dict) else {}
    audio = audio if isinstance(audio, dict) else {}
    e = html.escape

    def join(xs):
        return "  ·  ".join(e(str(x)) for x in xs if x) if isinstance(xs, list) else ""

    dur = m.get("duration_sec")
    kinds: dict[str, int] = {}
    for x in audio.get("sfx") or []:
        if isinstance(x, dict) and x.get("label_th"):
            kinds[x["label_th"]] = kinds.get(x["label_th"], 0) + 1
    pal = ((card.get("visual") or {}).get("palette") or []) if isinstance(card.get("visual"), dict) else []
    swatches = "&nbsp;&nbsp;".join(
        f'<span style="background-color:{e(c)};">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>&nbsp;<span style="color:#8A8F98;">{e(c)}</span>'
        for c in pal if isinstance(c, str) and re.fullmatch(r"#[0-9A-Fa-f]{6}", c))
    pacing = card.get("pacing") if isinstance(card.get("pacing"), dict) else {}
    st = card.get("structure") if isinstance(card.get("structure"), list) else []
    if isinstance(speech, dict) and isinstance(speech.get("segments"), list):
        full = speech.get("text") or " ".join(str(x.get("text") or "") for x in speech["segments"] if isinstance(x, dict))
        full = full.strip()
        sp = e(full[:140] + ("…" if len(full) > 140 else "")) or "ไม่มีเสียงพูด"
    else:
        sp = ""
    bpm = audio.get("bpm")
    return [
        ("ชื่อสไตล์", e(card.get("name_th") or ("รอวิเคราะห์" if m.get("status") == "waiting" else m.get("title") or ""))),
        ("ที่มา", e(" · ".join(x for x in (PLATFORM_LABEL.get(m.get("platform"), ""), KIND_LABEL.get(m.get("kind"), "")) if x))),
        ("ยอดวิว", fmt_views(m["view_count"]) if m.get("view_count") is not None else ""),
        ("ความยาว", f"{dur:.0f} วินาที" if isinstance(dur, (int, float)) else ""),
        ("จุดตัดภาพ", f"{cuts.get('cut_count')} จุด" if cuts.get("cut_count") is not None else ""),
        ("ช็อตเฉลี่ย", f"{cuts.get('avg_shot_sec')} วินาที" if cuts.get("avg_shot_sec") is not None else ""),
        ("ความเร็วที่รู้สึก", e(pacing.get("feel_th") or "")),
        ("ทรานซิชัน", join(pacing.get("transitions_th"))),
        ("จังหวะเพลง (ครั้งต่อนาที)", str(bpm) if bpm else ("ไม่มีเสียง" if audio and not audio.get("has_audio") else "")),
        ("ชนิดเสียงที่ได้ยิน", "  ·  ".join(f"{e(k)} {n}" for k, n in sorted(kinds.items(), key=lambda kv: -kv[1]))),
        ("แท็ก", join(card.get("tags"))),
        ("เหมาะกับ", join(card.get("fit_for_th"))),
        ("หน้าตาภาพ", e((card.get("visual") or {}).get("look_th") or "") if isinstance(card.get("visual"), dict) else ""),
        ("สีหลัก", swatches),
        ("ข้อความขึ้นแบบ", e(SC.thai_choice((card.get("remotion_recipe") or {}).get("text_anim"), SC.TEXT_ANIM_TH))
         if isinstance(card.get("remotion_recipe"), dict) else ""),
        ("โครงเรื่อง", "<br>".join(f"{x['from']:g}–{x['to']:g} วิ: {e(x.get('beat_th') or '')}" for x in st
                                   if isinstance(x, dict) and isinstance(x.get("from"), (int, float))
                                   and isinstance(x.get("to"), (int, float)))),
        ("คำพูดในคลิป", sp),
    ]


class ComparePage(QWidget):
    back = Signal()
    open_clip = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        body.setObjectName("Page")
        sc.setWidget(body)
        outer.addWidget(sc)
        root = QVBoxLayout(body)
        root.setContentsMargins(28, 18, 28, 24)
        root.setSpacing(14)
        b = QPushButton("←  กลับไปคลังสไตล์")
        b.setObjectName("Link")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(self.back)
        root.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        t = QLabel("เทียบ 2 คลิป")
        t.setObjectName("Title")
        root.addWidget(t)
        self.frame = QFrame()
        self.frame.setObjectName("Panel")
        self.grid = QGridLayout(self.frame)
        self.grid.setContentsMargins(18, 16, 18, 16)
        self.grid.setHorizontalSpacing(24)
        self.grid.setVerticalSpacing(12)
        self.grid.setColumnStretch(1, 1)
        self.grid.setColumnStretch(2, 1)
        root.addWidget(self.frame)
        root.addStretch(1)
        self.ids: tuple[str, str] | None = None

    def show_pair(self, lib: Library, a: str, b: str):
        self.ids = (a, b)
        while self.grid.count():
            it = self.grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for col, cid in ((1, a), (2, b)):
            head = QWidget()
            hl = QVBoxLayout(head)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(8)
            pic = QLabel()
            pic.setFixedSize(THUMB_W, THUMB_H)
            pic.setStyleSheet(f"background:{theme.SURFACE.name()}; border-radius:8px;")
            pic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tp = lib.thumb_path(cid)
            pm = QPixmap(tp) if tp else QPixmap()
            if not pm.isNull():
                pm = pm.scaled(THUMB_W, THUMB_H, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
                pic.setPixmap(pm.copy((pm.width() - THUMB_W) // 2, (pm.height() - THUMB_H) // 2, THUMB_W, THUMB_H))
            else:
                pic.setText("ยังไม่มีภาพปก")
            hl.addWidget(pic)
            num = L.num_label(lib.meta(cid))
            if num:
                nl = QLabel(num)
                nl.setStyleSheet(f"color:{theme.ACCENT.name()}; font-size:16px; font-weight:600;")
                hl.addWidget(nl)
            ob = QPushButton("เปิดคลิปนี้")
            ob.setCursor(Qt.CursorShape.PointingHandCursor)
            ob.clicked.connect(lambda _=False, c=cid: self.open_clip.emit(c))
            hl.addWidget(ob, 0, Qt.AlignmentFlag.AlignLeft)
            self.grid.addWidget(head, 0, col, Qt.AlignmentFlag.AlignTop)
        fa, fb = clip_facts(lib, a), clip_facts(lib, b)
        r = 1
        for (label, va), (_l, vb) in zip(fa, fb):
            if not va and not vb:
                continue
            k = QLabel(label)
            k.setObjectName("Soft")
            self.grid.addWidget(k, r, 0, Qt.AlignmentFlag.AlignTop)
            for col, v in ((1, va), (2, vb)):
                lab = QLabel(v or "—")
                lab.setTextFormat(Qt.TextFormat.RichText)
                lab.setWordWrap(True)
                lab.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
                if label == "ชื่อสไตล์":
                    lab.setStyleSheet("font-size:15px; font-weight:500;")
                self.grid.addWidget(lab, r, col)
            r += 1
            line = QFrame()
            line.setObjectName("Sep")
            self.grid.addWidget(line, r, 0, 1, 3)
            r += 1
