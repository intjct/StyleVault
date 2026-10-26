"""In-program updates: look at the GitHub Releases page, download the installer, run it quietly, reopen.

Nothing happens by itself except a quiet check at start-up. The user must press "อัปเดตเลย"."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

from . import VERSION, tools

REPO = "intjct/StyleVault"            # public repo: installers are published on its Releases page
API = f"https://api.github.com/repos/{REPO}/releases/latest"
UA = f"StyleVault/{VERSION}"


class UpdateError(Exception):
    """message is easy Thai, safe to show."""


def parse_version(text: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", text or "")
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - len(nums[:3])) if nums else (0, 0, 0)


def is_newer(remote: str, local: str = VERSION) -> bool:
    return parse_version(remote) > parse_version(local)


def api_url() -> str:
    return os.environ.get("STYLEVAULT_UPDATE_API") or API      # the tests point this at a fake server


def _get(url: str, timeout: float = 10):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)


def check() -> dict | None:
    """Returns {"version", "url", "size", "notes"} when a newer installer exists, else None.
    Raises UpdateError when the check itself fails (no internet, GitHub busy...)."""
    try:
        with _get(api_url()) as r:
            data = json.load(r)
    except Exception:
        raise UpdateError("เช็กเวอร์ชันใหม่ไม่ได้ — ตรวจสอบอินเทอร์เน็ตแล้วลองใหม่")
    tag = str(data.get("tag_name") or "")
    if not tag or not is_newer(tag):
        return None
    for a in data.get("assets") or []:
        name = str(a.get("name") or "")
        if re.fullmatch(r"StyleVault-Setup-[\d.]+\.exe", name) and a.get("browser_download_url"):
            return {"version": ".".join(str(n) for n in parse_version(tag)), "url": a["browser_download_url"],
                    "size": int(a.get("size") or 0), "notes": data.get("body") or ""}
    return None


def download(info: dict, progress) -> str:
    """Saves the installer in %TEMP% and returns its path. progress(fraction)."""
    folder = os.path.join(tempfile.gettempdir(), "StyleVault-update")
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, f"StyleVault-Setup-{info['version']}.exe")
    tmp = dest + ".part"
    try:
        with _get(info["url"], timeout=30) as r, open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length") or info.get("size") or 0)
            got = 0
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if total:
                    progress(min(0.99, got / total))
        expected = info.get("size") or 0
        if expected and os.path.getsize(tmp) != expected:
            raise UpdateError("ตัวอัปเดตที่โหลดมาไม่ครบ — ลองใหม่อีกครั้ง")
        os.replace(tmp, dest)
    except UpdateError:
        _rm(tmp)
        raise
    except Exception:
        _rm(tmp)
        raise UpdateError("โหลดตัวอัปเดตไม่สำเร็จ — ตรวจสอบอินเทอร์เน็ตแล้วลองใหม่")
    progress(1.0)
    return dest


def _rm(p: str) -> None:
    try:
        os.remove(p)
    except OSError:
        pass


def can_install() -> bool:
    """Only the finished Windows program installs itself (never when running from source)."""
    return bool(getattr(sys, "frozen", False)) and tools.IS_WIN


def install_command(installer: str) -> list[str]:
    # quiet install over the old version, then the installer reopens StyleVault (see installer/stylevault.iss)
    return [installer, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/RELAUNCH=1"]


def run_installer(installer: str) -> None:
    """Starts the installer on its own so it survives this program closing."""
    flags = 0x00000008 | 0x00000200 if tools.IS_WIN else 0      # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(install_command(installer), close_fds=True, creationflags=flags)
