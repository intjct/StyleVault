"""`StyleVault.exe --selftest` — proves the finished program really works on Windows.

Checks: Qt starts, Prompt font loads, ffmpeg/ffprobe/yt-dlp are found and run, a generated video
is added to a temporary library (copy, thumbnail, info, index), and the original file is untouched.
Writes a report to %TEMP%\\stylevault-selftest.txt and exits 0 on success."""
from __future__ import annotations

import hashlib
import os
import tempfile
import traceback


def selftest() -> int:
    lines: list[str] = []
    ok = True
    out_file = os.path.join(tempfile.gettempdir(), "stylevault-selftest.txt")

    def check(name, fn):
        nonlocal ok
        try:
            lines.append(f"PASS  {name}  {fn() or ''}")
        except Exception as e:
            ok = False
            lines.append(f"FAIL  {name}  {e}\n{traceback.format_exc()}")

    from . import VERSION, ingest, tools
    from . import library as L

    d = tempfile.mkdtemp(prefix="stylevault-selftest-")
    lines.append(f"StyleVault {VERSION} selftest in {d}")

    def qt_and_font():
        from PySide6.QtGui import QFontDatabase
        from PySide6.QtWidgets import QApplication
        from .ui import theme
        app = QApplication.instance() or QApplication([])
        theme.load_fonts()
        fams = QFontDatabase.families()
        if "Prompt" not in fams:
            raise RuntimeError("Prompt font did not load")
        from PySide6.QtMultimedia import QMediaPlayer  # noqa: F401  (video playback support is bundled)
        return "Qt + Prompt + QtMultimedia"

    def tool_versions():
        ff, fp, yd = tools.find_ffmpeg(), tools.find_ffprobe(), tools.find_ytdlp()
        if not (ff and fp and yd):
            raise RuntimeError(f"missing tool: ffmpeg={ff} ffprobe={fp} yt-dlp={yd}")
        v = tools.run([ff, "-hide_banner", "-version"], timeout=60).stdout.splitlines()[0]
        return f"{v} | yt-dlp {tools.ytdlp_version()}"

    src = os.path.join(d, "original.mp4")

    def make_video():
        r = tools.run([tools.find_ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=360x640:rate=30:duration=2",
                       "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-pix_fmt", "yuv420p", "-shortest", src], timeout=120)
        if not os.path.isfile(src):
            raise RuntimeError(r.stderr)
        return f"{os.path.getsize(src)} bytes"

    before = {}

    def add_file():
        before["h"] = hashlib.sha1(open(src, "rb").read()).hexdigest()
        lib = L.Library(os.path.join(d, "lib"))
        cid = lib.create_clip("file", L.file_short_id(src), "effects", None, title="original")
        ingest.add_file(lib, cid, src, lambda *_: None)
        m = lib.meta(cid)
        if m["status"] != "waiting" or not lib.thumb_path(cid) or not lib.video_path(cid):
            raise RuntimeError(f"bad result: {m}")
        if not (1.5 < (m.get("duration_sec") or 0) < 2.5 and m.get("width") == 360):
            raise RuntimeError(f"bad video info: {m}")
        lib.rebuild_index()
        if not os.path.isfile(os.path.join(lib.root, "library-index.json")):
            raise RuntimeError("no library-index.json")
        raw = os.path.join(lib.clip_dir(cid), "raw")
        for need in ("cuts.json", "audio.json", "contact-sheet.jpg", "waveform.png"):
            if not os.path.isfile(os.path.join(raw, need)):
                raise RuntimeError(f"raw/{need} missing")
        if not os.listdir(os.path.join(raw, "frames")) or not m.get("raw_ready"):
            raise RuntimeError("no frames / raw not ready")
        if not os.path.isfile(os.path.join(lib.root, "CLAUDE-README.md")):
            raise RuntimeError("no CLAUDE-README.md")
        return f"{cid} {m['duration_sec']}s {m['width']}x{m['height']}"

    def original_untouched():
        if hashlib.sha1(open(src, "rb").read()).hexdigest() != before["h"]:
            raise RuntimeError("original file was changed!")

    def sound_names():
        from . import sfxlabel
        if not sfxlabel.available():
            raise RuntimeError(f"YAMNet not available (model at {sfxlabel.model_path()})")
        if len(sfxlabel.class_names()) != 521:
            raise RuntimeError("class map broken")
        beep = os.path.join(d, "beep.wav")
        tools.run([tools.find_ffmpeg(), "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=1000:duration=0.6",
                   "-ac", "1", "-ar", "22050", beep], timeout=60)
        res = sfxlabel.label_file(beep)
        if not res:
            raise RuntimeError("no label")
        return f"beep -> {res}"

    def speech_program():
        from . import transcribe
        cli = transcribe.find_cli()
        if not cli:
            raise RuntimeError("whisper-cli not bundled")
        r = tools.run(cli + ["-h"], timeout=60, cwd=os.path.dirname(cli[-1]))
        if "usage" not in (r.stdout + r.stderr).lower():
            raise RuntimeError(f"whisper-cli did not run: code {r.returncode} {r.stderr[-300:]}")
        model = os.environ.get("STYLEVAULT_TEST_WHISPER_MODEL")
        if not model:
            return f"{cli[-1]} runs (no model given, transcription not tried)"
        os.environ["STYLEVAULT_WHISPER_MODEL"] = model
        out = os.path.join(d, "transcript.json")
        data = transcribe.transcribe(src, out)
        if not os.path.isfile(out):
            raise RuntimeError("no transcript.json")
        return f"transcribed: language={data.get('language')} segments={len(data.get('segments') or [])}"

    check("Qt, font, video playback", qt_and_font)
    check("ffmpeg / ffprobe / yt-dlp", tool_versions)
    check("make test video", make_video)
    check("add a video file to the library", add_file)
    check("original file untouched", original_untouched)
    check("sound-effect names (YAMNet)", sound_names)
    check("speech to text (whisper)", speech_program)

    lines.append("RESULT: " + ("ALL PASSED" if ok else "FAILED"))
    try:
        with open(out_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except OSError:
        pass
    return 0 if ok else 1
