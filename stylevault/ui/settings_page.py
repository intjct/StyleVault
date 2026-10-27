"""Small settings page: library folder, clip-downloader update, browser login, version."""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from .. import VERSION, tools, transcribe
from ..settings import Settings
from . import theme

COPYRIGHT_TH = "คลิปในคลังใช้เพื่อศึกษาเท่านั้น ห้ามนำไปโพสต์ซ้ำ"


class _Bg(QObject):
    done = Signal(bool, str)
    speech_progress = Signal(float, str)
    speech_done = Signal(bool, str)


class SettingsPage(QWidget):
    back = Signal()
    library_changed = Signal(str)
    speech_ready = Signal()

    def __init__(self, settings: Settings):
        super().__init__()
        self.setObjectName("Page")
        self.s = settings
        self._bg = _Bg()
        self._bg.done.connect(self._update_done)
        self._bg.speech_progress.connect(self._speech_progress)
        self._bg.speech_done.connect(self._speech_done)
        self._speech_stop = False
        self._speech_busy = False

        outer = QVBoxLayout(self)                      # the page scrolls, so nothing gets squeezed on short windows
        outer.setContentsMargins(0, 0, 0, 0)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        body.setObjectName("Page")
        sc.setWidget(body)
        outer.addWidget(sc)
        root = QVBoxLayout(body)
        root.setContentsMargins(28, 18, 28, 20)
        root.setSpacing(16)
        b = QPushButton("←  กลับไปคลังสไตล์")
        b.setObjectName("Link")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(self.back)
        root.addWidget(b, 0, Qt.AlignmentFlag.AlignLeft)
        t = QLabel("ตั้งค่า")
        t.setObjectName("Title")
        root.addWidget(t)

        # library folder
        root.addWidget(self._h("ที่เก็บคลัง"))
        self.path_lbl = QLabel()
        self.path_lbl.setWordWrap(True)
        self.path_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.path_lbl)
        row = QHBoxLayout()
        pick = QPushButton("เปลี่ยนที่เก็บ…")
        pick.clicked.connect(self._pick)
        openb = QPushButton("เปิดโฟลเดอร์")
        openb.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.s.library_path())))
        row.addWidget(pick)
        row.addWidget(openb)
        row.addStretch(1)
        root.addLayout(row)
        n = QLabel("ถ้าเปลี่ยนที่เก็บ คลิปเดิมจะยังอยู่ที่โฟลเดอร์เดิม ไม่ถูกย้ายหรือลบ")
        n.setObjectName("Soft")
        root.addWidget(n)
        root.addWidget(self._sep())

        # downloader
        root.addWidget(self._h("ตัวโหลดคลิป"))
        self.dl_lbl = QLabel()
        self.dl_lbl.setObjectName("Soft")
        root.addWidget(self.dl_lbl)
        self.up_btn = QPushButton("อัปเดตตัวโหลดคลิป")
        self.up_btn.clicked.connect(self._update)
        root.addWidget(self.up_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.up_msg = QLabel("")
        self.up_msg.setObjectName("Soft")
        self.up_msg.hide()
        root.addWidget(self.up_msg)
        h = QLabel("แพลตฟอร์มเปลี่ยนระบบบ่อย ถ้าโหลดคลิปไม่ได้ ให้กดปุ่มนี้ก่อน")
        h.setObjectName("Soft")
        root.addWidget(h)
        root.addWidget(self._sep())

        # speech -> text
        root.addWidget(self._h("ถอดคำพูดในคลิป"))
        sp = QLabel("ให้โปรแกรมฟังคำพูดในคลิปแล้วเขียนเป็นข้อความ (ภาษาไทยและภาษาอื่น) Claude จะได้รู้ว่าคลิปพูดอะไร ช่วงไหน "
                    f"ทำในเครื่องนี้ทั้งหมด ต้องดาวน์โหลดตัวถอดคำพูดครั้งเดียว {transcribe.MODEL_SIZE_TH}")
        sp.setObjectName("Soft")
        sp.setWordWrap(True)
        root.addWidget(sp)
        self.speech_lbl = QLabel()
        self.speech_lbl.setWordWrap(True)
        root.addWidget(self.speech_lbl)
        srow = QHBoxLayout()
        self.speech_btn = QPushButton("ดาวน์โหลดตัวถอดคำพูด")
        self.speech_btn.clicked.connect(self._speech_download)
        self.speech_cancel = QPushButton("ยกเลิก")
        self.speech_cancel.clicked.connect(self._speech_cancel_clicked)
        self.speech_cancel.hide()
        srow.addWidget(self.speech_btn)
        srow.addWidget(self.speech_cancel)
        srow.addStretch(1)
        root.addLayout(srow)
        self.speech_msg = QLabel("")
        self.speech_msg.setObjectName("Soft")
        self.speech_msg.setWordWrap(True)
        self.speech_msg.hide()
        root.addWidget(self.speech_msg)
        root.addWidget(self._sep())

        # browser login
        root.addWidget(self._h("คลิปที่ต้องล็อกอิน (Instagram / Facebook)"))
        self.login_cb = QCheckBox("ใช้การล็อกอินจากเบราว์เซอร์ในเครื่องนี้")
        self.login_cb.toggled.connect(self._login_toggled)
        root.addWidget(self.login_cb)
        brow = QHBoxLayout()
        bl = QLabel("เบราว์เซอร์ที่ล็อกอินไว้")
        bl.setObjectName("Soft")
        self.browser = QComboBox()
        self.browser.addItem("Chrome", "chrome")
        self.browser.addItem("Edge", "edge")
        self.browser.addItem("Firefox", "firefox")
        self.browser.currentIndexChanged.connect(self._browser_changed)
        brow.addWidget(bl)
        brow.addWidget(self.browser)
        brow.addStretch(1)
        root.addLayout(brow)
        self.login_warn = QLabel("โปรแกรมจะอ่านการล็อกอินจากเบราว์เซอร์ในเครื่องนี้เท่านั้น "
                                 "เพื่อโหลดคลิปที่ต้องล็อกอินก่อนดู ไม่ส่งข้อมูลไปที่ไหน และไม่แก้ไขอะไรในเบราว์เซอร์\n"
                                 "ถ้าอ่านจาก Chrome/Edge ไม่ได้ ให้ปิดเบราว์เซอร์ให้หมดก่อน หรือเลือก Firefox ซึ่งอ่านได้เสถียรกว่า")
        self.login_warn.setObjectName("Warn")
        self.login_warn.setWordWrap(True)
        root.addWidget(self.login_warn)
        root.addWidget(self._sep())

        cp = QLabel(COPYRIGHT_TH)
        cp.setObjectName("Hint")
        root.addWidget(cp)
        self.ver = QLabel(f"StyleVault เวอร์ชัน {VERSION}")
        self.ver.setObjectName("Soft")
        root.addWidget(self.ver)
        urow = QHBoxLayout()
        self.check_btn = QPushButton("เช็กเวอร์ชันใหม่")
        self.check_btn.clicked.connect(self._check_update)
        self.check_msg = QLabel("")
        self.check_msg.setObjectName("Soft")
        urow.addWidget(self.check_btn)
        urow.addWidget(self.check_msg)
        urow.addStretch(1)
        root.addLayout(urow)
        self.update_bar = None
        root.addStretch(1)

    def _h(self, text):
        l = QLabel(text)
        l.setObjectName("H2")
        return l

    def _sep(self):
        f = QFrame()
        f.setObjectName("Sep")
        return f

    def load(self):
        self.path_lbl.setText(self.s.library_path())
        self.dl_lbl.setText(f"เวอร์ชันตัวโหลดคลิป: {tools.ytdlp_version()}")
        self.login_cb.blockSignals(True)
        self.login_cb.setChecked(self.s.use_browser_login)
        self.login_cb.blockSignals(False)
        self.browser.blockSignals(True)
        self.browser.setCurrentIndex({"chrome": 0, "edge": 1, "firefox": 2}.get(self.s.browser, 0))
        self.browser.blockSignals(False)
        self._login_toggled(self.s.use_browser_login, save=False)
        self._speech_state()

    # ---- speech model
    def _speech_state(self):
        if self._speech_busy:
            return
        if not transcribe.find_cli():
            self.speech_lbl.setText("โปรแกรมรุ่นนี้ไม่มีตัวถอดคำพูด")
            self.speech_btn.hide()
        elif transcribe.model_ready():
            self.speech_lbl.setText("พร้อมใช้งาน — คลิปใหม่จะถูกถอดคำพูดให้เอง")
            self.speech_btn.hide()
        elif transcribe.old_model_present():
            self.speech_lbl.setText("มีตัวถอดคำพูดรุ่นใหม่ที่แม่นกว่าเดิมมาก (โดยเฉพาะภาษาไทย) — กดดาวน์โหลดเพื่อเปลี่ยน "
                                    "คลิปเดิมจะถูกถอดใหม่ให้เอง")
            self.speech_btn.setText("ดาวน์โหลดตัวถอดรุ่นใหม่")
            self.speech_btn.show()
        else:
            self.speech_lbl.setText("ยังไม่ได้ดาวน์โหลด")
            self.speech_btn.setText("ดาวน์โหลดตัวถอดคำพูด")
            self.speech_btn.show()

    def _speech_download(self):
        self._speech_busy = True
        self._speech_stop = False
        self.speech_btn.hide()
        self.speech_cancel.show()
        self.speech_msg.setText("กำลังเริ่มดาวน์โหลด…")
        self.speech_msg.show()

        def work():
            try:
                transcribe.download_model(lambda f, t: self._bg.speech_progress.emit(f, t), lambda: self._speech_stop)
                self._bg.speech_done.emit(True, "ดาวน์โหลดเสร็จแล้ว — กำลังถอดคำพูดคลิปเดิมในคลังให้ (ทำเบื้องหลัง)")
            except transcribe.TranscribeError as e:
                self._bg.speech_done.emit(False, str(e))
            except Exception:
                self._bg.speech_done.emit(False, "ดาวน์โหลดไม่สำเร็จ — ลองกดใหม่อีกครั้ง")
        threading.Thread(target=work, daemon=True).start()

    def _speech_cancel_clicked(self):
        self._speech_stop = True

    def _speech_progress(self, f: float, text: str):
        self.speech_lbl.setText(f"กำลังดาวน์โหลด {int(f * 100)}%")
        self.speech_msg.setText(text)

    def _speech_done(self, ok: bool, msg: str):
        self._speech_busy = False
        self.speech_cancel.hide()
        self.speech_msg.setText(msg)
        self._speech_state()
        if ok:
            self.speech_ready.emit()

    def _pick(self):
        d = QFileDialog.getExistingDirectory(self, "เลือกโฟลเดอร์เก็บคลัง", self.s.library_path())
        if d:
            self.s.library_dir = d
            self.s.save()
            self.path_lbl.setText(d)
            self.library_changed.emit(d)

    def _update(self):
        self.up_btn.setEnabled(False)
        self.up_msg.setText("กำลังอัปเดต… รอสักครู่")
        self.up_msg.show()
        threading.Thread(target=lambda: self._bg.done.emit(*tools.update_ytdlp()), daemon=True).start()

    def _update_done(self, ok: bool, msg: str):
        self.up_btn.setEnabled(True)
        self.up_msg.setText(msg)
        self.dl_lbl.setText(f"เวอร์ชันตัวโหลดคลิป: {tools.ytdlp_version()}")

    def _check_update(self):
        if not self.update_bar:
            return
        self.check_msg.setText("กำลังเช็ก…")
        self.update_bar.result_cb = self.check_msg.setText
        self.update_bar.check(manual=True)

    def _login_toggled(self, on: bool, save: bool = True):
        self.login_warn.setVisible(on)
        self.browser.setEnabled(on)
        if save:
            self.s.use_browser_login = on
            self.s.save()

    def _browser_changed(self):
        self.s.browser = self.browser.currentData()
        self.s.save()
