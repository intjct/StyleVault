"""v0.5.0: sound-effect names (YAMNet), speech to text (whisper), and how they plug into the raw data."""
import json
import os
import shutil
import subprocess
import sys

import pytest

from stylevault import library as L, prepare, sfxlabel, transcribe

HERE = os.path.dirname(os.path.abspath(__file__))
pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


@pytest.fixture
def fake_tools(tmp_path, monkeypatch):
    onnx = pytest.importorskip("onnx")  # noqa: F841
    from make_fake_yamnet import build
    model = build(str(tmp_path / "fake_yamnet.onnx"))
    whisper_model = tmp_path / "ggml-fake.bin"
    whisper_model.write_bytes(b"x")
    monkeypatch.setenv("STYLEVAULT_YAMNET", model)
    monkeypatch.setenv("STYLEVAULT_WHISPER", f"{sys.executable}|{os.path.join(HERE, 'fake_whisper.py')}")
    monkeypatch.setenv("STYLEVAULT_WHISPER_MODEL", str(whisper_model))
    monkeypatch.setattr(sfxlabel, "_session", None)
    monkeypatch.setattr(sfxlabel, "_failed", False)
    return model


def clip_with_sound(tmp_path):
    """3-second video: silence with two sharp clicks, so the program finds sound effects to name."""
    src = str(tmp_path / "src.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=360x640:rate=30:duration=3",
                    "-f", "lavfi", "-i", "aevalsrc='0.9*sin(2*PI*900*t)*(between(t,0.8,0.9)+between(t,2.0,2.1))':s=44100:d=3",
                    "-pix_fmt", "yuv420p", "-shortest", src], check=True)
    lib = L.Library(str(tmp_path / "lib"))
    cid = lib.create_clip("file", "s", "effects", None)
    shutil.copy(src, os.path.join(lib.clip_dir(cid), "video.mp4"))
    lib.update_meta(cid, video_file="video.mp4")
    return lib, cid


def test_thai_names_cover_real_class_names():
    names = set(sfxlabel.class_names())
    assert len(sfxlabel.class_names()) == 521
    assert all(n in names for n in sfxlabel.THAI)
    assert sfxlabel.THAI["Whoosh, swoosh, swish"].startswith("เสียงวูบ")


def test_pick_prefers_the_sound_effect_over_background_music():
    names = sfxlabel.class_names()
    row = [0.0] * 521
    row[names.index("Music")] = 0.6
    row[names.index("Typing")] = 0.2
    assert sfxlabel.pick(row)[1] == "เสียงพิมพ์ดีด"
    row[names.index("Typing")] = 0.01                      # too weak: then it's just music
    assert sfxlabel.pick(row)[1] == "เสียงเพลง"
    row = [0.0] * 521
    row[names.index("Ukulele") if "Ukulele" in names else 5] = 0.5   # not in the Thai table
    assert sfxlabel.pick(row)[1] in ("เสียงอื่นๆ", "เสียงเพลง")


def test_parse_whisper_output_drops_noise():
    d = transcribe.parse({"result": {"language": "th"}, "transcription": [
        {"offsets": {"from": 0, "to": 1200}, "text": " สวัสดี"}, {"offsets": {"from": 1200, "to": 1300}, "text": " [Music]"},
        {"offsets": {"from": 1300, "to": 1400}, "text": " (เพลง) "}, {"offsets": {"from": "x"}, "text": "พัง"},
        {"offsets": {"from": 1400, "to": 2500}, "text": "ลาก่อน"}]})
    assert d["segments"] == [{"from": 0.0, "to": 1.2, "text": "สวัสดี"}, {"from": 1.4, "to": 2.5, "text": "ลาก่อน"}]
    assert d["language"] == "th" and d["has_speech"] and d["text"] == "สวัสดี ลาก่อน"
    assert transcribe.parse({})["has_speech"] is False


def test_prepare_adds_sound_names_and_speech(tmp_path, fake_tools):
    lib, cid = clip_with_sound(tmp_path)
    prepare.prepare(lib, cid, lambda f, t: None)
    raw = os.path.join(lib.clip_dir(cid), "raw")
    audio = json.load(open(os.path.join(raw, "audio.json"), encoding="utf-8"))
    assert audio["sfx"] and audio["labels_version"] == 1
    assert all(s["label_th"] == "เสียงวูบ (ฟิ้ว)" and s["label"] == "Whoosh, swoosh, swish" for s in audio["sfx"])
    tr = json.load(open(os.path.join(raw, "transcript.json"), encoding="utf-8"))
    assert [s["text"] for s in tr["segments"]] == ["สวัสดีครับ วันนี้มาดูเทคนิคตัดต่อ", "กดติดตามด้วยนะ"]
    assert not [f for f in os.listdir(raw) if f.startswith("_")]          # temp files cleaned up
    assert lib.meta(cid)["status"] == "waiting" and lib.meta(cid)["has_speech"] is True
    assert not prepare.needs_extras(lib, cid)


def test_older_clips_get_extras_later_and_failures_are_harmless(tmp_path, fake_tools, monkeypatch):
    lib, cid = clip_with_sound(tmp_path)
    monkeypatch.setenv("STYLEVAULT_YAMNET", str(tmp_path / "missing.onnx"))
    monkeypatch.delenv("STYLEVAULT_WHISPER_MODEL")
    monkeypatch.setattr(transcribe, "models_dir", lambda: str(tmp_path / "nomodels"))
    prepare.prepare(lib, cid, lambda f, t: None)                     # nothing installed: still works
    assert lib.meta(cid)["status"] == "waiting" and not prepare.needs_extras(lib, cid)
    monkeypatch.setenv("STYLEVAULT_YAMNET", fake_tools)               # user installs / updates
    monkeypatch.setenv("STYLEVAULT_WHISPER_MODEL", str(tmp_path / "ggml-fake.bin"))
    assert prepare.needs_extras(lib, cid)
    lib.update_meta(cid, status="analyzed")
    prepare.extras(lib, cid)
    assert not prepare.needs_extras(lib, cid) and lib.meta(cid)["status"] == "analyzed"
    # a broken whisper never breaks the clip
    os.remove(os.path.join(lib.clip_dir(cid), "raw", "transcript.json"))
    monkeypatch.setenv("STYLEVAULT_WHISPER", f"{sys.executable}|-c|import sys; sys.exit(3)")
    prepare.extras(lib, cid)
    assert lib.meta(cid)["status"] == "analyzed"


def test_model_download_is_all_or_nothing(tmp_path, monkeypatch):
    src = tmp_path / "model.bin"
    src.write_bytes(b"m" * 3_000_000)
    monkeypatch.setattr(transcribe, "models_dir", lambda: str(tmp_path / "models"))
    monkeypatch.delenv("STYLEVAULT_WHISPER_MODEL", raising=False)
    monkeypatch.setattr(transcribe, "MODEL_URL", src.as_uri())
    monkeypatch.setattr(transcribe, "MODEL_MIN_BYTES", 2_000_000)
    with pytest.raises(transcribe.TranscribeError):
        transcribe.download_model(lambda f, t: None, should_stop=lambda: True)      # cancelled
    assert not os.listdir(tmp_path / "models") and not transcribe.model_ready()
    seen = []
    transcribe.download_model(lambda f, t: seen.append(f))
    assert transcribe.model_ready() and seen[-1] == 1.0
    monkeypatch.setattr(transcribe, "MODEL_MIN_BYTES", 5_000_000)                  # a short file is refused
    os.remove(transcribe.model_path())
    with pytest.raises(transcribe.TranscribeError):
        transcribe.download_model(lambda f, t: None)
    assert not os.listdir(tmp_path / "models")


@pytest.mark.skipif(not os.path.isfile(os.environ.get("STYLEVAULT_YAMNET", "")), reason="real YAMNet model only on the build machine")
def test_real_yamnet_model(tmp_path, monkeypatch):
    monkeypatch.setattr(sfxlabel, "_session", None)
    wav = str(tmp_path / "beep.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=1000:duration=0.6", wav], check=True)
    res = sfxlabel.label_file(wav)
    assert res and res[0] in sfxlabel.class_names() and 0 <= res[2] <= 1


def test_upgrade_from_the_old_small_model(tmp_path, fake_tools, monkeypatch):
    lib, cid = clip_with_sound(tmp_path)
    prepare.prepare(lib, cid, lambda f, t: None)
    tpath = os.path.join(lib.clip_dir(cid), "raw", "transcript.json")
    assert json.load(open(tpath, encoding="utf-8"))["model"] == transcribe.MODEL_LABEL
    assert not prepare.needs_extras(lib, cid)
    old = json.load(open(tpath, encoding="utf-8"))
    old["model"] = "whisper small"                                    # made by v0.5.0
    json.dump(old, open(tpath, "w", encoding="utf-8"))
    assert prepare.needs_extras(lib, cid)
    prepare.extras(lib, cid)
    assert json.load(open(tpath, encoding="utf-8"))["model"] == transcribe.MODEL_LABEL
    # downloading the new model deletes the old one
    models = tmp_path / "models"
    models.mkdir()
    (models / "ggml-small.bin").write_bytes(b"old")
    src = tmp_path / "new.bin"
    src.write_bytes(b"n" * 3_000_000)
    monkeypatch.setattr(transcribe, "models_dir", lambda: str(models))
    monkeypatch.delenv("STYLEVAULT_WHISPER_MODEL")
    monkeypatch.setattr(transcribe, "MODEL_URL", src.as_uri())
    monkeypatch.setattr(transcribe, "MODEL_MIN_BYTES", 2_000_000)
    assert transcribe.old_model_present() and not transcribe.model_ready()
    transcribe.download_model(lambda f, t: None)
    assert transcribe.model_ready() and not transcribe.old_model_present()
    assert os.listdir(models) == [transcribe.MODEL_NAME]
