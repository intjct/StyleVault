"""Finds the helper programs shipped with StyleVault (ffmpeg, ffprobe, yt-dlp)."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

IS_WIN = sys.platform == "win32"
NO_WINDOW = 0x08000000 if IS_WIN else 0   # CREATE_NO_WINDOW


def resource_dir() -> str:
    """Folder that holds assets/ and the bundled tools (inside the .exe bundle or the source tree)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _bundled(name: str) -> str | None:
    exe = name + (".exe" if IS_WIN else "")
    for sub in ("ffmpeg", "tools", ""):
        p = os.path.join(resource_dir(), sub, exe)
        if os.path.isfile(p):
            return p
    return None


def find_ffmpeg() -> str | None:
    return _bundled("ffmpeg") or shutil.which("ffmpeg")


def find_ffprobe() -> str | None:
    p = _bundled("ffprobe")
    if p:
        return p
    ff = find_ffmpeg()
    if ff:
        cand = os.path.join(os.path.dirname(ff), "ffprobe" + (".exe" if IS_WIN else ""))
        if os.path.isfile(cand):
            return cand
    return shutil.which("ffprobe")


def user_ytdlp_path() -> str:
    from .settings import config_dir
    return os.path.join(config_dir(), "yt-dlp" + (".exe" if IS_WIN else ""))


def find_ytdlp() -> list[str] | None:
    """Command to run yt-dlp. A copy the user updated (in %APPDATA%) wins over the bundled one."""
    env = os.environ.get("STYLEVAULT_YTDLP")           # used by the tests
    if env:
        return env.split("|")
    u = user_ytdlp_path()
    if os.path.isfile(u):
        return [u]
    b = _bundled("yt-dlp")
    if b:
        return [b]
    w = shutil.which("yt-dlp")
    return [w] if w else None


def run(cmd: list[str], timeout: float | None = None, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, creationflags=NO_WINDOW, **kw)


def update_ytdlp() -> tuple[bool, str]:
    """Copy the bundled yt-dlp to %APPDATA% (so it is writable) and let it update itself."""
    cmd = find_ytdlp()
    if not cmd:
        return False, "ไม่พบตัวโหลดคลิปในโปรแกรม"
    if os.environ.get("STYLEVAULT_YTDLP"):
        return True, "โหมดทดสอบ"
    target = user_ytdlp_path()
    try:
        if not os.path.isfile(target):
            shutil.copy2(cmd[0], target)
        r = run([target, "-U"], timeout=180)
        out = (r.stdout + r.stderr).strip().splitlines()
        text = out[-1] if out else ""
        if r.returncode != 0:
            return False, "อัปเดตไม่สำเร็จ ตรวจสอบอินเทอร์เน็ตแล้วลองใหม่"
        if "up to date" in text.lower():
            return True, "ตัวโหลดคลิปเป็นเวอร์ชันล่าสุดอยู่แล้ว"
        return True, "อัปเดตตัวโหลดคลิปเรียบร้อย"
    except Exception:
        return False, "อัปเดตไม่สำเร็จ ตรวจสอบอินเทอร์เน็ตแล้วลองใหม่"


def ytdlp_version() -> str:
    cmd = find_ytdlp()
    if not cmd:
        return "ไม่พบ"
    try:
        return run(cmd + ["--version"], timeout=30).stdout.strip() or "ไม่ทราบ"
    except Exception:
        return "ไม่ทราบ"
