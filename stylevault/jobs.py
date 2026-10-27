"""Runs downloads / file copies one after another on a background thread."""
from __future__ import annotations

import queue
import threading

from PySide6.QtCore import QObject, Signal

from . import ingest
from .library import Library


class Jobs(QObject):
    changed = Signal(str)                 # clip id: its meta.json changed
    progress = Signal(str, float, str)    # clip id, 0..1, text

    def __init__(self, get_library, get_settings):
        super().__init__()
        self._lib = get_library
        self._settings = get_settings
        self._q: queue.Queue = queue.Queue()
        self._active: set[str] = set()
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()

    def is_active(self, clip_id: str) -> bool:
        return clip_id in self._active

    def add_link(self, clip_id: str, url: str):
        self._enqueue(("link", clip_id, url))

    def add_file(self, clip_id: str, path: str):
        self._enqueue(("file", clip_id, path))

    def add_extras(self, clip_id: str):
        self._enqueue(("extras", clip_id, None))

    def add_prepare(self, clip_id: str):
        self._enqueue(("prepare", clip_id, None))

    def _enqueue(self, job):
        self._active.add(job[1])
        self._q.put((self._lib(), self._settings(), job))
        self.changed.emit(job[1])

    def _loop(self):
        while True:
            lib, settings, (kind, clip_id, arg) = self._q.get()
            lib: Library
            def prog(frac, text, cid=clip_id):
                self.progress.emit(cid, frac, text)
            try:
                if kind == "prepare":
                    from . import prepare
                    try:
                        prepare.prepare(lib, clip_id, prog)
                    except prepare.PrepareError as e:
                        raise ingest.IngestError(str(e))
                elif kind == "extras":
                    from . import prepare
                    prepare.extras(lib, clip_id, prog)
                elif kind == "link":
                    ingest.download(lib, clip_id, arg, settings, prog)
                else:
                    ingest.add_file(lib, clip_id, arg, prog)
            except ingest.IngestError as e:
                lib.update_meta(clip_id, status="error", error=str(e), error_detail=getattr(e, "detail", "") or None)
            except Exception:
                lib.update_meta(clip_id, status="error",
                                error="เกิดข้อผิดพลาดที่ไม่คาดคิด — กดลองใหม่ ถ้ายังไม่หายให้ลบแล้วเพิ่มใหม่")
            finally:
                self._active.discard(clip_id)
                try:
                    lib.rebuild_index()
                except Exception:
                    pass
                self.changed.emit(clip_id)
