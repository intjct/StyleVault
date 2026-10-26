import array
import math
import os
import shutil
import subprocess

import pytest

from stylevault import library as L, prepare

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def make_click_wav(path, secs, beat_times, rate=22050):
    s = array.array("h", [0] * int(secs * rate))
    for bt in beat_times:
        start = int(bt * rate)
        for i in range(int(0.03 * rate)):
            if start + i < len(s):
                s[start + i] = int(20000 * math.sin(2 * math.pi * 1000 * i / rate) * (1 - i / (0.03 * rate)))
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(s.tobytes())


def make_clip(tmp_path, beats=None, secs=8):
    """3 solid-color shots (hard cuts at 2.5 s and 5.0 s) + a click on every beat."""
    out = str(tmp_path / "v.mp4")
    wav = str(tmp_path / "a.wav")
    make_click_wav(wav, secs, beats or [])
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-f", "lavfi", "-i", "color=c=red:s=360x640:r=30:d=2.5",
                    "-f", "lavfi", "-i", "color=c=blue:s=360x640:r=30:d=2.5",
                    "-f", "lavfi", "-i", "color=c=green:s=360x640:r=30:d=" + str(secs - 5),
                    "-i", wav, "-filter_complex", "[0][1][2]concat=n=3:v=1:a=0[v]", "-map", "[v]", "-map", "3:a",
                    "-pix_fmt", "yuv420p", "-shortest", out], check=True)
    return out


def test_cuts_frames_and_contact_sheet(tmp_path):
    v = make_clip(tmp_path)
    cuts = prepare.detect_cuts(v)
    assert len(cuts) == 2 and abs(cuts[0] - 2.5) < 0.1 and abs(cuts[1] - 5.0) < 0.1
    times = prepare.pick_frame_times(cuts, 8.0)
    assert len(times) <= 30 and all(t < 8 for t in times)
    assert any(abs(t - 2.6) < 0.01 for t in times)                          # a frame right after each cut
    curve = prepare.motion_curve(v)
    assert curve[0] == [0.0, 0.0] and max(c[1] for c in curve) > 0.5       # the big color change shows up


def test_frame_cap():
    cuts = [i * 0.5 for i in range(1, 100)]
    assert len(prepare.pick_frame_times(cuts, 60)) == 30


def test_beat_and_onsets(tmp_path):
    beats = [0.25 + 0.5 * i for i in range(15)]                             # 120 beats per minute
    v = make_clip(tmp_path, beats, secs=8)
    db = prepare.energy_db(v)
    on = prepare.find_onsets(db)
    assert len(on) >= 12
    assert all(min(abs(t - b) for b in beats) < 0.08 for t, _ in on)
    bpm = prepare.estimate_bpm(db, len(on), 8.0)
    assert bpm is not None and abs(bpm - 120) <= 4


def test_no_steady_beat_gives_none(tmp_path):
    v = make_clip(tmp_path, [0.3, 1.1, 1.2, 3.9, 6.7], secs=8)
    db = prepare.energy_db(v)
    on = prepare.find_onsets(db)
    assert prepare.estimate_bpm(db, len(on), 8.0) is None


def test_full_prepare_writes_everything(tmp_path):
    beats = [0.25 + 0.5 * i for i in range(15)]
    v = make_clip(tmp_path, beats)
    lib = L.Library(str(tmp_path / "lib"))
    cid = lib.create_clip("file", "x1", "effects", None, status="preparing")
    shutil.copy(v, os.path.join(lib.clip_dir(cid), "video.mp4"))
    seen = []
    prepare.prepare(lib, cid, lambda f, t: seen.append(f))
    raw = os.path.join(lib.clip_dir(cid), "raw")
    cuts = L.read_json(os.path.join(raw, "cuts.json"))
    audio = L.read_json(os.path.join(raw, "audio.json"))
    assert cuts["cut_count"] == 2 and cuts["method"] == "ffmpeg scdet threshold=3" and cuts["avg_shot_sec"] == round(8 / 3, 2)
    assert audio["has_audio"] and audio["bpm"] and abs(audio["bpm"] - 120) <= 4
    assert audio["silences"] and audio["onsets_near_cut"] is not None
    assert 0 < len(audio["sfx"]) <= 40 and all(os.path.isfile(os.path.join(raw, a["file"])) for a in audio["sfx"])
    for name in ("contact-sheet.jpg", "waveform.png"):
        assert os.path.getsize(os.path.join(raw, name)) > 0
    frames = sorted(os.listdir(os.path.join(raw, "frames")))
    assert 2 <= len(frames) <= 30 and frames[0].startswith("0001_")
    m = lib.meta(cid)
    assert m["status"] == "waiting" and m["raw_ready"] is True
    assert seen[-1] == 1.0
    assert not os.path.exists(raw + ".tmp")
    # the library keeps a guide for Claude and an index
    assert "วิเคราะห์คลิปใหม่" in open(os.path.join(lib.root, "CLAUDE-README.md"), encoding="utf-8").read()
    assert L.read_json(os.path.join(lib.root, "library-index.json"))["clips"][0]["status"] == "waiting"


def test_silent_video_has_no_audio_data(tmp_path):
    v = str(tmp_path / "s.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=360x640:rate=30:duration=3",
                    "-pix_fmt", "yuv420p", v], check=True)
    lib = L.Library(str(tmp_path / "lib"))
    cid = lib.create_clip("file", "x2", "viral", None, status="preparing")
    shutil.copy(v, os.path.join(lib.clip_dir(cid), "video.mp4"))
    prepare.prepare(lib, cid, lambda *_: None)
    audio = L.read_json(os.path.join(lib.clip_dir(cid), "raw", "audio.json"))
    assert audio["has_audio"] is False and audio["bpm"] is None and audio["sfx"] == []


def test_prepare_missing_video_is_easy_thai(tmp_path):
    lib = L.Library(str(tmp_path / "lib"))
    cid = lib.create_clip("file", "x3", "viral", None, status="preparing")
    with pytest.raises(prepare.PrepareError) as e:
        prepare.prepare(lib, cid, lambda *_: None)
    assert "ไม่พบไฟล์วิดีโอ" in str(e.value)
