"""Main window: stacks the pages and handles adding clips (links and dropped files)."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QMenu, QStackedWidget, QVBoxLayout, QWidget

from .. import library as L
from ..jobs import Jobs
from ..settings import Settings
from . import dialogs, theme
from .detail_page import DetailPage
from .library_page import LibraryPage
from .compare_page import ComparePage
from .settings_page import COPYRIGHT_TH, SettingsPage
from .update_bar import UpdateBar


class MainWindow(QWidget):
    def __init__(self, settings: Settings):
        super().__init__()
        self.setObjectName("Main")
        self.s = settings
        self.setWindowTitle("คลังสไตล์ — StyleVault")
        self.setWindowIcon(theme.app_icon())
        self.resize(1120, 780)
        self.setMinimumSize(760, 560)
        self.setAcceptDrops(True)

        self.lib = L.Library(self.s.library_path())
        self.jobs = Jobs(lambda: self.lib, lambda: self.s)
        self.jobs.changed.connect(self._job_changed)
        self.jobs.progress.connect(self._job_progress)

        self.stack = QStackedWidget()
        self.library_page = LibraryPage()
        self.detail = DetailPage()
        self.settings_page = SettingsPage(self.s)
        self.compare = ComparePage()
        for w in (self.library_page, self.detail, self.settings_page, self.compare):
            self.stack.addWidget(w)
        self.update_bar = UpdateBar(is_busy=lambda: bool(self.jobs._active))
        self.settings_page.update_bar = self.update_bar
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.update_bar)
        lay.addWidget(self.stack)

        self.library_page.add_link.connect(self.add_link)
        self.library_page.open_clip.connect(self.open_clip)
        self.library_page.clip_menu.connect(self.clip_menu)
        self.library_page.open_settings.connect(self.open_settings)
        self.detail.back.connect(self.show_library)
        self.detail.delete_requested.connect(self.delete_clip)
        self.detail.retry_requested.connect(self.retry_clip)
        self.detail.tag_clicked.connect(self.show_tag)
        self.detail.compare_requested.connect(self.start_compare)
        self.compare.back.connect(self.show_library)
        self.compare.open_clip.connect(self.open_clip)
        self.settings_page.back.connect(self.show_library)
        self.settings_page.speech_ready.connect(self._queue_extras)
        self.settings_page.library_changed.connect(self._library_changed)

        self.drop_hint = QLabel("ปล่อยไฟล์วิดีโอที่นี่เพื่อเพิ่มเข้าคลัง", self)
        self.drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint.setStyleSheet(
            f"background: rgba(255,255,255,235); border: 2px dashed {theme.ACCENT.name()}; "
            f"border-radius: 14px; color: {theme.ACCENT.name()}; font-size: 18px; font-weight: 500;")
        self.drop_hint.hide()

        self.library_page.set_library(self.lib)
        self.lib.rebuild_index()
        self._recover()
        self._seen = self._signature()
        self._watch = QTimer(self, interval=1000, timeout=self._poll)      # Claude writes files: pick them up within ~1 s
        self._watch.start()
        if not os.environ.get("STYLEVAULT_NO_UPDATE_CHECK"):
            self.update_bar.check_later()

    def _signature(self) -> dict:
        """Modified-times of the files Claude (or the program) changes, per clip."""
        sig = {}
        try:
            names = os.listdir(self.lib.clips_dir)
        except OSError:
            return sig
        for n in names:
            d = self.lib.clip_dir(n)
            row = []
            for f in ("meta.json", "style-card.json"):
                try:
                    row.append(os.stat(os.path.join(d, f)).st_mtime_ns)
                except OSError:
                    row.append(None)
            sig[n] = tuple(row)
        return sig

    def _poll(self):
        now = self._signature()
        if now == self._seen:
            return
        changed = {k for k in set(now) | set(self._seen) if now.get(k) != self._seen.get(k)}
        self._seen = now
        try:
            self.lib.rebuild_index()
        except OSError:
            pass
        self.library_page.refresh()
        if self.stack.currentWidget() is self.detail and self.detail.clip_id in changed:
            self.detail.render()

    def _recover(self):
        """Clips left half-done (program closed mid-way) and clips from older versions that have no raw data yet."""
        for m in self.lib.list_meta():
            cid, st = m["id"], m.get("status")
            if self.jobs.is_active(cid):
                continue
            if st in ("downloading", "preparing"):
                if self.lib.video_path(cid):
                    self.lib.update_meta(cid, status="preparing", error=None)
                    self.jobs.add_prepare(cid)
                else:
                    self.lib.update_meta(cid, status="error",
                                         error="โปรแกรมถูกปิดก่อนโหลดคลิปเสร็จ — กดปุ่ม ⋯ บนการ์ดแล้วเลือกลองใหม่")
            elif st in ("waiting", "analyzed") and not m.get("raw_ready") and self.lib.video_path(cid):
                if st == "waiting":
                    self.lib.update_meta(cid, status="preparing")
                self.jobs.add_prepare(cid)
        self.library_page.refresh()
        self._queue_extras()

    def _queue_extras(self):
        """Sound names / spoken words for clips that were prepared before these existed (runs in the background)."""
        from .. import prepare
        for m in self.lib.list_meta():
            cid = m["id"]
            if m.get("raw_ready") and m.get("status") in ("waiting", "analyzed") and not self.jobs.is_active(cid):
                try:
                    if prepare.needs_extras(self.lib, cid):
                        self.jobs.add_extras(cid)
                except Exception:
                    pass

    # ---- navigation
    def show_library(self):
        self.detail.leave()
        self.library_page.refresh()
        self.stack.setCurrentWidget(self.library_page)

    def open_clip(self, clip_id: str):
        first = self.library_page.compare_first
        if first and self.stack.currentWidget() is self.library_page:
            if clip_id == first:
                return
            self.library_page.set_compare(None)
            if self.lib.meta(first):
                self.compare.show_pair(self.lib, first, clip_id)
                self.stack.setCurrentWidget(self.compare)
                return
        self.detail.show_clip(self.lib, clip_id)
        self.stack.setCurrentWidget(self.detail)

    def show_tag(self, tag: str):
        self.show_library()
        self.library_page.show_tag(tag)

    def start_compare(self, clip_id: str):
        m = self.lib.meta(clip_id) or {}
        card = self.lib.style_card(clip_id) if m.get("status") == "analyzed" else None
        title = (card or {}).get("name_th") or m.get("title") or "คลิปนี้"
        self.show_library()
        self.library_page.set_compare(clip_id, title[:40])

    def open_settings(self):
        self.settings_page.load()
        self.stack.setCurrentWidget(self.settings_page)

    def _library_changed(self, _path: str):
        self.lib = L.Library(self.s.library_path())
        self.library_page.set_library(self.lib)
        self.lib.rebuild_index()
        self._recover()
        self._seen = self._signature()

    # ---- adding clips
    def add_link(self, text: str):
        if not L.looks_like_url(text):
            dialogs.message(self, "ลิงก์ไม่ถูกต้อง", "ข้อความที่วางไม่ใช่ลิงก์\nลองคัดลอกลิงก์ของคลิปจากแอป แล้ววางใหม่อีกครั้ง")
            return
        url = L.normalize_url(text)
        plat = L.platform_of(url)
        if plat is None:
            if not dialogs.message(self, "ลิงก์นี้ไม่ใช่ของแพลตฟอร์มที่รองรับ",
                                   "โปรแกรมรองรับ TikTok, YouTube Shorts, Instagram Reels และ Facebook\nอยากลองโหลดลิงก์นี้ต่อไหม?",
                                   "ลองต่อ", "ยกเลิก"):
                return
            plat = "other"
        sid = L.short_id_of(url, plat)
        exist = self.lib.find_existing(plat, sid)
        if exist:
            dialogs.message(self, "มีคลิปนี้ในคลังแล้ว", "คลิปนี้เคยเพิ่มไว้แล้ว เปิดให้ดูเลยนะ")
            self.open_clip(exist)
            return
        kind = self._ask_kind()
        if not kind:
            return
        cid = self.lib.create_clip(plat, sid, kind, url)
        self._first_run_notice()
        self.library_page.clear_url()
        self.library_page.refresh()
        self.jobs.add_link(cid, url)

    def add_files(self, paths: list[str]):
        vids = [p for p in paths if os.path.isfile(p) and p.lower().endswith(L.VIDEO_EXTS)]
        if not vids:
            dialogs.message(self, "ไฟล์นี้เพิ่มไม่ได้", "ลากได้เฉพาะไฟล์วิดีโอ (.mp4 .mov .mkv .webm .avi .m4v)")
            return
        kind = self._ask_kind(len(vids))
        if not kind:
            return
        for src in vids:
            cid = self.lib.create_clip("file", L.file_short_id(src), kind, None, title=os.path.splitext(os.path.basename(src))[0])
            self.jobs.add_file(cid, src)
        self._first_run_notice()
        self.library_page.refresh()

    def _ask_kind(self, count: int = 1) -> str | None:
        kind = dialogs.ask_kind(self, self.s.last_kind, count)
        if kind:
            self.s.last_kind = kind
            self.s.save()
        return kind

    def _first_run_notice(self):
        if not self.s.first_run_done:
            self.s.first_run_done = True
            self.s.save()
            dialogs.message(self, "ก่อนเริ่มใช้", COPYRIGHT_TH)

    # ---- jobs
    def _job_changed(self, clip_id: str):
        self.library_page.refresh()
        if self.stack.currentWidget() is self.detail and self.detail.clip_id == clip_id:
            self.detail.show_clip(self.lib, clip_id)

    def _job_progress(self, clip_id: str, frac: float, text: str):
        self.library_page.set_progress(clip_id, frac, text)

    # ---- card menu
    def clip_menu(self, clip_id: str, pos):
        m = self.lib.meta(clip_id) or {}
        menu = QMenu(self)
        a_url = menu.addAction("เปิดลิงก์ต้นฉบับ") if m.get("source_url") else None
        a_dir = menu.addAction("เปิดโฟลเดอร์คลิป")
        a_retry = menu.addAction("ลองใหม่") if m.get("status") == "error" else None
        a_cmp = menu.addAction("เทียบกับคลิปอื่น")
        menu.addSeparator()
        a_del = menu.addAction("ลบออกจากคลัง")
        act = menu.exec(pos)
        if act is None:
            return
        if act is a_url:
            QDesktopServices.openUrl(QUrl(m["source_url"]))
        elif act is a_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.lib.clip_dir(clip_id)))
        elif act is a_retry:
            self.retry_clip(clip_id)
        elif act is a_cmp:
            self.start_compare(clip_id)
        elif act is a_del:
            self.delete_clip(clip_id)

    def retry_clip(self, clip_id: str):
        m = self.lib.meta(clip_id) or {}
        if self.jobs.is_active(clip_id):
            return
        if self.lib.video_path(clip_id):                           # video is there: only the data prep failed
            self.lib.update_meta(clip_id, status="preparing", error=None, error_detail=None)
            self.jobs.add_prepare(clip_id)
        elif m.get("source_url"):
            self.lib.update_meta(clip_id, status="downloading", error=None, error_detail=None)
            self.jobs.add_link(clip_id, m["source_url"])
        else:
            dialogs.message(self, "ลองใหม่ไม่ได้", "คลิปนี้มาจากไฟล์ ให้ลบแล้วลากไฟล์มาวางใหม่")
        self.library_page.refresh()
        if self.stack.currentWidget() is self.detail and self.detail.clip_id == clip_id:
            self.detail.render()

    def delete_clip(self, clip_id: str):
        if not dialogs.message(self, "ลบคลิปนี้ออกจากคลัง?",
                               "คลิปนี้และข้อมูลที่เกี่ยวข้อง (โน้ต การ์ดสไตล์) จะถูกลบออกจากโฟลเดอร์คลัง\n"
                               "ไฟล์ต้นฉบับที่คุณเคยลากมาวางจะไม่ถูกแตะต้อง",
                               "ลบ", "ยกเลิก"):
            return
        if self.jobs.is_active(clip_id):
            dialogs.message(self, "ยังลบไม่ได้", "คลิปนี้กำลังโหลดอยู่ รอให้เสร็จก่อนแล้วค่อยลบ")
            return
        self.lib.delete_clip(clip_id)
        if self.library_page.compare_first == clip_id:
            self.library_page.set_compare(None)
        if self.stack.currentWidget() is self.detail and self.detail.clip_id == clip_id:
            self.show_library()
        self.library_page.refresh()

    # ---- drag & drop of video files anywhere in the window
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.drop_hint.setGeometry(14, 14, self.width() - 28, self.height() - 28)
            self.drop_hint.raise_()
            self.drop_hint.show()

    def dragLeaveEvent(self, e):
        self.drop_hint.hide()

    def dropEvent(self, e):
        self.drop_hint.hide()
        urls = e.mimeData().urls()
        files = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if files:
            self.add_files(files)
        elif urls:
            self.add_link(urls[0].toString())
        e.acceptProposedAction()

    def closeEvent(self, e):
        self.detail.leave()
        super().closeEvent(e)
