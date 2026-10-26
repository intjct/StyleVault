"""The thin bar at the top: "มีเวอร์ชันใหม่ · อัปเดตเลย". Waits for the user to press the button."""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton

from .. import updater
from . import dialogs, theme


class _Bridge(QObject):
    found = Signal(object)            # info dict or None
    failed = Signal(str)
    progress = Signal(float)
    downloaded = Signal(str)


class UpdateBar(QFrame):
    def __init__(self, is_busy=lambda: False):
        super().__init__()
        self.is_busy = is_busy
        self.info: dict | None = None
        self.manual = False
        self.checking = False
        self.setStyleSheet(f"QFrame#UpdateBar {{ background:{theme.ACCENT_SOFT.name()}; }}"
                           f"QLabel {{ color:{theme.ACCENT.name()}; font-weight:500; background:transparent; }}")
        self.setObjectName("UpdateBar")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(28, 8, 28, 8)
        self.label = QLabel()
        lay.addWidget(self.label)
        lay.addStretch(1)
        self.go = QPushButton("อัปเดตเลย")
        self.go.setObjectName("Primary")
        self.go.setCursor(Qt.CursorShape.PointingHandCursor)
        self.go.clicked.connect(self._on_go)
        self.later = QPushButton("ไว้ทีหลัง")
        self.later.setCursor(Qt.CursorShape.PointingHandCursor)
        self.later.clicked.connect(self.hide)
        for b in (self.go, self.later):
            b.setStyleSheet("padding:5px 14px;")
            lay.addWidget(b)
        self.b = _Bridge()
        self.b.found.connect(self._found)
        self.b.failed.connect(self._failed)
        self.b.progress.connect(self._progress)
        self.b.downloaded.connect(self._downloaded)
        self.hide()
        self.result_cb = None          # settings page listens: callback(text)

    # ---- checking
    def check_later(self, ms: int = 4000):
        QTimer.singleShot(ms, lambda: self.check(manual=False))

    def check(self, manual: bool = True):
        if self.checking:
            return
        self.checking, self.manual = True, manual

        def work():
            try:
                self.b.found.emit(updater.check())
            except updater.UpdateError as e:
                self.b.failed.emit(str(e))
        threading.Thread(target=work, daemon=True).start()

    def _found(self, info):
        self.checking = False
        if info:
            self.info = info
            self._show_ready()
            self._report(f"มีเวอร์ชันใหม่ {info['version']}")
        else:
            self._report("คุณใช้เวอร์ชันล่าสุดอยู่แล้ว")

    def _failed(self, msg: str):
        was_checking, self.checking = self.checking, False
        if not was_checking and self.info:        # the download failed: say so on the bar and let them retry
            self.label.setText(msg)
            self.go.setEnabled(True)
            self.go.setText("ลองใหม่")
            self.later.show()
            return
        self._report(msg)                          # a quiet start-up check never bothers the user when it fails

    def _report(self, text: str):
        if self.result_cb and self.manual:
            self.result_cb(text)

    # ---- the bar
    def _show_ready(self):
        self.label.setText(f"มีเวอร์ชันใหม่ {self.info['version']}  ·  กด \"อัปเดตเลย\" แล้วโปรแกรมจะติดตั้งและเปิดใหม่ให้เอง")
        self.go.setEnabled(True)
        self.go.setText("อัปเดตเลย")
        self.later.show()
        self.show()

    def _on_go(self):
        if not self.info:
            return
        if not updater.can_install():
            dialogs.message(self, "อัปเดตตอนนี้ไม่ได้",
                            "ตอนนี้เปิดโปรแกรมแบบนักพัฒนาอยู่ จึงอัปเดตให้อัตโนมัติไม่ได้\nให้โหลดตัวติดตั้งจากหน้า Releases แทน")
            return
        if self.is_busy() and not dialogs.message(
                self, "ตอนนี้ยังมีงานค้างอยู่",
                "กำลังโหลดหรือเตรียมคลิปอยู่ ถ้าอัปเดตตอนนี้งานนั้นจะหยุดกลางคัน\n"
                "(เปิดโปรแกรมใหม่แล้วมันจะทำต่อหรือกดลองใหม่ได้ ไฟล์ที่เก็บไว้ไม่หาย)\nอัปเดตเลยไหม?",
                "อัปเดตเลย", "รอให้เสร็จก่อน"):
            return
        self.go.setEnabled(False)
        self.later.hide()
        self.label.setText("กำลังโหลดตัวอัปเดต… 0%")

        def work(info=self.info):
            try:
                self.b.downloaded.emit(updater.download(info, self.b.progress.emit))
            except updater.UpdateError as e:
                self.b.failed.emit(str(e))
        threading.Thread(target=work, daemon=True).start()

    def _progress(self, frac: float):
        self.label.setText(f"กำลังโหลดตัวอัปเดต… {int(frac * 100)}%")

    def _downloaded(self, path: str):
        self.label.setText("กำลังติดตั้ง… โปรแกรมจะปิดแล้วเปิดใหม่เอง")
        try:
            updater.run_installer(path)
        except OSError:
            self.label.setText("เปิดตัวติดตั้งไม่สำเร็จ — ลองกดอีกครั้ง")
            self.go.setEnabled(True)
            self.go.setText("ลองใหม่")
            return
        QTimer.singleShot(800, QApplication.quit)
