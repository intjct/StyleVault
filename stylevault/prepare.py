"""Raw data for Claude: cut points, still frames, contact sheet, audio facts and short sound-effect clips.

Everything is written to  <clip>/raw/  (cuts.json, audio.json, frames/, contact-sheet.jpg, waveform.png, sfx/).
Every number comes from measuring the video — nothing is guessed."""
from __future__ import annotations

import array
import math
import os
import re
import shutil
import subprocess

from . import VERSION, tools
from .library import Library, write_json

MAX_FRAMES = 30
MAX_SFX = 40
HOP = 0.02            # audio is measured in 20 ms steps


class PrepareError(Exception):
    """message is easy Thai, safe to show on the card."""


def _ff() -> str:
    ff = tools.find_ffmpeg()
    if not ff:
        raise PrepareError("ไม่พบตัวประมวลผลวิดีโอในโปรแกรม — ลองติดตั้งโปรแกรมทับใหม่")
    return ff


def _log(video: str, args: list[str], timeout: int = 600) -> str:
    r = tools.run([_ff(), "-hide_banner", "-nostats", "-i", video, *args, "-f", "null", "-"], timeout=timeout)
    return r.stderr


def _pipe(cmd: list[str], timeout: int = 600) -> bytes:
    r = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=tools.NO_WINDOW)
    return r.stdout


def has_audio(video: str) -> bool:
    fp = tools.find_ffprobe()
    if fp:
        out = tools.run([fp, "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type",
                         "-of", "csv=p=0", video], timeout=60).stdout
        return "audio" in out
    return "Audio:" in tools.run([_ff(), "-hide_banner", "-i", video], timeout=60).stderr


# ------------------------------------------------------------------ video side

def detect_cuts(video: str) -> list[float]:
    """Scene changes with scdet threshold 3 (the threshold the plan found to work on motion-graphic clips)."""
    log = _log(video, ["-an", "-filter:v", "scdet=threshold=3"])
    times = sorted({round(float(m), 2) for m in re.findall(r"lavfi\.scd\.time:\s*([\d.]+)", log)})
    return times


def motion_curve(video: str) -> list[list[float]]:
    """How much the picture changes, every 0.5 s (0 = still, 1 = very different). Shows moving transitions."""
    w, h = 64, 36
    data = _pipe([_ff(), "-v", "error", "-i", video, "-an", "-vf", f"fps=2,scale={w}:{h}:flags=area,format=gray",
                  "-f", "rawvideo", "-"])
    size = w * h
    frames = [data[i:i + size] for i in range(0, len(data) - size + 1, size)]
    curve = [[0.0, 0.0]]
    for i in range(1, len(frames)):
        a, b = frames[i - 1], frames[i]
        diff = sum(abs(x - y) for x, y in zip(a, b)) / size
        curve.append([round(i * 0.5, 1), round(min(1.0, diff / 64), 3)])
    return curve


def pick_frame_times(cuts: list[float], duration: float) -> list[float]:
    step = 1.0 if duration <= 20 else 2.0
    end = duration - 0.05
    times = [round(c + 0.1, 2) for c in cuts if c + 0.1 < end]
    k, t = 0, 0.1
    while t < end:
        if all(abs(t - x) >= 0.3 for x in times):
            times.append(round(t, 2))
        k += 1
        t = 0.1 + k * step
    times.sort()
    if len(times) > MAX_FRAMES:
        times = [times[round(i * (len(times) - 1) / (MAX_FRAMES - 1))] for i in range(MAX_FRAMES)]
    return times


def extract_frames(video: str, times: list[float], folder: str) -> int:
    os.makedirs(folder, exist_ok=True)
    n = 0
    for i, t in enumerate(times, 1):
        out = os.path.join(folder, f"{i:04d}_{t:05.2f}s.jpg")
        tools.run([_ff(), "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                   "-vf", "scale=360:-2", "-q:v", "3", out], timeout=60)
        n += os.path.isfile(out)
    return n


def contact_sheet(video: str, duration: float, out: str) -> None:
    step = max(1, math.ceil(duration / 16))
    tools.run([_ff(), "-y", "-v", "error", "-i", video, "-an", "-vf", f"fps=1/{step},scale=240:-2,tile=4x4",
               "-frames:v", "1", "-q:v", "3", out], timeout=300)


# ------------------------------------------------------------------ audio side

def silences(video: str) -> list[list[float]]:
    log = _log(video, ["-vn", "-af", "silencedetect=noise=-30dB:d=0.15"])
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*(-?[\d.]+)", log)]
    out = []
    for i, s in enumerate(starts):
        out.append([round(max(0.0, s), 2), round(ends[i], 2) if i < len(ends) else None])
    return out


def loudness(video: str) -> float | None:
    log = _log(video, ["-vn", "-af", "ebur128=framelog=quiet"])
    m = re.findall(r"\bI:\s+(-?[\d.]+)\s+LUFS", log)
    return round(float(m[-1]), 1) if m else None


def energy_db(video: str) -> list[float]:
    """Loudness (dB) of every 20 ms of the sound, mono 22 kHz."""
    pcm = _pipe([_ff(), "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", "22050", "-f", "s16le", "-"])
    s = array.array("h")
    s.frombytes(pcm[: len(pcm) // 2 * 2])
    step = int(22050 * HOP)
    out = []
    for i in range(0, len(s) - step + 1, step):
        chunk = s[i:i + step]
        rms = math.sqrt(sum(x * x for x in chunk) / step)
        out.append(20 * math.log10(max(rms, 1.0) / 32768))
    return out


def find_onsets(db: list[float]) -> list[tuple[float, float]]:
    """(time, strength) of sudden loud sounds: >= 9 dB above the last 100 ms, at least 0.12 s apart."""
    cands = []
    for i in range(5, len(db) - 2):
        base = sum(db[i - 5:i]) / 5
        st = db[i] - base
        if st >= 9 and db[i] > -45 and db[i] >= max(db[i - 2:i + 3]):
            cands.append((round(i * HOP, 2), st))
    out: list[tuple[float, float]] = []
    for t, st in cands:
        if out and t - out[-1][0] < 0.12:
            if st > out[-1][1]:
                out[-1] = (t, st)
        else:
            out.append((t, st))
    return out


def estimate_bpm(db: list[float], onsets: int, duration: float) -> int | None:
    """Beats per minute from the rhythm of the sound; None when no steady beat is found (70–180 range)."""
    if duration < 6 or onsets < 8 or len(db) < 200:
        return None
    env = [max(0.0, db[i] - db[i - 1]) for i in range(1, len(db))]
    n = len(env)
    lo, hi = int(60 / (180 * HOP)), int(60 / (70 * HOP))
    r = {}
    for lag in range(lo - 1, hi + 2):
        r[lag] = sum(env[i] * env[i + lag] for i in range(n - lag)) / (n - lag)
    best = max(range(lo, hi + 1), key=lambda l: r[l])
    mean = sum(r[l] for l in range(lo, hi + 1)) / (hi - lo + 1)
    if mean <= 0 or r[best] / mean < 1.6:
        return None
    a, b, c = r[best - 1], r[best], r[best + 1]
    den = a - 2 * b + c
    lag = best + (0.5 * (a - c) / den if den else 0)
    return round(60 / (lag * HOP))


def save_sfx(video: str, onsets: list[tuple[float, float]], folder: str) -> list[dict]:
    top = sorted(sorted(onsets, key=lambda o: -o[1])[:MAX_SFX])
    os.makedirs(folder, exist_ok=True)
    items = []
    for i, (t, _st) in enumerate(top, 1):
        name = f"{i:04d}_{t:05.2f}s.wav"
        tools.run([_ff(), "-y", "-v", "error", "-ss", f"{max(0.0, t - 0.1):.2f}", "-t", "0.6", "-i", video,
                   "-vn", "-ac", "1", "-ar", "22050", os.path.join(folder, name)], timeout=60)
        if os.path.isfile(os.path.join(folder, name)):
            items.append({"t": t, "file": f"sfx/{name}", "label": None, "confidence": None})
    return items


# ------------------------------------------------------------------ everything

def prepare(lib: Library, clip_id: str, progress) -> None:
    """Writes <clip>/raw/. progress(fraction, text). Raises PrepareError."""
    video = lib.video_path(clip_id)
    if not video:
        raise PrepareError("ไม่พบไฟล์วิดีโอของคลิปนี้ — ลบแล้วเพิ่มใหม่")
    meta = lib.meta(clip_id) or {}
    from . import ingest
    info = ingest.probe(video)
    duration = info.get("duration_sec") or meta.get("duration_sec")
    if not duration:
        raise PrepareError("อ่านความยาวคลิปไม่ได้ — ไฟล์อาจเสีย")
    fill = {k: v for k, v in info.items() if v is not None and meta.get(k) is None}
    if fill:                                                   # clips added by v0.1 may lack size / length
        lib.update_meta(clip_id, **fill)
    text = "กำลังเตรียมข้อมูล…"
    final = os.path.join(lib.clip_dir(clip_id), "raw")
    tmp = final + ".tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    try:
        progress(0.05, text)
        cuts = detect_cuts(video)
        progress(0.15, text)
        curve = motion_curve(video)
        write_json(os.path.join(tmp, "cuts.json"), {
            "method": "ffmpeg scdet threshold=3", "cuts_sec": cuts, "cut_count": len(cuts),
            "avg_shot_sec": round(duration / (len(cuts) + 1), 2), "motion_curve": curve})
        progress(0.3, text)
        extract_frames(video, pick_frame_times(cuts, duration), os.path.join(tmp, "frames"))
        progress(0.5, text)
        contact_sheet(video, duration, os.path.join(tmp, "contact-sheet.jpg"))

        audio: dict = {"has_audio": False, "loudness_lufs": None, "silences": [], "onsets_sec": [],
                       "onsets_near_cut": None, "bpm": None, "sfx": []}
        if has_audio(video):
            audio["has_audio"] = True
            progress(0.6, text)
            audio["loudness_lufs"] = loudness(video)
            audio["silences"] = silences(video)
            db = energy_db(video)
            onsets = find_onsets(db)
            audio["onsets_sec"] = [t for t, _ in onsets][:400]
            if onsets and cuts:
                near = sum(1 for t, _ in onsets if any(abs(t - c) <= 0.12 for c in cuts))
                audio["onsets_near_cut"] = round(near / len(onsets), 2)
            audio["bpm"] = estimate_bpm(db, len(onsets), duration)
            progress(0.75, text)
            tools.run([_ff(), "-y", "-v", "error", "-i", video, "-filter_complex", "showwavespic=s=1200x160:colors=0x2F5BFF",
                       "-frames:v", "1", os.path.join(tmp, "waveform.png")], timeout=300)
            audio["sfx"] = save_sfx(video, onsets, os.path.join(tmp, "sfx"))
        write_json(os.path.join(tmp, "audio.json"), audio)
        progress(0.97, text)
        shutil.rmtree(final, ignore_errors=True)
        os.replace(tmp, final)
    except PrepareError:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise PrepareError("เตรียมข้อมูลคลิปไม่สำเร็จ — กดลองใหม่ ถ้ายังไม่หายให้ลบแล้วเพิ่มคลิปใหม่")
    changes = {"raw_ready": True, "raw_version": VERSION, "error": None}
    lib.update_meta(clip_id, **changes)
    extras(lib, clip_id, lambda f, t: progress(0.97 + 0.03 * f, t))    # labels + speech: optional, never fatal
    if (lib.meta(clip_id) or {}).get("status") in ("preparing", "error", "downloading"):
        lib.update_meta(clip_id, status="waiting")
    lib.rebuild_index()
    progress(1.0, "เสร็จแล้ว")


# ------------------------------------------------------------------ extras: sound names + spoken words

def needs_extras(lib: Library, clip_id: str) -> bool:
    """True when this clip could get sound-effect names or a transcript that it does not have yet."""
    from . import sfxlabel, transcribe
    raw = os.path.join(lib.clip_dir(clip_id), "raw")
    audio = _read(os.path.join(raw, "audio.json"))
    if not audio or not audio.get("has_audio"):
        return False
    if sfxlabel.available() and audio.get("sfx") and not audio.get("labels_version"):
        return True
    return transcribe.ready() and not os.path.isfile(os.path.join(raw, "transcript.json"))


def extras(lib: Library, clip_id: str, progress=lambda f, t: None) -> None:
    """Adds names to the sound effects (YAMNet) and the spoken words (whisper). Failures only skip that part."""
    from . import sfxlabel, transcribe
    raw = os.path.join(lib.clip_dir(clip_id), "raw")
    apath = os.path.join(raw, "audio.json")
    audio = _read(apath)
    if not audio or not audio.get("has_audio"):
        return
    if sfxlabel.available() and audio.get("sfx") and not audio.get("labels_version"):
        progress(0.05, "กำลังแยกชนิดเสียงเอฟเฟกต์…")
        try:
            sfxlabel.label_sfx(raw, audio["sfx"])
            audio["labels_version"] = 1
            write_json(apath, audio)
        except Exception:
            pass
    video = lib.video_path(clip_id)
    tpath = os.path.join(raw, "transcript.json")
    if video and transcribe.ready() and not os.path.isfile(tpath):
        progress(0.3, "กำลังถอดคำพูด…")
        try:
            data = transcribe.transcribe(video, tpath, lambda f, t: progress(0.3 + 0.7 * f, t))
            lib.update_meta(clip_id, has_speech=data.get("has_speech"))
        except Exception:
            pass
    progress(1.0, "เสร็จแล้ว")


def _read(path: str):
    import json
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None
