"""Small settings page: library folder, clip-downloader update, browser login, version."""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from .. import VERSION, autostart, tools, transcribe
from ..settings import Settings
from . import dialogs, theme

COPYRIGHT_TH = "คลิปในคลังใช้เพื่อศึกษาเท่านั้น ห้ามนำไปโพสต์ซ้ำ"


class _Bg(QObject):
    done = Signal(bool, str)
    speech_progress = Signal(float, str)
    speech_done = Signal(bool, str)


class SettingsPage(QWidget):
    back = Signal()
    library_changed = Signal(str)
    speech_ready = Signal()
    tg_changed = Signal()

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
        sp = QLabel("ให้โปรแกรมฟังคำพูดในคลิปแล้วเขียนเป็นข้อความ (ใช้ตัวถอดที่ทำมาสำหรับภาษาไทยโดยเฉพาะ) Claude จะได้รู้ว่าคลิปพูดอะไร ช่วงไหน และวิเคราะห์สคริปต์ให้ "
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

        self._build_telegram(root)

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

    # ---- Telegram (links from the phone)
    TG_STATUS = {"ok": "พร้อมรับลิงก์ ✓", "connecting": "กำลังเชื่อม…", "offline": "ต่ออินเทอร์เน็ตไม่ได้ — จะลองใหม่เอง",
                 "conflict": "มีโปรแกรมอื่นใช้บอทนี้อยู่ — ปิดอันอื่นก่อน", "badtoken": "รหัสบอทใช้ไม่ได้แล้ว — กดยกเลิกการเชื่อมแล้วเชื่อมใหม่",
                 "paused": "หยุดรับลิงก์ชั่วคราว (เปิดใหม่ได้จากไอคอนข้างนาฬิกา)", "off": ""}

    def _build_telegram(self, root):
        self.tg = None
        self._tg_verifying = False
        root.addWidget(self._h("ส่งลิงก์จากมือถือ (Telegram)"))
        intro = QLabel("แชร์ลิงก์คลิปจากมือถือเข้าบอท Telegram ของคุณเอง แล้วโปรแกรมนี้จะโหลดเข้าคลังให้ "
                       "ส่งแค่ลิงก์ ไม่มีไฟล์ของคุณขึ้นอินเทอร์เน็ต และรับจากบัญชี Telegram ของคุณคนเดียว")
        intro.setObjectName("Soft")
        intro.setWordWrap(True)
        root.addWidget(intro)

        # not connected yet: the 3-step wizard
        self.tg_wizard = QWidget()
        w = QVBoxLayout(self.tg_wizard)
        w.setContentsMargins(0, 0, 0, 0)
        w.setSpacing(8)
        for t in ("1. เปิด Telegram ค้นหา @BotFather แล้วพิมพ์ /newbot ตั้งชื่อบอทตามใจชอบ",
                  "2. BotFather จะส่ง \"รหัสบอท\" ยาวๆ มาให้ คัดลอกมาวางด้านล่าง"):
            l = QLabel(t)
            l.setWordWrap(True)
            w.addWidget(l)
        self.tg_token_edit = QLineEdit()
        self.tg_token_edit.setPlaceholderText("วางรหัสบอทที่นี่ เช่น 123456789:AAH…")
        self.tg_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        w.addWidget(self.tg_token_edit)
        self.tg_check_btn = QPushButton("ตรวจรหัสบอท")
        self.tg_check_btn.setObjectName("Primary")
        self.tg_check_btn.clicked.connect(self._tg_check)
        w.addWidget(self.tg_check_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.tg_result = QLabel("")
        self.tg_result.setWordWrap(True)
        self.tg_result.hide()
        w.addWidget(self.tg_result)
        self.tg_step3 = QWidget()
        s3 = QVBoxLayout(self.tg_step3)
        s3.setContentsMargins(0, 0, 0, 0)
        s3.setSpacing(6)
        l3 = QLabel("3. เปิดแชตกับบอทตัวนี้ในมือถือ แล้วพิมพ์รหัสยืนยันนี้ส่งไป:")
        l3.setWordWrap(True)
        s3.addWidget(l3)
        self.tg_code = QLabel("")
        self.tg_code.setStyleSheet(f"font-size: 26px; font-weight: 500; letter-spacing: 6px; color: {theme.ACCENT.name()};")
        s3.addWidget(self.tg_code)
        self.tg_wait = QLabel("โปรแกรมกำลังรอรหัสนี้อยู่ พอเชื่อมสำเร็จหน้านี้จะเปลี่ยนเอง")
        self.tg_wait.setObjectName("Soft")
        self.tg_wait.setWordWrap(True)
        s3.addWidget(self.tg_wait)
        self.tg_newcode = QPushButton("สร้างรหัสใหม่")
        self.tg_newcode.clicked.connect(self._tg_new_code)
        self.tg_newcode.hide()
        s3.addWidget(self.tg_newcode, 0, Qt.AlignmentFlag.AlignLeft)
        self.tg_step3.hide()
        w.addWidget(self.tg_step3)
        root.addWidget(self.tg_wizard)

        # connected
        self.tg_done = QWidget()
        d = QVBoxLayout(self.tg_done)
        d.setContentsMargins(0, 0, 0, 0)
        d.setSpacing(8)
        self.tg_status = QLabel("")
        self.tg_status.setObjectName("Good")
        self.tg_status.setWordWrap(True)
        d.addWidget(self.tg_status)
        self.tg_event = QLabel("")
        self.tg_event.setObjectName("Soft")
        self.tg_event.setWordWrap(True)
        d.addWidget(self.tg_event)
        self.tg_auto_cb = QCheckBox("เปิดโปรแกรมเองตอนเปิดคอม")
        self.tg_auto_cb.toggled.connect(self._tg_autostart)
        d.addWidget(self.tg_auto_cb)
        self.tg_tray_cb = QCheckBox("ปิดหน้าต่างแล้วให้ทำงานต่อที่ไอคอนข้างนาฬิกา")
        self.tg_tray_cb.toggled.connect(self._tg_tray)
        d.addWidget(self.tg_tray_cb)
        self.tg_bye_cb = QCheckBox("ตอนปิดโปรแกรม ให้ส่งข้อความบอกในแชตมือถือ")
        self.tg_bye_cb.toggled.connect(self._tg_bye)
        d.addWidget(self.tg_bye_cb)
        krow = QHBoxLayout()
        kl = QLabel("ถ้าไม่กดเลือกประเภทคลิปในมือถือ ให้ใช้")
        kl.setObjectName("Soft")
        self.tg_kind = QComboBox()
        self.tg_kind.addItem("คลิปไวรัล", "viral")
        self.tg_kind.addItem("สไตล์เอฟเฟกต์", "effects")
        self.tg_kind.currentIndexChanged.connect(self._tg_kind)
        krow.addWidget(kl)
        krow.addWidget(self.tg_kind)
        krow.addStretch(1)
        d.addLayout(krow)
        self.tg_warn = QLabel("ถ้าปิดโปรแกรมจริงๆ (คลิกขวาที่ไอคอน → ออกจากโปรแกรม) บอทจะรับลิงก์ไม่ได้ "
                              "Telegram เก็บลิงก์ไว้ให้ 24 ชั่วโมง เปิดโปรแกรมใหม่แล้วจะเข้าคลังเอง")
        self.tg_warn.setObjectName("Warn")
        self.tg_warn.setWordWrap(True)
        d.addWidget(self.tg_warn)
        self.tg_off_btn = QPushButton("ยกเลิกการเชื่อม")
        self.tg_off_btn.clicked.connect(self._tg_disconnect)
        d.addWidget(self.tg_off_btn, 0, Qt.AlignmentFlag.AlignLeft)
        root.addWidget(self.tg_done)
        root.addWidget(self._sep())

    def bind_telegram(self, service):
        self.tg = service
        service.verified.connect(self._tg_verified)
        service.paired.connect(self._tg_paired)
        service.pair_locked.connect(self._tg_locked)
        service.status.connect(self._tg_state)
        service.event.connect(lambda t: self.tg_event.setText("ข้อความล่าสุดที่บอทได้รับ: " + t))

    def _tg_render(self):
        connected = bool(self.s.tg_token and self.s.tg_chat_id)
        self.tg_done.setVisible(connected)
        self.tg_wizard.setVisible(not connected)
        if connected:
            self._tg_state(self.tg.state if self.tg else "off")
            last = self.tg.last_event if self.tg else ""
            self.tg_event.setText(("ข้อความล่าสุดที่บอทได้รับ: " + last) if last else
                                  "ยังไม่มีข้อความเข้ามา — ลองส่งลิงก์เข้าบอท แล้วดูบรรทัดนี้เปลี่ยน")
            for cb, val in ((self.tg_auto_cb, self.s.autostart and autostart.is_enabled()), (self.tg_tray_cb, self.s.tray_on_close), (self.tg_bye_cb, self.s.tg_notify_quit)):
                cb.blockSignals(True)
                cb.setChecked(bool(val))
                cb.blockSignals(False)
            self.tg_kind.blockSignals(True)
            self.tg_kind.setCurrentIndex(0 if self.s.tg_default_kind != "effects" else 1)
            self.tg_kind.blockSignals(False)
        else:
            code = self.tg.code if self.tg else None
            self.tg_step3.setVisible(bool(code) or self.tg_newcode.isVisible())
            if code:
                self.tg_code.setText(code)

    def _tg_state(self, st: str):
        self.tg_status.setText("✓ เชื่อมแล้ว — " + self.TG_STATUS.get(st, ""))
        self.tg_status.setObjectName("Good" if st in ("ok", "connecting") else "Warn")
        self.tg_status.style().unpolish(self.tg_status)
        self.tg_status.style().polish(self.tg_status)

    def _tg_check(self):
        token = self.tg_token_edit.text().strip()
        if not token or not self.tg:
            self._tg_msg("วางรหัสบอทก่อนนะ ได้มาจาก BotFather ในข้อ 2", good=False)
            return
        self._tg_verifying = True
        self.tg_check_btn.setEnabled(False)
        self._tg_msg("กำลังตรวจ…", good=True)
        self.tg.verify(token)

    def _tg_msg(self, text: str, good: bool):
        self.tg_result.setText(text)
        self.tg_result.setObjectName("Good" if good else "Warn")
        self.tg_result.style().unpolish(self.tg_result)
        self.tg_result.style().polish(self.tg_result)
        self.tg_result.show()

    def _tg_verified(self, ok: bool, msg: str):
        if not self._tg_verifying:
            return
        self._tg_verifying = False
        self.tg_check_btn.setEnabled(True)
        if not ok:
            self._tg_msg(msg, good=False)
            return
        self._tg_msg(f"✓ เจอบอทชื่อ {msg}", good=True)
        self.s.tg_token = self.tg_token_edit.text().strip()
        self.s.tg_chat_id = 0
        self.s.save()
        self.tg.configure(self.s.tg_token, 0, self.s.tg_default_kind, pairing=True)
        self.tg_newcode.hide()
        self.tg_wait.setText("โปรแกรมกำลังรอรหัสนี้อยู่ พอเชื่อมสำเร็จหน้านี้จะเปลี่ยนเอง")
        self.tg_step3.show()
        self.tg_code.setText(self.tg.code or "")

    def _tg_new_code(self):
        code = self.tg.new_pair_code() if self.tg else None
        if code:
            self.tg_code.setText(code)
            self.tg_newcode.hide()
            self.tg_wait.setText("โปรแกรมกำลังรอรหัสนี้อยู่ พอเชื่อมสำเร็จหน้านี้จะเปลี่ยนเอง")

    def _tg_locked(self):
        self.tg_code.setText("— — — —")
        self.tg_wait.setText("รหัสถูกยกเลิก เพราะมีคนส่งรหัสผิดหลายครั้ง กดสร้างรหัสใหม่")
        self.tg_newcode.show()

    def _tg_paired(self, *_):
        self.tg_token_edit.clear()
        self.tg_result.hide()
        self.tg_step3.hide()
        self._tg_render()
        self.tg_changed.emit()

    def _tg_autostart(self, on: bool):
        ok = autostart.set_enabled(on)
        if on and not ok:
            self.tg_auto_cb.blockSignals(True)
            self.tg_auto_cb.setChecked(False)
            self.tg_auto_cb.blockSignals(False)
            dialogs.message(self, "ตั้งไม่ได้", "ตัวเลือกนี้ใช้ได้เฉพาะโปรแกรมที่ติดตั้งจากตัวติดตั้งแล้วเท่านั้น")
            on = False
        self.s.autostart = on
        self.s.save()

    def _tg_bye(self, on: bool):
        self.s.tg_notify_quit = on
        self.s.save()

    def _tg_tray(self, on: bool):
        self.s.tray_on_close = on
        self.s.save()
        self.tg_changed.emit()

    def _tg_kind(self):
        self.s.tg_default_kind = self.tg_kind.currentData()
        self.s.save()
        if self.tg:
            self.tg.set_default_kind(self.s.tg_default_kind)

    def _tg_disconnect(self):
        if not dialogs.message(self, "ยกเลิกการเชื่อม Telegram?",
                               "โปรแกรมจะเลิกรับลิงก์จากบอท (คลิปที่อยู่ในคลังไม่หาย) เชื่อมใหม่ได้ทุกเมื่อ",
                               "ยกเลิกการเชื่อม", "ไม่ยกเลิก"):
            return
        if self.tg:
            self.tg.disconnect()
        self.s.tg_token, self.s.tg_chat_id, self.s.tg_paused = "", 0, False
        self.s.save()
        self._tg_render()
        self.tg_changed.emit()

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
        self._tg_render()

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
