import os
import shutil
import subprocess
import sys
import time

import pytest
from PySide6.QtWidgets import QApplication

from stylevault import library as L
from stylevault.settings import Settings
from stylevault.ui import dialogs, theme
from stylevault.ui.cards import Card, lines_clamped
from stylevault.ui.mainwindow import MainWindow

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    theme.load_fonts()
    a.setStyleSheet(theme.STYLE)
    return a


def make_window(tmp_path):
    s = Settings(library_dir=str(tmp_path / "lib"), first_run_done=True)
    os.environ["APPDATA"] = str(tmp_path / "appdata")
    return MainWindow(s)


def wait_until(app, cond, secs=60):
    end = time.time() + secs
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.05)
    return False


def seed(lib, n):
    for i in range(n):
        cid = lib.create_clip("tiktok", str(1000 + i), "effects" if i % 2 else "viral", f"https://x/{i}", status="waiting")
        lib.update_meta(cid, title=f"คลิป {i} " + "ชื่อยาวมากๆ " * (i % 5), view_count=1000 * i)


def test_all_cards_same_size_at_every_width(app, tmp_path):
    w = make_window(tmp_path)
    seed(w.lib, 9)
    w.library_page.refresh()
    for width in (760, 900, 1120, 1500):
        w.resize(width, 700)
        w.show()
        app.processEvents()
        cards = w.library_page.grid.cards
        assert len(cards) == 9
        assert len({(c.width(), c.height()) for c in cards}) == 1, width      # equal width AND height
        c0 = cards[0]
        assert abs(c0.height() - Card.height_for(c0.width())) <= 1
        assert c0.width() >= 200


def test_long_thai_titles_are_clamped_to_two_lines():
    f = theme.font(13, theme.MEDIUM)
    lines = lines_clamped("ฮุกเปิดคลิปด้วยตัวเลขใหญ่แล้วเฉลยตอนท้ายแบบกระชากอารมณ์คนดูมากๆเลยทีเดียว" * 3, f, 200)
    assert len(lines) == 2 and lines[-1].endswith("…")
    assert lines_clamped("", f, 200) == []


def test_filters(app, tmp_path):
    w = make_window(tmp_path)
    seed(w.lib, 6)
    cid = w.lib.list_ids()[0]
    w.lib.update_meta(cid, status="analyzed")
    w.library_page.refresh()
    p = w.library_page
    assert len(p.grid.cards) == 6
    p._set_filter("viral")
    assert all(c.meta["kind"] == "viral" for c in p.grid.cards)
    p._set_filter("waiting")
    assert all(c.meta["status"] == "waiting" for c in p.grid.cards) and len(p.grid.cards) == 5
    p._set_filter("all")
    p.search.setText("zzz-ไม่มี")
    assert len(p.grid.cards) == 0


def test_add_file_by_drop_flow(app, tmp_path, monkeypatch):
    if not shutil.which("ffmpeg"):
        pytest.skip("no ffmpeg")
    src = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=360x640:rate=30:duration=2",
                    "-pix_fmt", "yuv420p", str(src)], check=True)
    w = make_window(tmp_path)
    monkeypatch.setattr(dialogs, "ask_kind", lambda *a, **k: "viral")
    w.add_files([str(src), str(tmp_path / "not-a-video.txt")])
    assert wait_until(app, lambda: [m.get("status") for m in w.lib.list_meta()] == ["waiting"])
    m = w.lib.list_meta()[0]
    assert m["kind"] == "viral" and m["platform"] == "file"
    assert w.s.last_kind == "viral"                                           # remembers the last choice
    assert src.exists()


def test_add_link_duplicate_and_bad_text(app, tmp_path, monkeypatch):
    w = make_window(tmp_path)
    shown = []
    monkeypatch.setattr(dialogs, "message", lambda parent, title, text, *a, **k: shown.append(title) or True)
    monkeypatch.setattr(dialogs, "ask_kind", lambda *a, **k: "effects")
    monkeypatch.setattr(w.jobs, "add_link", lambda *a: None)                 # don't really download
    w.add_link("สวัสดี ไม่ใช่ลิงก์")
    assert shown == ["ลิงก์ไม่ถูกต้อง"] and not w.lib.list_ids()
    w.add_link("https://www.tiktok.com/@x/video/7412345")
    assert len(w.lib.list_ids()) == 1
    w.add_link("https://www.tiktok.com/@x/video/7412345?lang=th")
    assert shown[-1] == "มีคลิปนี้ในคลังแล้ว" and len(w.lib.list_ids()) == 1


def test_notes_autosave_and_detail_page(app, tmp_path):
    w = make_window(tmp_path)
    seed(w.lib, 1)
    cid = w.lib.list_ids()[0]
    w.open_clip(cid)
    w.detail.notes.setPlainText("เด่นเรื่องเสียงวูบ")
    w.show_library()                                                          # leaving saves the notes
    with open(w.lib.notes_path(cid), encoding="utf-8") as f:
        assert f.read() == "เด่นเรื่องเสียงวูบ"
    w.open_clip(cid)
    assert w.detail.notes.toPlainText() == "เด่นเรื่องเสียงวูบ"


def test_settings_survive_reload(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    s = Settings(library_dir="D:\\คลัง", last_kind="viral", use_browser_login=True, browser="edge")
    s.save()
    t = Settings.load()
    assert (t.library_dir, t.last_kind, t.use_browser_login, t.browser) == ("D:\\คลัง", "viral", True, "edge")


def test_broken_style_card_shows_message_not_crash(app, tmp_path):
    w = make_window(tmp_path)
    seed(w.lib, 1)
    cid = w.lib.list_ids()[0]
    w.lib.update_meta(cid, status="analyzed")
    with open(os.path.join(w.lib.clip_dir(cid), "style-card.json"), "w") as f:
        f.write("{oops")
    w.library_page.refresh()
    card = w.library_page.grid.cards[0]
    assert "อ่านไม่ได้" in card._title()[0]
    w.open_clip(cid)
