"""User settings, saved as JSON in %APPDATA%\\StyleVault\\settings.json (survives reinstalling)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

from . import APP_NAME


def config_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def default_library_dir() -> str:
    return os.path.join(os.path.expanduser("~"), "Documents", "StyleVault Library")


@dataclass
class Settings:
    library_dir: str = ""
    last_kind: str = "effects"           # effects / viral
    use_browser_login: bool = False      # read the browser's login for Instagram/Facebook
    browser: str = "chrome"              # chrome / edge
    first_run_done: bool = False
    volume: int = 50                     # clip player volume 0-100 (remembered)
    tg_token: str = ""                   # Telegram bot token (kept only on this PC)
    tg_chat_id: int = 0                  # the one chat the bot listens to (the owner's)
    tg_paused: bool = False              # "หยุดรับลิงก์ชั่วคราว" from the tray menu
    tg_default_kind: str = "viral"       # used when no button is pressed within 1 minute
    tg_notify_quit: bool = True          # tell the phone chat when the program is closed
    tray_on_close: bool = True           # closing the window keeps the program running in the tray (only while Telegram is on)
    autostart: bool = False              # start with Windows
    tray_hint_shown: bool = False        # the "still running in the tray" balloon is shown only once

    def library_path(self) -> str:
        return self.library_dir or default_library_dir()

    @classmethod
    def load(cls) -> "Settings":
        try:
            with open(os.path.join(config_dir(), "settings.json"), encoding="utf-8") as f:
                raw = json.load(f)
            known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
            return cls(**known)
        except Exception:
            return cls()

    def save(self) -> None:
        try:
            path = os.path.join(config_dir(), "settings.json")
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception:
            pass
