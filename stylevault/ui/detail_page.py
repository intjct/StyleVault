"""Clip detail: video, my notes, Claude's style card, timeline, clip info, structure and Remotion recipe."""
from __future__ import annotations

import os

from PySide6.QtCore import QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QScrollArea,
                               QSlider, QVBoxLayout, QWidget)

from .. import library as L
from .. import stylecard as SC
from ..library import KIND_LABEL, PLATFORM_LABEL, Library, fmt_views
from . import theme
from .timeline import Timeline

VIDEO_W = 288
VIDEO_H = 512


def _fmt_time(sec: float) -> str:
    sec = int(max(0, sec))
    return f"{sec // 60}:{sec % 60:02d}"


class DetailPage(QWidget):
    back = Signal()
    delete_requested = Signal(str)
    retry_requested = Signal(str)
    tag_clicked = Signal(str)
    compare_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("Page")
        self.lib: Library | None = None
        self.clip_id: str | None = None
        self.player = None
        self._dirty = False
        self._save_timer = QTimer(self, singleShot=True, interval=600, timeout=self._save_notes)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 18, 28, 0)
        root.setSpacing(14)
        b = QPushButton("←  กลับไปคลังสไตล์")
        b.setObjectName("Link")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(self.back)
        root.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)

        body = QHBoxLayout()
        body.setSpacing(28)
        body.setContentsMargins(0, 0, 0, 24)
        body.setAlignment(Qt.AlignmentFlag.AlignTop)
        page_scroll = QScrollArea()                    # the whole page scrolls on short windows
        page_scroll.setWidgetResizable(True)
        page_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body_holder = QWidget()
        body_holder.setLayout(body)
        page_scroll.setWidget(body_holder)
        root.addWidget(page_scroll, 1)

        # ---- left column
        left = QVBoxLayout()
        left.setSpacing(10)
        self.video_box = QFrame()
        self.video_box.setFixedSize(VIDEO_W, VIDEO_H)
        self.video_box.setStyleSheet("background:#0E1014; border-radius:10px;")
        vb = QVBoxLayout(self.video_box)
        vb.setContentsMargins(0, 0, 0, 0)
        self._setup_player(vb)
        left.addWidget(self.video_box)
        ctl = QHBoxLayout()
        self.play_btn = QPushButton("เล่น")
        self.play_btn.setFixedWidth(64)
        self.play_btn.clicked.connect(self._toggle)
        ctl.addWidget(self.play_btn)
        self.seek = QSlider(Qt.Orientation.Horizontal)
        self.seek.sliderMoved.connect(lambda v: self.player and self.player.setPosition(v))
        ctl.addWidget(self.seek, 1)
        self.time_lbl = QLabel("0:00")
        self.time_lbl.setObjectName("Soft")
        self.time_lbl.setMinimumWidth(70)
        ctl.addWidget(self.time_lbl)
        left.addLayout(ctl)
        nl = QLabel("โน้ตของแตม")
        nl.setObjectName("H2")
        left.addWidget(nl)
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("จดไว้ว่าคลิปนี้เด่นตรงไหน หรืออยากให้ Claude สังเกตอะไร (บันทึกให้อัตโนมัติ)")
        self.notes.setFixedHeight(96)
        self.notes.textChanged.connect(self._on_notes)
        left.addWidget(self.notes)
        body.addLayout(left)

        # ---- right column (scrolls)
        self.right = QVBoxLayout()
        self.right.setSpacing(16)
        self.right.setAlignment(Qt.AlignmentFlag.AlignTop)
        body.addLayout(self.right, 1)

        self.badges = QLabel()
        self.badges.setObjectName("Soft")
        self.title_lbl = QLabel()
        self.title_lbl.setObjectName("Title")
        self.title_lbl.setWordWrap(True)
        self.right.addWidget(self.title_lbl)
        self.right.addWidget(self.badges)

        self.status_box = QLabel()
        self.status_box.setWordWrap(True)
        self.status_box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.right.addWidget(self.status_box)
        self.copy_btn = QPushButton("คัดลอกคำสั่งให้ Claude")
        self.copy_btn.clicked.connect(self._copy_command)
        self.right.addWidget(self.copy_btn, 0, Qt.AlignmentFlag.AlignLeft)

        self.card_holder = QVBoxLayout()               # Claude's style card (rebuilt on every refresh)
        self.card_holder.setSpacing(12)
        self.right.addLayout(self.card_holder)

        self.timeline_title = QLabel("ไทม์ไลน์")
        self.timeline_title.setObjectName("H2")
        self.right.addWidget(self.timeline_title)
        self.timeline = Timeline()
        self.timeline.seek.connect(self._seek_to)
        self.timeline.play_sfx.connect(self._play_sfx)
        self.right.addWidget(self.timeline)
        self.timeline_legend = QLabel("เส้นน้ำเงิน = จุดตัดภาพ   ·   จุดส้ม = เสียงเอฟเฟกต์ (คลิกเพื่อฟัง)   ·   คลิกที่ว่างเพื่อกระโดดไปตรงนั้น")
        self.timeline_legend.setObjectName("Soft")
        self.timeline_legend.setWordWrap(True)
        self.right.addWidget(self.timeline_legend)

        h = QLabel("ข้อมูลคลิป")
        h.setObjectName("H2")
        self.right.addWidget(h)
        self.info = QFrame()
        self.info.setObjectName("Panel")
        self.info_grid = QGridLayout(self.info)
        self.info_grid.setContentsMargins(16, 12, 16, 12)
        self.info_grid.setHorizontalSpacing(20)
        self.info_grid.setVerticalSpacing(10)
        self.info_grid.setColumnStretch(1, 1)
        self.right.addWidget(self.info)

        self.extra_holder = QVBoxLayout()              # structure, Remotion recipe, limits
        self.extra_holder.setSpacing(12)
        self.right.addLayout(self.extra_holder)
        self.speech_holder = QVBoxLayout()             # spoken words (whisper)
        self.speech_holder.setSpacing(8)
        self.right.addLayout(self.speech_holder)

        btns = QHBoxLayout()
        self.open_url_btn = QPushButton("เปิดลิงก์ต้นฉบับ")
        self.open_url_btn.clicked.connect(self._open_source)
        self.open_dir_btn = QPushButton("เปิดโฟลเดอร์คลิป")
        self.open_dir_btn.clicked.connect(self._open_folder)
        btns.addWidget(self.open_url_btn)
        btns.addWidget(self.open_dir_btn)
        self.cmp_btn = QPushButton("เทียบกับคลิปอื่น")
        self.cmp_btn.clicked.connect(lambda: self.compare_requested.emit(self.clip_id))
        btns.addWidget(self.cmp_btn)
        self.retry_btn = QPushButton("ลองโหลดใหม่")
        self.retry_btn.clicked.connect(lambda: self.retry_requested.emit(self.clip_id))
        btns.addWidget(self.retry_btn)
        btns.addStretch(1)
        self.delete_btn = QPushButton("ลบคลิปนี้ออกจากคลัง")
        self.delete_btn.setStyleSheet("QPushButton { color: #C5221F; } QPushButton:hover { background: #FDECEA; }")
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.clip_id))
        btns.addWidget(self.delete_btn)
        self.right.addLayout(btns)

    # ---- player (Qt Multimedia; fails soft if the system has no video support)
    def _setup_player(self, layout):
        try:
            if os.environ.get("STYLEVAULT_NO_MEDIA"):          # tests / servers without sound or video support
                raise RuntimeError("media off")
            from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer
            from PySide6.QtMultimediaWidgets import QVideoWidget
            self.video = QVideoWidget()
            self.video.setStyleSheet("background:#0E1014;")
            layout.addWidget(self.video)
            self.player = QMediaPlayer(self)
            if QMediaDevices.audioOutputs():          # a PC with no speakers must not crash the page
                self.audio = QAudioOutput(self)
                self.player.setAudioOutput(self.audio)
            self.player.setVideoOutput(self.video)
            self.player.positionChanged.connect(self._on_pos)
            self.player.durationChanged.connect(lambda d: self.seek.setRange(0, d))
            self.player.playbackStateChanged.connect(
                lambda s: self.play_btn.setText("หยุด" if s == QMediaPlayer.PlaybackState.PlayingState else "เล่น"))
            self.player.mediaStatusChanged.connect(self._on_media_status)
        except Exception:
            self.player = None
            self.fallback = QLabel("เครื่องนี้เล่นวิดีโอในโปรแกรมไม่ได้")
            self.fallback.setStyleSheet("color:white; background:transparent;")
            self.fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.fallback)

    def _on_media_status(self, st):
        from PySide6.QtMultimedia import QMediaPlayer
        if st == QMediaPlayer.MediaStatus.InvalidMedia:
            self.play_btn.setText("เล่น")

    def _on_pos(self, pos):
        if not self.seek.isSliderDown():
            self.seek.setValue(pos)
        dur = self.player.duration() if self.player else 0
        self.time_lbl.setText(f"{_fmt_time(pos / 1000)} / {_fmt_time(dur / 1000)}")
        self.timeline.set_position(pos / 1000)

    def _toggle(self):
        if not self.player:
            return
        from PySide6.QtMultimedia import QMediaPlayer
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    # ---- notes
    def _on_notes(self):
        if self.clip_id:
            self._dirty = True
            self._save_timer.start()

    def _save_notes(self):
        if self.lib and self.clip_id and self._dirty:
            try:
                with open(self.lib.notes_path(self.clip_id), "w", encoding="utf-8") as f:
                    f.write(self.notes.toPlainText())
                self._dirty = False
            except OSError:
                pass

    def leave(self):
        """Call before leaving the page: saves notes and stops the video."""
        self._save_timer.stop()
        self._save_notes()
        if self.player:
            self.player.stop()
            self.player.setSource(QUrl())

    # ---- show
    def show_clip(self, lib: Library, clip_id: str):
        self.leave()
        self.lib, self.clip_id = lib, clip_id
        m = lib.meta(clip_id) or {}
        self._dirty = False
        self.notes.blockSignals(True)
        try:
            with open(lib.notes_path(clip_id), encoding="utf-8") as f:
                self.notes.setPlainText(f.read())
        except OSError:
            self.notes.setPlainText("")
        self.notes.blockSignals(False)

        v = lib.video_path(clip_id)
        if not self.player and hasattr(self, "fallback"):      # no video support: show the cover picture instead
            t = lib.thumb_path(clip_id)
            if t:
                from PySide6.QtGui import QPixmap
                self.fallback.setPixmap(QPixmap(t).scaled(VIDEO_W, VIDEO_H, Qt.AspectRatioMode.KeepAspectRatio,
                                                           Qt.TransformationMode.SmoothTransformation))
        if self.player and v:
            self.player.setSource(QUrl.fromLocalFile(v))
            self.play_btn.setEnabled(True)
        else:
            self.play_btn.setEnabled(False)
        self.seek.setValue(0)
        self.timeline.set_position(0)
        self.render()

    def render(self):
        """(Re)draws the right-hand side from the files on disk. Safe to call any time: video and notes are untouched."""
        if not (self.lib and self.clip_id):
            return
        lib, clip_id = self.lib, self.clip_id
        m = lib.meta(clip_id) or {}
        card = lib.style_card(clip_id) if m.get("status") == "analyzed" else None
        self.title_lbl.setText((card or {}).get("name_th") or m.get("title") or "คลิปที่ไม่มีชื่อ")
        bits = [PLATFORM_LABEL.get(m.get("platform"), ""), KIND_LABEL.get(m.get("kind"), "")]
        if m.get("view_count") is not None:
            bits.append(f"วิว {fmt_views(m['view_count'])}")
        if m.get("like_count") is not None:
            bits.append(f"ไลก์ {fmt_views(m['like_count'])}")
        self.badges.setText("   ·   ".join(b for b in bits if b))

        st = m.get("status")
        self.retry_btn.setVisible(st == "error")
        if st == "error":
            self.status_box.setObjectName("Warn")
            det = (m.get("error_detail") or "").strip().splitlines()
            det = det[-1][:220] if det else ""
            self.status_box.setText((m.get("error") or "โหลดคลิปไม่สำเร็จ") + (f"\n\nรายละเอียด (ส่งให้ผมดูได้): {det}" if det else ""))
            self.copy_btn.hide()
        elif st in ("downloading", "preparing"):
            self.status_box.setObjectName("Hint")
            self.status_box.setText("กำลังโหลดคลิปนี้อยู่ รอสักครู่" if st == "downloading"
                                    else "กำลังเตรียมข้อมูลคลิปให้ Claude (จุดตัด ภาพนิ่ง เสียง) รอสักครู่")
            self.copy_btn.hide()
        elif st == "analyzed" and card is None:
            self.status_box.setObjectName("Warn")
            self.status_box.setText("การ์ดสไตล์อ่านไม่ได้ — สั่ง Claude วิเคราะห์ใหม่ (กดปุ่มด้านล่างเพื่อคัดลอกคำสั่ง)")
            self.copy_btn.show()
        elif st == "analyzed":
            self.status_box.setObjectName("Good")
            self.status_box.setText("Claude วิเคราะห์คลิปนี้แล้ว" + (f"  ·  {card['analyzed_at'][:10]}" if card.get("analyzed_at") else ""))
            self.copy_btn.hide()
        else:
            self.status_box.setObjectName("Hint")
            self.status_box.setText("คลิปนี้พร้อมให้ Claude วิเคราะห์แล้ว\nกดปุ่มด้านล่างเพื่อคัดลอกคำสั่ง แล้ววางในแชต Claude (แชตใหม่ก็ได้)")
            self.copy_btn.show()
        self.status_box.style().unpolish(self.status_box)
        self.status_box.style().polish(self.status_box)

        self._fill_card(card)
        self._fill_timeline(m, card)
        self._fill_info(m)
        self._fill_extra(card)
        self._fill_speech(m)
        self.open_url_btn.setVisible(bool(m.get("source_url")))

    # ---- helpers to build panels
    @staticmethod
    def _clear(layout):
        while layout.count():
            it = layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
            elif it.layout():
                DetailPage._clear(it.layout())

    @staticmethod
    def _pill(text: str, blue: bool = False) -> QLabel:
        l = QLabel(text)
        bg, fg = (theme.ACCENT_SOFT.name(), theme.ACCENT.name()) if blue else (theme.SURFACE.name(), theme.TEXT_MID.name())
        l.setStyleSheet(f"background:{bg}; color:{fg}; border-radius:12px; padding:4px 12px; font-weight:500;")
        return l

    def _panel(self, title: str, rows: list[tuple[str, str]], top_widget: QWidget | None = None) -> QWidget | None:
        rows = [(k, v) for k, v in rows if v]
        if not rows and top_widget is None:
            return None
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        h = QLabel(title)
        h.setObjectName("H2")
        lay.addWidget(h)
        frame = QFrame()
        frame.setObjectName("Panel")
        g = QGridLayout(frame)
        g.setContentsMargins(16, 12, 16, 12)
        g.setHorizontalSpacing(20)
        g.setVerticalSpacing(10)
        g.setColumnStretch(1, 1)
        r = 0
        if top_widget is not None:
            g.addWidget(top_widget, r, 0, 1, 2)
            r += 1
        for k, v in rows:
            a = QLabel(k)
            a.setObjectName("Soft")
            a.setAlignment(Qt.AlignmentFlag.AlignTop)
            b = QLabel(v)
            b.setWordWrap(True)
            g.addWidget(a, r, 0, Qt.AlignmentFlag.AlignTop)
            g.addWidget(b, r, 1)
            r += 1
        lay.addWidget(frame)
        return box

    # ---- Claude's style card
    def _fill_card(self, card: dict | None):
        self._clear(self.card_holder)
        if not card:
            return
        head = QFrame()
        head.setObjectName("Panel")
        hl = QVBoxLayout(head)
        hl.setContentsMargins(16, 14, 16, 14)
        hl.setSpacing(10)
        tags = QWidget()
        tl = QHBoxLayout(tags)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(6)
        for i, t in enumerate(card.get("tags") or []):
            b = QPushButton(t)                         # click a tag = show every clip with this tag
            bg, fg = (theme.ACCENT_SOFT.name(), theme.ACCENT.name()) if i == 0 else (theme.SURFACE.name(), theme.TEXT_MID.name())
            b.setStyleSheet(f"QPushButton {{ background:{bg}; color:{fg}; border:none; border-radius:12px; padding:4px 12px; "
                            f"min-height:0; font-weight:500; }} QPushButton:hover {{ color:{theme.ACCENT.name()}; }}")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip("ดูคลิปทั้งหมดที่มีแท็กนี้")
            b.clicked.connect(lambda _=False, t=t: self.tag_clicked.emit(t))
            tl.addWidget(b)
        tl.addStretch(1)
        hl.addWidget(tags)
        if card.get("summary_th"):
            sm = QLabel(card["summary_th"])
            sm.setWordWrap(True)
            hl.addWidget(sm)
        fit = card.get("fit_for_th") or []
        if fit:
            f = QLabel("เหมาะกับ: " + "  ·  ".join(fit))
            f.setObjectName("Mid")
            f.setWordWrap(True)
            hl.addWidget(f)
        if card.get("engky_fit_th"):
            e = QLabel("เหมาะกับคลิปอิงกี้: " + card["engky_fit_th"])
            e.setObjectName("Mid")
            e.setWordWrap(True)
            hl.addWidget(e)
        self.card_holder.addWidget(head)

        vis = card.get("visual") or {}
        sw = None
        pal = [c for c in (vis.get("palette") or []) if QColor(c).isValid()]
        if pal:
            sw = QWidget()
            sl = QHBoxLayout(sw)
            sl.setContentsMargins(0, 0, 0, 0)
            sl.setSpacing(6)
            sl.addWidget(QLabel("สีหลัก"))
            for c in pal[:8]:
                d = QFrame()
                d.setFixedSize(24, 24)
                d.setToolTip(c)
                d.setStyleSheet(f"background:{QColor(c).name()}; border-radius:12px; border:1px solid {theme.LINE.name()};")
                sl.addWidget(d)
            sl.addStretch(1)
        w = self._panel("หน้าตาภาพ", [("ภาพรวม", vis.get("look_th") or ""), ("ตัวหนังสือ", vis.get("text_style_th") or ""),
                                       ("การจัดวาง", vis.get("layout_th") or "")], sw)
        if w:
            self.card_holder.addWidget(w)

        pac = card.get("pacing") or {}
        pace_rows = []
        if pac.get("feel_th"):
            pace_rows.append(("ความเร็ว", pac["feel_th"]))
        if pac.get("avg_shot_sec") is not None:
            pace_rows.append(("ช็อตละ", f"{pac['avg_shot_sec']} วินาที (เฉลี่ย)"))
        if pac.get("transitions_th"):
            pace_rows.append(("ทรานซิชัน", "  ·  ".join(pac["transitions_th"])))
        w = self._panel("จังหวะการตัดต่อ", pace_rows)
        if w:
            self.card_holder.addWidget(w)

        aud = card.get("audio") or {}
        sfx = aud.get("sfx_th") or []
        lines = [f"{SC.mmss(x['t'])}  {x.get('type_th') or 'เสียงเอฟเฟกต์'}" + (f" — {x['role_th']}" if x.get("role_th") else "")
                 for x in sfx[:8]]
        if len(sfx) > 8:
            lines.append(f"…และอีก {len(sfx) - 8} จุด")
        w = self._panel("เสียง", [("เพลง", aud.get("music_th") or ""), ("เสียงพูด", aud.get("voice_th") or ""),
                                  ("เสียงเอฟเฟกต์", "\n".join(lines))])
        if w:
            self.card_holder.addWidget(w)

    # ---- timeline
    def _fill_timeline(self, m: dict, card: dict | None):
        raw = os.path.join(self.lib.clip_dir(m["id"]), "raw")
        cuts = L.read_json(os.path.join(raw, "cuts.json"))
        audio = L.read_json(os.path.join(raw, "audio.json"))
        cut_list = cuts.get("cuts_sec") if isinstance(cuts, dict) and isinstance(cuts.get("cuts_sec"), list) else []
        sfx = []
        if isinstance(audio, dict) and isinstance(audio.get("sfx"), list):
            labels = ((card or {}).get("audio") or {}).get("sfx_th") or []
            for s in audio["sfx"]:
                if not isinstance(s, dict) or not isinstance(s.get("t"), (int, float)):
                    continue
                near = [x for x in labels if abs(x["t"] - s["t"]) <= 0.15]
                label = (near[0].get("type_th") if near else None) or s.get("label_th")
                sfx.append({"t": s["t"], "file": s.get("file") or "", "label": label})
        dur = m.get("duration_sec")
        show = bool(dur) and isinstance(cuts, dict)
        for w in (self.timeline_title, self.timeline, self.timeline_legend):
            w.setVisible(show)
        if show:
            self.timeline.set_data(dur, cut_list, sfx)

    def _seek_to(self, sec: float):
        if self.player:
            self.player.setPosition(int(sec * 1000))
        self.timeline.set_position(sec)

    def _play_sfx(self, rel: str):
        if not (rel and self.lib and self.clip_id) or os.environ.get("STYLEVAULT_NO_MEDIA"):
            return
        path = os.path.join(self.lib.clip_dir(self.clip_id), "raw", rel)
        if not os.path.isfile(path):
            return
        try:
            from PySide6.QtMultimedia import QMediaDevices, QSoundEffect
            if not QMediaDevices.audioOutputs():
                return
            if getattr(self, "_sfx_player", None) is None:
                self._sfx_player = QSoundEffect(self)
            self._sfx_player.setSource(QUrl.fromLocalFile(path))
            self._sfx_player.play()
        except Exception:
            pass

    # ---- structure + Remotion recipe + limits
    def _fill_extra(self, card: dict | None):
        self._clear(self.extra_holder)
        if not card:
            return
        st = card.get("structure") or []
        if st:
            rows = [(f"{x['from']:g}–{x['to']:g} วินาที", x.get("beat_th") or "") for x in st]
            w = self._panel("โครงเรื่อง", rows)
            if w:
                self.extra_holder.addWidget(w)
        rec = card.get("remotion_recipe") or {}
        if rec:
            rows = []
            fps, sf = rec.get("fps"), rec.get("shot_frames")
            if fps:
                rows.append(("ความเร็วภาพ", f"{fps:g} ภาพต่อวินาที"))
            if sf:
                rows.append(("ความยาวต่อช็อต", f"{sf:g} เฟรม" + (f" (ประมาณ {sf / fps:.1f} วินาที)" if fps else "")))
            rows.append(("ข้อความขึ้นแบบ", SC.thai_choice(rec.get("text_anim"), SC.TEXT_ANIM_TH)))
            rows.append(("ทรานซิชัน", SC.thai_choice(rec.get("transition"), SC.TRANSITION_TH)))
            rows.append(("กฎการใส่เสียง", rec.get("sfx_rule_th") or ""))
            rows.append(("หมายเหตุ", rec.get("notes_th") or ""))
            w = self._panel("สูตรตัดต่อ (สำหรับ Remotion)", rows)
            if w:
                self.extra_holder.addWidget(w)
        lim = card.get("limits_th") or []
        if lim:
            l = QLabel("ข้อจำกัดของการวิเคราะห์นี้\n" + "\n".join("• " + x for x in lim))
            l.setObjectName("Hint")
            l.setWordWrap(True)
            self.extra_holder.addWidget(l)

    def _fill_speech(self, m: dict):
        from .. import transcribe
        self._clear(self.speech_holder)
        if not self.lib:
            return
        raw = os.path.join(self.lib.clip_dir(m["id"]), "raw")
        audio = L.read_json(os.path.join(raw, "audio.json"))
        if not (isinstance(audio, dict) and audio.get("has_audio")):
            return
        h = QLabel("คำพูดในคลิป")
        h.setObjectName("H2")
        self.speech_holder.addWidget(h)
        data = L.read_json(os.path.join(raw, "transcript.json"))
        segs = data.get("segments") if isinstance(data, dict) and isinstance(data.get("segments"), list) else None
        if segs is None:
            note = QLabel("กำลังรอถอดคำพูด (ทำเบื้องหลัง)…" if transcribe.ready()
                          else "ยังไม่ได้ถอดคำพูด — ดาวน์โหลดตัวถอดคำพูดได้ในหน้าตั้งค่า (ครั้งเดียว)")
            note.setObjectName("Hint")
            note.setWordWrap(True)
            self.speech_holder.addWidget(note)
            return
        if not segs:
            note = QLabel("ไม่มีเสียงพูดในคลิปนี้")
            note.setObjectName("Soft")
            self.speech_holder.addWidget(note)
            return
        frame = QFrame()
        frame.setObjectName("Panel")
        g = QGridLayout(frame)
        g.setContentsMargins(12, 10, 16, 10)
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(4)
        g.setColumnStretch(1, 1)
        for r, sg in enumerate(segs[:300]):
            if not isinstance(sg, dict) or not isinstance(sg.get("from"), (int, float)):
                continue
            t = QPushButton(_fmt_time(sg["from"]))
            t.setObjectName("Link")
            t.setCursor(Qt.CursorShape.PointingHandCursor)
            t.setToolTip("กระโดดไปช่วงนี้")
            t.clicked.connect(lambda _=False, x=float(sg["from"]): self._seek_to(x))
            txt = QLabel(str(sg.get("text") or ""))
            txt.setWordWrap(True)
            txt.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            g.addWidget(t, r, 0, Qt.AlignmentFlag.AlignTop)
            g.addWidget(txt, r, 1)
        self.speech_holder.addWidget(frame)
        tip = QLabel("ถอดโดยโปรแกรมในเครื่อง อาจสะกดผิดบ้าง — กดเวลาด้านซ้ายเพื่อกระโดดไปช่วงนั้น")
        tip.setObjectName("Soft")
        tip.setWordWrap(True)
        self.speech_holder.addWidget(tip)

    def _fill_info(self, m: dict):
        while self.info_grid.count():
            it = self.info_grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        dur = m.get("duration_sec")
        rows = [
            ("ช่อง / ผู้โพสต์", m.get("uploader")),
            ("วันที่โพสต์", m.get("upload_date")),
            ("ความยาว", f"{dur:.0f} วินาที" if isinstance(dur, (int, float)) else None),
            ("ขนาดภาพ", f"{m['width']} × {m['height']}" if m.get("width") else None),
            ("เพิ่มเข้าคลังเมื่อ", (m.get("added_at") or "")[:16].replace("T", " ") or None),
        ]
        cuts = L.read_json(os.path.join(self.lib.clip_dir(m["id"]), "raw", "cuts.json")) if self.lib else None
        audio = L.read_json(os.path.join(self.lib.clip_dir(m["id"]), "raw", "audio.json")) if self.lib else None
        if isinstance(cuts, dict):
            rows.append(("จุดตัดภาพ", f"{cuts.get('cut_count', 0)} จุด (เฉลี่ยช็อตละ {cuts.get('avg_shot_sec', '—')} วินาที)"))
        if isinstance(audio, dict):
            if not audio.get("has_audio"):
                rows.append(("เสียง", "ไม่มีเสียง"))
            else:
                bpm = audio.get("bpm")
                rows.append(("จังหวะเพลง (ครั้งต่อนาที)", str(bpm) if bpm else "จับจังหวะที่ชัดเจนไม่ได้"))
                rows.append(("เสียงกระแทกที่จับได้", f"{len(audio.get('onsets_sec') or [])} จุด"))
                kinds: dict[str, int] = {}
                for x in audio.get("sfx") or []:
                    if isinstance(x, dict) and x.get("label_th"):
                        kinds[x["label_th"]] = kinds.get(x["label_th"], 0) + 1
                if kinds:
                    rows.append(("ชนิดเสียงที่ได้ยิน", "  ·  ".join(f"{k} {n}" for k, n in sorted(kinds.items(), key=lambda kv: -kv[1]))))
                rows.append(("เสียงเงียบ", "ไม่มีช่วงเงียบเลย (มีเพลงหรือเสียงคลอตลอด)" if not audio.get("silences")
                             else f"{len(audio['silences'])} ช่วง"))
        for i, (k, val) in enumerate(rows):
            a = QLabel(k)
            a.setObjectName("Soft")
            b = QLabel(str(val) if val else "—")
            b.setWordWrap(True)
            self.info_grid.addWidget(a, i, 0)
            self.info_grid.addWidget(b, i, 1)

    def _copy_command(self):
        from ..claude_readme import analyze_command
        if self.lib:
            QGuiApplication.clipboard().setText(analyze_command(self.lib.root))
            self.copy_btn.setText("คัดลอกแล้ว ✓ ไปวางในแชต Claude ได้เลย")
            QTimer.singleShot(2500, lambda: self.copy_btn.setText("คัดลอกคำสั่งให้ Claude"))

    def _open_source(self):
        m = (self.lib.meta(self.clip_id) if self.lib and self.clip_id else None) or {}
        if m.get("source_url"):
            QDesktopServices.openUrl(QUrl(m["source_url"]))

    def _open_folder(self):
        if self.lib and self.clip_id:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.lib.clip_dir(self.clip_id)))
