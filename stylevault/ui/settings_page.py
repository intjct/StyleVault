"""Small settings page: library folder, clip-downloader update, browser login, version."""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from .. import VERSION, tools
from ..settings import Settings
from . import theme

COPYRIGHT_TH = "คลิปในคลังใช้เพื่อศึกษาเท่านั้น ห้ามนำไปโพสต์ซ้ำ"


class _Bg(QObject):
    done = Signal(bool, str)


class SettingsPage(QWidget):
    back = Signal()
    library_changed = Signal(str)

    def __init__(self, settings: Settings):
        super().__init__()
        self.setObjectName("Page")
        self.s = settings
        self._bg = _Bg()
        self._bg.done.connect(self._update_done)

        root = QVBoxLayout(self)
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
        self.browser.currentIndexChanged.connect(self._browser_changed)
        brow.addWidget(bl)
        brow.addWidget(self.browser)
        brow.addStretch(1)
        root.addLayout(brow)
        self.login_warn = QLabel("โปรแกรมจะอ่านการล็อกอินจากเบราว์เซอร์ในเครื่องนี้เท่านั้น "
                                 "เพื่อโหลดคลิปที่ต้องล็อกอินก่อนดู ไม่ส่งข้อมูลไปที่ไหน และไม่แก้ไขอะไรในเบราว์เซอร์")
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
        self.browser.setCurrentIndex(1 if self.s.browser == "edge" else 0)
        self.browser.blockSignals(False)
        self._login_toggled(self.s.use_browser_login, save=False)

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

    def _login_toggled(self, on: bool, save: bool = True):
        self.login_warn.setVisible(on)
        self.browser.setEnabled(on)
        if save:
            self.s.use_browser_login = on
            self.s.save()

    def _browser_changed(self):
        self.s.browser = self.browser.currentData()
        self.s.save()
