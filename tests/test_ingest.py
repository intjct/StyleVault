import hashlib
import os
import shutil
import subprocess
import sys

import pytest

from stylevault import ingest, library as L
from stylevault.settings import Settings

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
HERE = os.path.dirname(os.path.abspath(__file__))


def make_video(path, secs=2):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=size=360x640:rate=30:duration={secs}",
                    "-pix_fmt", "yuv420p", path], check=True)


def test_add_file_copies_and_never_touches_original(tmp_path):
    src = tmp_path / "mine.mp4"
    make_video(str(src))
    before = hashlib.sha1(src.read_bytes()).hexdigest()
    lib = L.Library(str(tmp_path / "lib"))
    cid = lib.create_clip("file", L.file_short_id(str(src)), "effects", None)
    ingest.add_file(lib, cid, str(src), lambda *_: None)
    m = lib.meta(cid)
    assert m["status"] == "waiting" and m["width"] == 360 and 1.5 < m["duration_sec"] < 2.5
    assert lib.thumb_path(cid) and lib.video_path(cid) != str(src)
    assert hashlib.sha1(src.read_bytes()).hexdigest() == before and src.exists()


def test_download_flow_with_fake_ytdlp(tmp_path, monkeypatch):
    monkeypatch.setenv("STYLEVAULT_YTDLP", f"{sys.executable}|{os.path.join(HERE, 'fake_ytdlp.py')}")
    lib = L.Library(str(tmp_path / "lib"))
    cid = lib.create_clip("tiktok", "7412345", "viral", "https://www.tiktok.com/@x/video/7412345")
    seen = []
    ingest.download(lib, cid, "https://www.tiktok.com/@x/video/7412345", Settings(), lambda f, t: seen.append(f))
    m = lib.meta(cid)
    assert m["status"] == "waiting" and m["view_count"] == 1400000 and m["uploader"] == "@tester"
    assert m["upload_date"] == "2026-09-21" and m["like_count"] == 220000
    assert lib.video_path(cid) and lib.thumb_path(cid)
    assert seen[-1] == 1.0 and seen == sorted(seen)


def test_download_failure_gives_easy_thai(tmp_path, monkeypatch):
    monkeypatch.setenv("STYLEVAULT_YTDLP", f"{sys.executable}|{os.path.join(HERE, 'fake_ytdlp.py')}")
    lib = L.Library(str(tmp_path / "lib"))
    cid = lib.create_clip("tiktok", "1", "viral", "https://x/FAIL")
    with pytest.raises(ingest.IngestError) as e:
        ingest.download(lib, cid, "https://x/FAIL", Settings(), lambda *_: None)
    assert "ล็อกอิน" in str(e.value)


def test_error_messages_have_no_technical_words():
    for raw in ("Unsupported URL: x", "HTTP Error 429", "getaddrinfo failed", "Video unavailable", "weird"):
        msg = ingest.friendly_error(raw)
        assert msg and not any(w in msg for w in ("yt-dlp", "HTTP", "Traceback", "ffmpeg"))


def test_unreadable_browser_login_falls_back_to_guest(tmp_path, monkeypatch):
    monkeypatch.setenv("STYLEVAULT_YTDLP", f"{sys.executable}|{os.path.join(HERE, 'fake_ytdlp.py')}")
    st = Settings(library_dir=str(tmp_path / "lib"), use_browser_login=True, browser="chrome")
    lib = L.Library(str(tmp_path / "lib"))
    cid = lib.create_clip("facebook", "9", "effects", "https://www.facebook.com/reel/COOKIEBAD")
    ingest.download(lib, cid, "https://www.facebook.com/reel/COOKIEBAD", st, lambda f, t: None)
    assert lib.meta(cid)["status"] == "waiting" and lib.video_path(cid)


def test_cookie_problem_message_and_detail():
    msg = ingest.friendly_error("ERROR: Could not copy Chrome cookie database.")
    assert "ปิดเบราว์เซอร์" in msg and "cookie" not in msg.lower()
    e = ingest.IngestError("x", "abc" * 500)
    assert len(e.detail) <= 600
