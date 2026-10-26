"""Bringing a clip into the library: download from a link, or copy a file the user dropped.

The user's own files are only ever COPIED, never changed or moved."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

from . import tools
from .library import Library


class IngestError(Exception):
    """message is already easy Thai, safe to show on the card."""


def friendly_error(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("login", "log in", "sign in", "cookies", "private", "authentication",
                            "rate-limit reached or login required", "age-restricted", "confirm your age")):
        return "คลิปนี้ต้องล็อกอินก่อน — เปิดตัวเลือก \"ใช้การล็อกอินจากเบราว์เซอร์\" ในหน้าตั้งค่า แล้วกดลองใหม่"
    if "unsupported url" in t:
        return "ลิงก์นี้โปรแกรมยังอ่านไม่ได้ — ลองลิงก์ของคลิปโดยตรง หรือโหลดคลิปเองแล้วลากไฟล์มาวาง"
    if "429" in t or "too many requests" in t:
        return "แพลตฟอร์มกันชั่วคราวเพราะโหลดถี่เกินไป — รอสักพักแล้วกดลองใหม่"
    if any(k in t for k in ("getaddrinfo", "network", "timed out", "connection", "urlopen error", "name resolution")):
        return "เชื่อมต่ออินเทอร์เน็ตไม่ได้ — ตรวจสอบเน็ตแล้วกดลองใหม่"
    if "video unavailable" in t or "404" in t or "not found" in t or "removed" in t:
        return "ไม่พบคลิปนี้ อาจถูกลบหรือปิดการมองเห็นแล้ว"
    if "ffmpeg" in t and "not found" in t:
        return "ไม่พบตัวประมวลผลวิดีโอในโปรแกรม — ลองติดตั้งโปรแกรมทับใหม่"
    return "โหลดคลิปไม่สำเร็จ — ลองกด \"อัปเดตตัวโหลดคลิป\" ในหน้าตั้งค่า แล้วกดลองใหม่"


def _cookie_args(settings) -> list[str]:
    if getattr(settings, "use_browser_login", False):
        return ["--cookies-from-browser", "edge" if settings.browser == "edge" else "chrome"]
    return []


def fetch_info(url: str, settings) -> dict:
    cmd = tools.find_ytdlp()
    if not cmd:
        raise IngestError("ไม่พบตัวโหลดคลิปในโปรแกรม — ลองติดตั้งโปรแกรมทับใหม่")
    r = tools.run(cmd + ["-J", "--no-playlist", "--no-warnings"] + _cookie_args(settings) + [url], timeout=120)
    if r.returncode != 0:
        raise IngestError(friendly_error(r.stderr or r.stdout))
    try:
        return json.loads(r.stdout)
    except Exception:
        raise IngestError(friendly_error(r.stderr))


def download(lib: Library, clip_id: str, url: str, settings, progress) -> None:
    """progress(fraction 0..1, text). Raises IngestError."""
    progress(0.02, "กำลังอ่านข้อมูลคลิป…")
    info = fetch_info(url, settings)
    up = info.get("upload_date")
    if isinstance(up, str) and re.fullmatch(r"\d{8}", up):
        up = f"{up[:4]}-{up[4:6]}-{up[6:]}"
    lib.update_meta(
        clip_id,
        title=info.get("title") or info.get("description") or "",
        uploader=info.get("uploader") or info.get("channel") or info.get("uploader_id"),
        upload_date=up if isinstance(up, str) else None,
        view_count=info.get("view_count"), like_count=info.get("like_count"),
        duration_sec=info.get("duration"),
    )
    lib.rebuild_index()

    out_dir = lib.clip_dir(clip_id)
    for f in os.listdir(out_dir):                       # clean leftovers of a failed try
        if f.startswith("video."):
            try:
                os.remove(os.path.join(out_dir, f))
            except OSError:
                pass
    cmd = tools.find_ytdlp() + [
        "--no-playlist", "--no-warnings", "--newline", "--no-part",
        "-S", "vcodec:h264,res:1080,acodec:aac", "-f", "bv*+ba/b",
        "--merge-output-format", "mp4",
        "-o", os.path.join(out_dir, "video.%(ext)s"),
    ]
    ff = tools.find_ffmpeg()
    if ff:
        cmd += ["--ffmpeg-location", ff]
    cmd += _cookie_args(settings) + [url]
    progress(0.05, "กำลังโหลดคลิป…")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace", creationflags=tools.NO_WINDOW)
    tail: list[str] = []
    for line in p.stdout:                                # type: ignore[union-attr]
        tail = (tail + [line.strip()])[-12:]
        m = re.search(r"\[download\]\s+([\d.]+)%", line)
        if m:
            progress(0.05 + 0.85 * float(m.group(1)) / 100, "กำลังโหลดคลิป…")
    p.wait()
    video = _find_video(out_dir)
    if p.returncode != 0 or not video:
        raise IngestError(friendly_error("\n".join(tail)))
    finish(lib, clip_id, video, progress)


def add_file(lib: Library, clip_id: str, src: str, progress) -> None:
    ext = os.path.splitext(src)[1].lower() or ".mp4"
    dest = os.path.join(lib.clip_dir(clip_id), "video" + ext)
    progress(0.1, "กำลังคัดลอกไฟล์เข้าคลัง…")
    try:
        shutil.copy2(src, dest)                         # copy only — the original is never touched
    except OSError:
        raise IngestError("คัดลอกไฟล์ไม่ได้ — ตรวจสอบว่ามีที่ว่างพอและไฟล์ไม่ได้เปิดค้างอยู่")
    lib.update_meta(clip_id, title=os.path.splitext(os.path.basename(src))[0], video_file="video" + ext)
    finish(lib, clip_id, dest, progress)


def _find_video(folder: str) -> str | None:
    for f in sorted(os.listdir(folder)):
        if f.startswith("video.") and not f.endswith((".part", ".ytdl", ".tmp")):
            return os.path.join(folder, f)
    return None


def probe(path: str) -> dict:
    fp = tools.find_ffprobe()
    if not fp:
        return {}
    try:
        r = tools.run([fp, "-v", "error", "-print_format", "json", "-show_entries",
                       "format=duration:stream=codec_type,width,height,r_frame_rate", path], timeout=60)
        data = json.loads(r.stdout)
    except Exception:
        return {}
    out: dict = {}
    try:
        out["duration_sec"] = round(float(data["format"]["duration"]), 2)
    except Exception:
        pass
    for s in data.get("streams", []):
        if s.get("codec_type") == "video":
            out["width"], out["height"] = s.get("width"), s.get("height")
            try:
                a, b = s["r_frame_rate"].split("/")
                out["fps"] = round(float(a) / float(b), 2) if float(b) else None
            except Exception:
                pass
            break
    return out


def make_thumb(video: str, thumb: str, duration: float | None) -> bool:
    ff = tools.find_ffmpeg()
    if not ff:
        return False
    for t in (min(0.5, (duration or 1) / 3), 0):
        try:
            tools.run([ff, "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                       "-vf", "scale=480:-2", "-q:v", "3", thumb], timeout=60)
        except Exception:
            continue
        if os.path.isfile(thumb) and os.path.getsize(thumb) > 0:
            return True
    return False


def finish(lib: Library, clip_id: str, video: str, progress) -> None:
    progress(0.9, "กำลังทำภาพปก…")
    info = probe(video)
    meta = lib.meta(clip_id) or {}
    dur = info.get("duration_sec") or meta.get("duration_sec")
    make_thumb(video, os.path.join(lib.clip_dir(clip_id), "thumb.jpg"), dur)
    changes = {k: v for k, v in info.items() if v is not None}
    lib.update_meta(clip_id, video_file=os.path.basename(video), status="preparing", error=None, **changes)
    lib.rebuild_index()
    from . import prepare
    try:
        prepare.prepare(lib, clip_id, lambda f, t: progress(0.9 + 0.1 * f, t))   # raw data for Claude; sets status to "waiting"
    except prepare.PrepareError as e:
        raise IngestError(str(e))
