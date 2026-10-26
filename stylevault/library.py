"""The library folder: one folder per clip, plus library-index.json for Claude.

Layout (see plans/style-library-plan.md):
  <library>/library-index.json
  <library>/clips/<date>_<platform>_<id>/{video.mp4, thumb.jpg, meta.json, notes.md, style-card.json (Claude)}
StyleVault never writes style-card.json — that file belongs to Claude."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import threading
from datetime import datetime, timezone
from urllib.parse import urlparse

from . import VERSION

PLATFORMS = {
    "tiktok": ("TikTok", ("tiktok.com",)),
    "youtube": ("YouTube", ("youtube.com", "youtu.be")),
    "instagram": ("Instagram", ("instagram.com",)),
    "facebook": ("Facebook", ("facebook.com", "fb.watch", "fb.com")),
}
PLATFORM_LABEL = {k: v[0] for k, v in PLATFORMS.items()} | {"file": "ไฟล์", "other": "อื่นๆ"}
KIND_LABEL = {"effects": "สไตล์เอฟเฟกต์", "viral": "คลิปไวรัล"}
VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")

_lock = threading.RLock()


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def looks_like_url(text: str) -> bool:
    t = text.strip()
    if " " in t or "\n" in t:
        return False
    if not re.match(r"^https?://", t, re.I):
        t = "https://" + t
    p = urlparse(t)
    return bool(p.netloc and "." in p.netloc)


def normalize_url(text: str) -> str:
    t = text.strip()
    return t if re.match(r"^https?://", t, re.I) else "https://" + t


def platform_of(url: str) -> str | None:
    host = (urlparse(normalize_url(url)).hostname or "").lower()
    for key, (_label, domains) in PLATFORMS.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return key
    return None


def short_id_of(url: str, platform: str) -> str:
    """A steady id taken from the link, so adding the same link twice is noticed."""
    u = normalize_url(url)
    pats = {
        "tiktok": r"/video/(\d+)",
        "youtube": r"(?:/shorts/|/live/|[?&]v=|youtu\.be/)([\w-]{6,})",
        "instagram": r"/(?:reels?|p|tv)/([\w-]+)",
        "facebook": r"(?:/reel/|/videos?/|[?&]v=)(\d+)",
    }
    m = re.search(pats.get(platform, "$^"), u)
    if m:
        return m.group(1)
    return hashlib.sha1(u.encode()).hexdigest()[:8]


def file_short_id(path: str) -> str:
    st = os.stat(path)
    return hashlib.sha1(f"{os.path.abspath(path)}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()[:8]


def safe_part(s: str) -> str:
    return re.sub(r"[^\w\-]", "", s)[:40] or "x"


def read_json(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def write_json(path: str, data) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class Library:
    def __init__(self, root: str):
        self.root = root
        self.clips_dir = os.path.join(root, "clips")
        os.makedirs(self.clips_dir, exist_ok=True)

    # ---- paths
    def clip_dir(self, clip_id: str) -> str:
        return os.path.join(self.clips_dir, clip_id)

    def meta_path(self, clip_id: str) -> str:
        return os.path.join(self.clip_dir(clip_id), "meta.json")

    def video_path(self, clip_id: str) -> str | None:
        m = self.meta(clip_id) or {}
        name = m.get("video_file") or "video.mp4"
        p = os.path.join(self.clip_dir(clip_id), name)
        return p if os.path.isfile(p) else None

    def thumb_path(self, clip_id: str) -> str | None:
        p = os.path.join(self.clip_dir(clip_id), "thumb.jpg")
        return p if os.path.isfile(p) else None

    def notes_path(self, clip_id: str) -> str:
        return os.path.join(self.clip_dir(clip_id), "notes.md")

    # ---- meta
    def meta(self, clip_id: str) -> dict | None:
        m = read_json(self.meta_path(clip_id))
        return m if isinstance(m, dict) else None

    def update_meta(self, clip_id: str, **changes) -> dict:
        with _lock:
            m = self.meta(clip_id) or {}
            m.update(changes)
            write_json(self.meta_path(clip_id), m)
        return m

    def list_ids(self) -> list[str]:
        out = []
        for name in os.listdir(self.clips_dir):
            if os.path.isfile(self.meta_path(name)):
                out.append(name)
        return out

    def list_meta(self) -> list[dict]:
        metas = [m for m in (self.meta(i) for i in self.list_ids()) if m and m.get("id")]
        metas.sort(key=lambda m: m.get("added_at") or "", reverse=True)
        return metas

    def find_existing(self, platform: str, short_id: str) -> str | None:
        suffix = f"_{platform}_{safe_part(short_id)}"
        for name in os.listdir(self.clips_dir):
            if name.endswith(suffix) and os.path.isfile(self.meta_path(name)):
                return name
        return None

    # ---- creating clips
    def create_clip(self, platform: str, short_id: str, kind: str, source_url: str | None,
                    title: str = "", status: str = "downloading") -> str:
        with _lock:
            clip_id = f"{datetime.now().strftime('%Y-%m-%d')}_{platform}_{safe_part(short_id)}"
            os.makedirs(self.clip_dir(clip_id), exist_ok=True)
            write_json(self.meta_path(clip_id), {
                "id": clip_id, "source_url": source_url, "platform": platform, "kind": kind,
                "title": title, "uploader": None, "upload_date": None,
                "view_count": None, "like_count": None, "duration_sec": None,
                "width": None, "height": None, "fps": None,
                "added_at": now_iso(), "status": status, "error": None,
                "video_file": "video.mp4", "app_version": VERSION,
            })
        return clip_id

    def delete_clip(self, clip_id: str) -> None:
        d = os.path.realpath(self.clip_dir(clip_id))
        if os.path.dirname(d) == os.path.realpath(self.clips_dir):   # never delete outside clips/
            shutil.rmtree(d, ignore_errors=True)
        self.rebuild_index()

    # ---- index for Claude
    def rebuild_index(self) -> None:
        items = []
        for m in self.list_meta():
            card = read_json(os.path.join(self.clip_dir(m["id"]), "style-card.json"))
            card = card if isinstance(card, dict) else {}
            items.append({
                "id": m["id"], "kind": m.get("kind"), "platform": m.get("platform"),
                "status": m.get("status"), "view_count": m.get("view_count"),
                "name_th": card.get("name_th"), "tags": card.get("tags") or [],
                "summary_th": card.get("summary_th"), "fit_for_th": card.get("fit_for_th") or [],
            })
        with _lock:
            write_json(os.path.join(self.root, "library-index.json"),
                       {"updated_at": now_iso(), "app_version": VERSION, "clips": items})

    def style_card(self, clip_id: str) -> dict | None:
        c = read_json(os.path.join(self.clip_dir(clip_id), "style-card.json"))
        return c if isinstance(c, dict) else None


def fmt_views(n) -> str:
    if not isinstance(n, (int, float)):
        return ""
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}".rstrip("0").rstrip(".") + "K" if n < 100_000 else f"{n // 1000}K"
    return str(n)
