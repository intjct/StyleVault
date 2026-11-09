"""Speech -> text with whisper.cpp, entirely on this computer.

The program (whisper-cli) ships inside StyleVault; the language model (~870 MB) is downloaded once,
only when the user presses the button in Settings.

Since v0.7.0 the model is Typhoon Whisper Turbo (SCB 10X, MIT licence): Whisper large-v3-turbo fine-tuned for Thai,
which makes clearly fewer Thai spelling mistakes than the plain Whisper model. The weights are the official
typhoon-ai checkpoint converted to whisper.cpp format (q8_0, nearly identical to full precision) by a third party."""
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.request

from . import tools

# Typhoon Whisper Turbo (Thai fine-tune of large-v3-turbo), q8_0 = near-lossless 8-bit
MODEL_NAME = "ggml-typhoon-whisper-turbo-q8_0.bin"
MODEL_URL = "https://huggingface.co/JoaoZaokk/typhoon-whisper-turbo-ggml/resolve/main/ggml-typhoon-whisper-turbo-q8_0.bin"
MODEL_MIN_BYTES = 800_000_000          # the real file is ~874 MB; anything smaller is a broken download
MODEL_SIZE_TH = "ประมาณ 870 MB"
MODEL_LABEL = "typhoon-whisper-turbo"
# earlier, less accurate models — removed after the upgrade (v0.5.0 "small", v0.5.2 plain large-v3-turbo)
OLD_MODELS = ("ggml-small.bin", "ggml-large-v3-turbo-q5_0.bin")


class TranscribeError(Exception):
    """Message is easy Thai."""


def models_dir() -> str:
    from .settings import config_dir
    return os.path.join(config_dir(), "models")


def model_path() -> str:
    return os.environ.get("STYLEVAULT_WHISPER_MODEL") or os.path.join(models_dir(), MODEL_NAME)


def old_model_present() -> bool:
    return any(os.path.isfile(os.path.join(models_dir(), n)) for n in OLD_MODELS)


def needs_redo(transcript: dict | None) -> bool:
    """A transcript made by the older, weaker model is redone once the better model is installed."""
    return not isinstance(transcript, dict) or transcript.get("model") != MODEL_LABEL


def model_ready() -> bool:
    p = model_path()
    if not os.path.isfile(p):
        return False
    if os.environ.get("STYLEVAULT_WHISPER_MODEL"):
        return True
    return os.path.getsize(p) >= MODEL_MIN_BYTES


def find_cli() -> list[str] | None:
    env = os.environ.get("STYLEVAULT_WHISPER")             # tests: "python|fake_whisper.py"
    if env:
        return env.split("|")
    exe = "whisper-cli" + (".exe" if tools.IS_WIN else "")
    root = os.path.join(tools.resource_dir(), "tools", "whisper")
    for base, _dirs, files in os.walk(root):
        if exe in files:
            return [os.path.join(base, exe)]
    return None


def ready() -> bool:
    return bool(find_cli()) and model_ready()


def download_model(progress, should_stop=lambda: False) -> None:
    """progress(fraction, text). Downloads to a .part file first so a half download never counts as installed."""
    os.makedirs(models_dir(), exist_ok=True)
    final = os.path.join(models_dir(), MODEL_NAME)
    part = final + ".part"
    try:
        req = urllib.request.Request(MODEL_URL, headers={"User-Agent": "StyleVault"})
        with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0) or 874_000_000
            got = 0
            while True:
                if should_stop():
                    raise TranscribeError("ยกเลิกการดาวน์โหลดแล้ว")
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                progress(min(0.99, got / total), f"กำลังดาวน์โหลด… {got // 1_000_000} / {total // 1_000_000} MB")
    except TranscribeError:
        _rm(part)
        raise
    except OSError:
        _rm(part)
        raise TranscribeError("ดาวน์โหลดไม่สำเร็จ — ตรวจสอบอินเทอร์เน็ตและพื้นที่ว่างในเครื่อง แล้วกดใหม่อีกครั้ง")
    if os.path.getsize(part) < MODEL_MIN_BYTES:
        _rm(part)
        raise TranscribeError("ไฟล์ที่ได้ไม่ครบ — กดดาวน์โหลดใหม่อีกครั้ง")
    os.replace(part, final)
    for n in OLD_MODELS:                                   # free the disk space of the old model
        _rm(os.path.join(models_dir(), n))
    progress(1.0, "ดาวน์โหลดเสร็จแล้ว")


def _rm(p: str) -> None:
    try:
        os.remove(p)
    except OSError:
        pass


_NOISE = re.compile(r"^[\s\[\(（【♪*-]*(music|เพลง|ดนตรี|เสียงเพลง|applause|laughter|silence|blank_audio|เสียงหัวเราะ)?[\s\]\)）】♪*.-]*$",
                    re.IGNORECASE)


PAUSE_MIN_SEC = 0.35        # a gap between two spoken lines at least this long counts as a pause


def speech_stats(segs: list[dict], lang: str | None = None) -> dict | None:
    """Measured speaking rhythm. Thai has no spaces between words, so speed is counted in characters per second.
    Whisper cuts lines by itself, so `pauses` are the gaps between its lines — good enough to copy a rhythm."""
    if not segs:
        return None
    chars = sum(len(re.sub(r"\s+", "", x["text"])) for x in segs)
    spoken = sum(max(0.0, x["to"] - x["from"]) for x in segs)
    pauses = []
    for a, b in zip(segs, segs[1:]):
        gap = b["from"] - a["to"]
        if gap >= PAUSE_MIN_SEC:
            pauses.append({"t": round(a["to"], 2), "sec": round(gap, 2)})
    first, last = segs[0]["from"], segs[-1]["to"]
    out = {
        "chars": chars,
        "speech_sec": round(spoken, 2),
        "first_word_at": round(first, 2),
        "last_word_at": round(last, 2),
        "chars_per_sec": round(chars / spoken, 2) if spoken > 0 else None,
        "line_count": len(segs),
        "avg_line_chars": round(chars / len(segs), 1),
        "avg_line_sec": round(spoken / len(segs), 2),
        "pause_count": len(pauses),
        "avg_pause_sec": round(sum(p["sec"] for p in pauses) / len(pauses), 2) if pauses else None,
        "pauses": pauses[:60],
    }
    if lang and lang != "th":                 # languages with spaces between words also get words per second
        words = sum(len(x["text"].split()) for x in segs)
        out["words"] = words
        out["words_per_sec"] = round(words / spoken, 2) if spoken > 0 else None
    return out


def parse(raw: dict) -> dict:
    """whisper.cpp -oj output -> our transcript.json shape."""
    segs = []
    for s in raw.get("transcription") or []:
        text = (s.get("text") or "").strip()
        off = s.get("offsets") or {}
        if not text or _NOISE.match(text):
            continue
        try:
            a, b = float(off.get("from", 0)) / 1000, float(off.get("to", 0)) / 1000
        except (TypeError, ValueError):
            continue
        segs.append({"from": round(a, 2), "to": round(b, 2), "text": text})
    lang = (raw.get("result") or {}).get("language")
    return {"language": lang, "model": MODEL_LABEL, "segments": segs,
            "text": " ".join(s["text"] for s in segs), "has_speech": bool(segs), "stats": speech_stats(segs, lang)}


def transcribe(video: str, out_json: str, progress=lambda f, t: None) -> dict:
    """Writes out_json (raw/transcript.json). Raises TranscribeError."""
    cli = find_cli()
    if not cli or not model_ready():
        raise TranscribeError("ยังไม่ได้ดาวน์โหลดตัวถอดคำพูด — กดดาวน์โหลดได้ในหน้าตั้งค่า")
    folder = os.path.dirname(out_json)
    wav = os.path.join(folder, "_speech16k.wav")
    base = os.path.join(folder, "_whisper")
    ff = tools.find_ffmpeg() or "ffmpeg"
    try:
        r = tools.run([ff, "-y", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wav],
                      timeout=600)
        if r.returncode != 0 or not os.path.isfile(wav):
            raise TranscribeError("แยกเสียงจากคลิปไม่ได้")
        progress(0.1, "กำลังถอดคำพูด…")
        threads = str(max(1, min(8, (os.cpu_count() or 2) - 1)))
        cmd = cli + ["-m", model_path(), "-f", wav, "-l", "auto", "-oj", "-of", base, "-np", "-t", threads]
        cwd = os.path.dirname(cli[-1]) if len(cli) == 1 else None      # its DLLs sit next to it
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=3600, creationflags=tools.NO_WINDOW, cwd=cwd)
        if p.returncode != 0 or not os.path.isfile(base + ".json"):
            raise TranscribeError("ถอดคำพูดไม่สำเร็จ")
        with open(base + ".json", encoding="utf-8", errors="replace") as f:
            data = parse(json.load(f))
    except subprocess.TimeoutExpired:
        raise TranscribeError("ถอดคำพูดนานเกินไป — ข้ามคลิปนี้ไปก่อน")
    except (OSError, ValueError):
        raise TranscribeError("ถอดคำพูดไม่สำเร็จ")
    finally:
        for f in (wav, base + ".json"):
            _rm(f)
    tmp = out_json + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, out_json)
    progress(1.0, "ถอดคำพูดเสร็จแล้ว")
    return data
