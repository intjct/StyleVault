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


def test_old_clips_without_raw_data_get_prepared_on_start(app, tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("no ffmpeg")
    lib = L.Library(str(tmp_path / "lib"))
    cid = lib.create_clip("file", "old1", "effects", None, status="waiting")     # made by v0.1: no raw/ yet
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=360x640:rate=30:duration=2",
                    "-pix_fmt", "yuv420p", os.path.join(lib.clip_dir(cid), "video.mp4")], check=True)
    dead = lib.create_clip("tiktok", "dead1", "viral", "https://x", status="downloading")   # app was closed mid-download
    w = make_window(tmp_path)
    assert wait_until(app, lambda: (w.lib.meta(cid) or {}).get("raw_ready") is True)
    assert w.lib.meta(cid)["status"] == "waiting"
    assert w.lib.meta(dead)["status"] == "error" and "ลองใหม่" in w.lib.meta(dead)["error"]


def test_copy_command_works_in_a_brand_new_chat(app, tmp_path):
    w = make_window(tmp_path)
    seed(w.lib, 1)
    cid = w.lib.list_ids()[0]
    w.lib.update_meta(cid, raw_ready=True)
    w.library_page.refresh()
    assert not w.library_page.copy_cmd.isHidden()
    w.library_page._copy_command()
    text = QApplication.clipboard().text()
    assert w.lib.root in text and "CLAUDE-README.md" in text and "วิเคราะห์คลิปใหม่" in text
    w.open_clip(cid)
    w.detail._copy_command()
    assert w.lib.root in QApplication.clipboard().text()


# ---------------------------------------------------------------- v0.4.0: style card, timeline, folder watching
import json

from sample_card import CARD, card as make_card
from stylevault.ui.timeline import PAD, BAR_Y, Timeline


def analyzed_clip(w, tmp_path, name="p"):
    """A clip that has raw data (2 cuts, 2 sound effects) so the timeline has something to show."""
    cid = w.lib.create_clip("tiktok", name, "effects", "https://x", status="waiting")
    w.lib.update_meta(cid, duration_sec=10.0, raw_ready=True, title="คลิปทดสอบ")
    raw = os.path.join(w.lib.clip_dir(cid), "raw")
    os.makedirs(raw)
    L.write_json(os.path.join(raw, "cuts.json"), {"cuts_sec": [2.5, 5.0], "cut_count": 2, "avg_shot_sec": 3.33})
    L.write_json(os.path.join(raw, "audio.json"), {"has_audio": True, "bpm": 120, "onsets_sec": [0.38, 2.4], "silences": [],
                 "sfx": [{"t": 0.38, "file": "sfx/0001_00.38s.wav", "label": None, "confidence": None},
                         {"t": 2.4, "file": "sfx/0002_02.40s.wav", "label": None, "confidence": None}]})
    return cid


def test_card_written_by_hand_shows_up_within_two_seconds(app, tmp_path):
    w = make_window(tmp_path)
    cid = analyzed_clip(w, tmp_path)
    w.library_page.refresh()
    assert w.library_page.grid.cards[0]._title()[0] == "รอวิเคราะห์"
    w.open_clip(cid)
    assert w.detail.card_holder.count() == 0
    # Claude writes the card and flips the status
    L.write_json(os.path.join(w.lib.clip_dir(cid), "style-card.json"), CARD)
    w.lib.update_meta(cid, status="analyzed")
    t0 = time.time()
    assert wait_until(app, lambda: w.detail.card_holder.count() > 0, secs=4)
    assert time.time() - t0 < 2.5                                           # the plan asks for 2 s
    assert w.detail.title_lbl.text() == CARD["name_th"]
    assert w.library_page.cards[cid]._title()[0] == CARD["name_th"]
    # the index Claude reads is refreshed too
    idx = L.read_json(os.path.join(w.lib.root, "library-index.json"))
    assert idx["clips"][0]["name_th"] == CARD["name_th"]


def test_detail_page_shows_everything_in_plain_thai(app, tmp_path):
    w = make_window(tmp_path)
    cid = analyzed_clip(w, tmp_path)
    L.write_json(os.path.join(w.lib.clip_dir(cid), "style-card.json"), CARD)
    w.lib.update_meta(cid, status="analyzed")
    w.open_clip(cid)
    texts = " ".join(l.text() for l in w.detail.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel))
    for need in ("การ์ดคำคมคนดัง", "เหมาะกับ", "คำเด้งขึ้นทีละคำ / พิมพ์ดีดทีละตัว", "ซูมกระแทก", "โครงเรื่อง", "ฮุก: คำคมใหญ่เต็มจอ",
                 "30 ภาพต่อวินาที", "48 เฟรม (ประมาณ 1.6 วินาที)", "0:00.38", "เสียงวูบ", "ข้อจำกัด"):
        assert need in texts, need
    for jargon in ("word-pop", "zoom-punch", "JSON", "remotion_recipe", "fps"):
        assert jargon not in texts, jargon
    assert not w.detail.timeline.isHidden() and w.detail.timeline.cuts == [2.5, 5.0] and len(w.detail.timeline.sfx) == 2
    assert w.detail.timeline.sfx[0]["label"] == "เสียงวูบ"                  # label comes from Claude's card


def test_broken_card_never_crashes_and_recovers(app, tmp_path):
    w = make_window(tmp_path)
    cid = analyzed_clip(w, tmp_path)
    path = os.path.join(w.lib.clip_dir(cid), "style-card.json")
    w.lib.update_meta(cid, status="analyzed")
    w.open_clip(cid)
    for junk in ("{oops", json.dumps([1, 2]), json.dumps(make_card(tags="เร็ว")), json.dumps(make_card(structure=[{"from": "a"}])), ""):
        with open(path, "w", encoding="utf-8") as f:
            f.write(junk)
        w.lib.update_meta(cid, status="analyzed")                          # touch -> watcher fires
        assert wait_until(app, lambda: cid in w.library_page.cards and "อ่านไม่ได้" in w.library_page.cards[cid]._title()[0], secs=4), junk
        assert "อ่านไม่ได้" in w.detail.status_box.text()
        assert w.detail.card_holder.count() == 0
    L.write_json(path, CARD)                                                # fixed by Claude: recovers on its own
    w.lib.update_meta(cid, status="analyzed")
    assert wait_until(app, lambda: w.detail.card_holder.count() > 0, secs=4)


def test_timeline_clicks(app, tmp_path):
    tl = Timeline()
    tl.resize(600, 80)
    tl.set_data(10.0, [2.5, 5.0], [{"t": 2.4, "file": "sfx/a.wav", "label": "เสียงวูบ"}])
    jumps, sounds = [], []
    tl.seek.connect(jumps.append)
    tl.play_sfx.connect(sounds.append)
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QEvent

    def click(x, y):
        e = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(x, y), QPointF(x, y), Qt.MouseButton.LeftButton,
                        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        tl.mousePressEvent(e)
    click(tl._x(7.0), 30)                                                    # empty place: jump there
    assert len(jumps) == 1 and abs(jumps[0] - 7.0) < 0.05 and not sounds
    click(tl._x(2.4), BAR_Y)                                                 # orange dot: play it (and jump to it)
    assert sounds == ["sfx/a.wav"] and abs(jumps[-1] - 2.4) < 0.01
    click(-50, 30)                                                           # far left: clamps to the start
    assert jumps[-1] == 0.0
    tl.grab()                                                                # paints without error
    Timeline().grab()                                                        # empty timeline too


# ---------------------------------------------------------------- v0.4.1: visible delete/retry, scrolling settings
def test_delete_and_retry_buttons_on_detail_page(app, tmp_path, monkeypatch):
    w = make_window(tmp_path)
    cid = w.lib.create_clip("facebook", "z", "effects", "https://x", status="error")
    w.lib.update_meta(cid, error="ลองใหม่นะ", error_detail="line1\nERROR: boom")
    w.open_clip(cid)
    assert not w.detail.retry_btn.isHidden() and not w.detail.delete_btn.isHidden()
    assert "boom" in w.detail.status_box.text()
    monkeypatch.setattr(dialogs, "message", lambda *a, **k: True)
    monkeypatch.setattr(w.jobs, "add_link", lambda *a, **k: None)
    w.detail.retry_btn.click()
    assert w.lib.meta(cid)["status"] == "downloading"
    w.lib.update_meta(cid, status="error")
    w.detail.delete_btn.click()
    assert w.lib.meta(cid) is None and w.stack.currentWidget() is w.library_page


def test_card_menu_button_opens_menu_and_settings_scrolls(app, tmp_path):
    from PySide6.QtCore import QPointF, Qt, QEvent
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QScrollArea
    w = make_window(tmp_path)
    cid = w.lib.create_clip("tiktok", "q", "effects", "https://x", status="waiting")
    c = Card(cid)                                     # standalone card: the real menu would block the test
    c.set_data(w.lib.meta(cid), None, None)
    c.resize(220, 400)
    got = []
    c.menu.connect(lambda i, pos: got.append(i))
    pt = c._menu_rect().center()
    e = QMouseEvent(QEvent.Type.MouseButtonRelease, pt, c.mapToGlobal(pt), Qt.MouseButton.LeftButton,
                    Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    c.mouseReleaseEvent(e)
    assert got == [cid]
    assert w.settings_page.findChild(QScrollArea) is not None
    c.grab()


# ---------------------------------------------------------------- v0.5.0: speech, sound names, tags, compare
def _speech_and_labels(w, cid):
    raw = os.path.join(w.lib.clip_dir(cid), "raw")
    a = L.read_json(os.path.join(raw, "audio.json"))
    a["sfx"][0].update(label="Whoosh, swoosh, swish", label_th="เสียงวูบ (ฟิ้ว)", confidence=0.6)
    a["sfx"][1].update(label="Typing", label_th="เสียงพิมพ์ดีด", confidence=0.4)
    a["labels_version"] = 1
    L.write_json(os.path.join(raw, "audio.json"), a)
    L.write_json(os.path.join(raw, "transcript.json"), {"language": "th", "has_speech": True, "text": "สวัสดี ลาก่อน",
                 "segments": [{"from": 0.0, "to": 1.2, "text": "สวัสดีครับ"}, {"from": 65.0, "to": 66.0, "text": "ลาก่อน"}]})


def test_detail_shows_speech_and_sound_names(app, tmp_path):
    from PySide6.QtWidgets import QLabel, QPushButton
    w = make_window(tmp_path)
    cid = analyzed_clip(w, tmp_path)
    _speech_and_labels(w, cid)
    w.open_clip(cid)
    texts = " ".join(l.text() for l in w.detail.findChildren(QLabel))
    for need in ("คำพูดในคลิป", "สวัสดีครับ", "ลาก่อน", "เสียงเอฟเฟกต์", "เสียงวูบ (ฟิ้ว) 1", "เสียงพิมพ์ดีด 1"):
        assert need in texts, need
    assert [s["label"] for s in w.detail.timeline.sfx] == ["เสียงวูบ (ฟิ้ว)", "เสียงพิมพ์ดีด"]
    jumps = [b for b in w.detail.findChildren(QPushButton) if b.text() == "1:05"]
    assert jumps
    seeks = []
    w.detail._seek_to = seeks.append
    jumps[0].click()
    assert seeks == [65.0]


def test_speech_note_when_not_installed(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QLabel
    from stylevault import transcribe
    monkeypatch.setattr(transcribe, "ready", lambda: False)
    w = make_window(tmp_path)
    cid = analyzed_clip(w, tmp_path)
    w.open_clip(cid)
    assert any("ดาวน์โหลดตัวถอดคำพูด" in l.text() for l in w.detail.findChildren(QLabel))


def test_tag_click_filters_library(app, tmp_path):
    from PySide6.QtWidgets import QPushButton
    w = make_window(tmp_path)
    cid = analyzed_clip(w, tmp_path)
    other = w.lib.create_clip("tiktok", "o", "viral", "https://y", status="waiting")
    L.write_json(os.path.join(w.lib.clip_dir(cid), "style-card.json"), CARD)
    w.lib.update_meta(cid, status="analyzed")
    w.open_clip(cid)
    tag = [b for b in w.detail.findChildren(QPushButton) if b.text() == "ไวรัล"][0]
    tag.click()
    assert w.stack.currentWidget() is w.library_page and w.library_page.search.text() == "ไวรัล"
    shown = {c.clip_id for c in w.library_page.grid.cards}
    assert shown == {cid} and other not in shown


def test_compare_two_clips(app, tmp_path):
    from PySide6.QtWidgets import QLabel
    w = make_window(tmp_path)
    a = analyzed_clip(w, tmp_path, "a")
    b = analyzed_clip(w, tmp_path, "b")
    _speech_and_labels(w, a)
    L.write_json(os.path.join(w.lib.clip_dir(a), "style-card.json"), CARD)
    w.lib.update_meta(a, status="analyzed", view_count=1_400_000)
    w.library_page.refresh()
    w.open_clip(a)
    w.detail.cmp_btn.click()                                   # from the clip page
    assert w.stack.currentWidget() is w.library_page and not w.library_page.compare_bar.isHidden()
    w.open_clip(a)                                             # same clip again: ignored, still picking
    assert w.stack.currentWidget() is w.library_page
    w.open_clip(b)
    assert w.stack.currentWidget() is w.compare and w.library_page.compare_bar.isHidden()
    texts = " ".join(l.text() for l in w.compare.findChildren(QLabel))
    for need in ("เทียบ 2 คลิป", CARD["name_th"], "รอวิเคราะห์", "1.4M", "จุดตัดภาพ", "2 จุด", "เสียงวูบ (ฟิ้ว) 1", "สวัสดี", "#7A2E8E"):
        assert need in texts, need
    w.compare.open_clip.emit(b)
    assert w.stack.currentWidget() is w.detail and w.detail.clip_id == b
    # cancel works, and a deleted first pick clears the banner
    w.start_compare(b)
    w.library_page.set_compare(None)
    w.open_clip(a)
    assert w.stack.currentWidget() is w.detail


def test_settings_speech_section(app, tmp_path, monkeypatch):
    from stylevault import transcribe
    w = make_window(tmp_path)
    monkeypatch.setattr(transcribe, "find_cli", lambda: ["whisper-cli"])
    monkeypatch.setattr(transcribe, "model_ready", lambda: False)
    w.open_settings()
    sp = w.settings_page
    assert sp.speech_lbl.text() == "ยังไม่ได้ดาวน์โหลด" and not sp.speech_btn.isHidden()
    got = []
    sp.speech_ready.connect(lambda: got.append(1))
    monkeypatch.setattr(transcribe, "download_model", lambda prog, stop: prog(0.5, "กำลังดาวน์โหลด… 1 / 2 MB"))
    monkeypatch.setattr(transcribe, "model_ready", lambda: True)
    sp.speech_btn.click()
    assert wait_until(app, lambda: got, secs=5)
    assert "พร้อมใช้งาน" in sp.speech_lbl.text() and sp.speech_btn.isHidden()


# ---------------------------------------------------------------- v0.5.1: player stays put, volume, grey dots
def test_player_stays_next_to_video_with_long_transcript(app, tmp_path):
    w = make_window(tmp_path)
    cid = analyzed_clip(w, tmp_path)
    _speech_and_labels(w, cid)
    raw = os.path.join(w.lib.clip_dir(cid), "raw")
    L.write_json(os.path.join(raw, "transcript.json"), {"language": "th", "has_speech": True, "text": "x",
                 "segments": [{"from": i * 2.0, "to": i * 2.0 + 2, "text": f"ประโยคที่ {i}"} for i in range(60)]})
    w.resize(1100, 1000)
    w.show()
    w.open_clip(cid)
    for _ in range(5):
        app.processEvents()
    gap = w.detail.play_btn.mapTo(w.detail, w.detail.play_btn.rect().topLeft()).y() - \
        w.detail.video_box.mapTo(w.detail, w.detail.video_box.rect().bottomLeft()).y()
    assert 0 <= gap < 30, gap                                         # controls sit right under the video
    assert w.detail.right_scroll.verticalScrollBar().maximum() > 0     # only the right side scrolls
    assert w.detail.left_scroll.verticalScrollBar().maximum() == 0
    w.hide()


def test_volume_is_remembered_and_mute_works(app, tmp_path):
    w = make_window(tmp_path)
    assert w.detail.vol_slider.value() == 50 and abs(w.detail._gain() - 0.25) < 1e-6
    w.detail.vol_slider.setValue(30)
    assert w.s.volume == 30 and w.detail.vol_lbl.text() == "เสียง 30%"
    w.detail.mute_btn.setChecked(True)
    assert w.detail._gain() == 0.0 and w.detail.mute_btn.text() == "เปิดเสียง"
    w.detail.vol_slider.setValue(40)                                  # moving the slider un-mutes
    assert not w.detail.mute_btn.isChecked() and w.detail._gain() > 0
    w._vol_timer.timeout.emit()
    from stylevault.settings import Settings as S2
    assert S2.load().volume == 40
    w2 = make_window(tmp_path)
    w2.s.volume = 40
    w2.detail.set_volume(w2.s.volume)
    assert w2.detail.vol_slider.value() == 40


def test_speech_and_music_dots_are_grey(app, tmp_path):
    from PySide6.QtWidgets import QLabel
    w = make_window(tmp_path)
    cid = analyzed_clip(w, tmp_path)
    raw = os.path.join(w.lib.clip_dir(cid), "raw")
    a = L.read_json(os.path.join(raw, "audio.json"))
    a["sfx"][0].update(label_th="เสียงพูด")
    a["sfx"][1].update(label_th="เสียงป๊อป")
    L.write_json(os.path.join(raw, "audio.json"), a)
    w.open_clip(cid)
    assert [s["background"] for s in w.detail.timeline.sfx] == [True, False]
    texts = " ".join(l.text() for l in w.detail.findChildren(QLabel))
    assert "เสียงป๊อป 1" in texts and "เสียงพูด 1" in texts and "จุดเทา" in texts
    # Claude's card overrides: a sound it named is an effect even if the model said "speech"
    L.write_json(os.path.join(w.lib.clip_dir(cid), "style-card.json"),
                 make_card(audio={"sfx_th": [{"t": 0.38, "type_th": "เสียงวูบ", "role_th": "x"}]}))
    w.lib.update_meta(cid, status="analyzed")
    w.detail.render()
    assert w.detail.timeline.sfx[0]["background"] is False and w.detail.timeline.sfx[0]["label"] == "เสียงวูบ"
    w.detail.timeline.grab()


def test_settings_offers_the_better_speech_model(app, tmp_path, monkeypatch):
    from stylevault import transcribe
    w = make_window(tmp_path)
    monkeypatch.setattr(transcribe, "find_cli", lambda: ["whisper-cli"])
    monkeypatch.setattr(transcribe, "model_ready", lambda: False)
    monkeypatch.setattr(transcribe, "old_model_present", lambda: True)
    w.open_settings()
    sp = w.settings_page
    assert "รุ่นใหม่" in sp.speech_lbl.text() and sp.speech_btn.text() == "ดาวน์โหลดตัวถอดรุ่นใหม่"
    assert "570 MB" in " ".join(l.text() for l in sp.findChildren(__import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel))
