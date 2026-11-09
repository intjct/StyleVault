"""Telegram bot: the owner shares a clip link to the bot from the phone, the program adds it to the library.

The program asks Telegram for new messages itself (long polling) - no server of ours in between.
Only the owner's private chat is accepted. Only links and short notes are read; nothing from the library is sent out
except short status lines ("#12 เข้าคลังแล้ว")."""
from __future__ import annotations

import json
import re
import secrets
import threading
import time
import urllib.error
import urllib.request

from PySide6.QtCore import QObject, Signal

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
PENDING_SEC = 60            # no button pressed within this time -> use the default kind
MAX_WRONG_CODES = 5
KIND_TH = {"effects": "สไตล์เอฟเฟกต์", "viral": "คลิปไวรัล"}


def ssl_context():
    """Windows' own list of trusted certificate makers, plus the Mozilla list (the one Firefox uses).
    Windows only keeps roots it has needed before, so a root that Chrome would fetch on demand can be missing
    for this program ("self-signed certificate in certificate chain"). Checking stays fully on."""
    import ssl
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    return ctx


class TgError(Exception):
    def __init__(self, kind: str, message: str = "", detail: str = ""):
        super().__init__(message or kind)
        self.kind = kind            # auth / conflict / net / other
        self.detail = detail        # raw reason, for tech support


def net_message(e: BaseException) -> str:
    """Easy-Thai reason for a network failure."""
    import socket
    import ssl
    r = getattr(e, "reason", e)
    if isinstance(r, ssl.SSLError) or "CERTIFICATE" in str(r).upper():
        return ("เครื่องนี้ไม่ไว้ใจใบรับรองความปลอดภัยของ Telegram — มักเกิดจากโปรแกรมแอนตี้ไวรัส VPN หรือเวลาในเครื่องไม่ตรง "
                "ลองปิดโปรแกรมพวกนี้ชั่วคราวแล้วกดตรวจใหม่")
    if isinstance(r, (socket.timeout, TimeoutError)) or "timed out" in str(r).lower():
        return "เข้า Telegram ไม่ทัน (หมดเวลา) — เน็ตอาจช้า หรือเครือข่ายนี้บล็อก Telegram ลองเปลี่ยนไปใช้เน็ตอื่น (เช่น ฮอตสปอตมือถือ) แล้วกดตรวจใหม่"
    if isinstance(r, socket.gaierror) or "getaddrinfo" in str(r).lower():
        return "หาที่อยู่ของ Telegram ไม่เจอ — เน็ตอาจหลุด หรือเครือข่ายนี้บล็อก Telegram ลองเปลี่ยนเน็ตหรือปิด VPN แล้วกดตรวจใหม่"
    return "เชื่อมต่อ Telegram ไม่ได้ — ตรวจว่าเน็ตใช้ได้ ปิด VPN หรือโปรแกรมแอนตี้ไวรัสชั่วคราว แล้วกดตรวจใหม่"


def extract(text: str) -> tuple[list[str], str]:
    """Links found in a message, and the rest of the text (the user's own note)."""
    text = text or ""
    urls = [u.rstrip(".,;)") for u in URL_RE.findall(text)]
    seen: list[str] = []
    for u in urls:
        if u not in seen:
            seen.append(u)
    note = " ".join(URL_RE.sub(" ", text).split())
    return seen, note


def new_code() -> str:
    return f"{secrets.randbelow(10000):04d}"


class Api:
    def __init__(self, token: str, transport=None):
        self.token = token
        self._transport = transport or self._http
        self._ctx = ssl_context() if transport is None else None

    def _http(self, url: str, payload: dict, timeout: float) -> dict:
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=self._ctx) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read().decode("utf-8"))
            except Exception:
                body = {"ok": False, "error_code": e.code, "description": str(e)}
            return body
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            raise TgError("net", net_message(e), detail=f"{type(e).__name__}: {e}") from e
        except ValueError as e:                          # a pasted token with strange characters makes an invalid address
            raise TgError("auth", "รหัสบอทใช้ไม่ได้", detail=str(e)) from e

    def call(self, method: str, params: dict | None = None, timeout: float = 30) -> object:
        data = self._transport(f"https://api.telegram.org/bot{self.token}/{method}", params or {}, timeout)
        if data.get("ok"):
            return data.get("result")
        code = data.get("error_code")
        if code in (401, 404):
            raise TgError("auth", "รหัสบอทใช้ไม่ได้")
        if code == 409:
            raise TgError("conflict", "มีโปรแกรมอื่นกำลังรับข้อความของบอทนี้อยู่")
        raise TgError("other", str(data.get("description") or "เกิดข้อผิดพลาด"))


class Bot:
    """The rules. No threads here, so it can be tested with a fake transport."""

    def __init__(self, api: Api, chat_id: int = 0, default_kind: str = "viral", pair_code: str | None = None):
        self.api = api
        self.chat_id = int(chat_id or 0)
        self.default_kind = default_kind if default_kind in KIND_TH else "viral"
        self.pair_code = pair_code
        self.wrong = 0
        self.pending: dict[str, dict] = {}
        self.offset = 0
        # filled in by the service
        self.on_add = lambda urls, note, kind, chat_id: None
        self.on_paired = lambda chat_id, name: None
        self.on_pair_locked = lambda: None

    # ---- sending
    def say(self, chat_id: int, text: str, markup: dict | None = None) -> int | None:
        params: dict = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
        if markup:
            params["reply_markup"] = markup
        try:
            res = self.api.call("sendMessage", params, timeout=20)
            return (res or {}).get("message_id")
        except TgError:
            return None

    def _edit(self, chat_id: int, message_id: int | None, text: str):
        if not message_id:
            return
        try:
            self.api.call("editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text}, timeout=20)
        except TgError:
            pass

    # ---- incoming
    def poll(self, timeout: int = 20) -> int:
        updates = self.api.call("getUpdates", {"offset": self.offset, "timeout": timeout,
                                               "allowed_updates": ["message", "callback_query"]}, timeout=timeout + 15)
        for u in updates or []:
            self.offset = max(self.offset, int(u.get("update_id", 0)) + 1)
            try:
                self.handle(u)
            except TgError:
                pass
        return len(updates or [])

    def handle(self, u: dict, now: float | None = None):
        now = time.time() if now is None else now
        if "callback_query" in u:
            self._callback(u["callback_query"])
            return
        m = u.get("message")
        if not m:
            return
        chat = m.get("chat") or {}
        if chat.get("type") != "private":
            return
        cid = int(chat.get("id", 0))
        text = (m.get("text") or m.get("caption") or "").strip()
        if not self.chat_id or cid != self.chat_id:
            self._maybe_pair(cid, m, text)
            return
        if text.startswith("/start") or text.startswith("/help"):
            self.say(cid, "สวัสดีครับ ส่งลิงก์คลิป (TikTok / Reels / Shorts / Facebook) มาได้เลย\n"
                          "จะพิมพ์โน้ตต่อท้ายลิงก์ด้วยก็ได้ โน้ตจะไปอยู่ในคลิปนั้น")
            return
        urls, note = extract(text)
        if not urls:
            self.say(cid, "ยังไม่เจอลิงก์ในข้อความนี้ — ส่งลิงก์คลิปมาได้เลยครับ")
            return
        key = str(m.get("message_id"))
        label = "ลิงก์" if len(urls) == 1 else f"{len(urls)} ลิงก์"
        kb = {"inline_keyboard": [[
            {"text": "🎨 สไตล์เอฟเฟกต์", "callback_data": f"k|{key}|effects"},
            {"text": "🔥 คลิปไวรัล", "callback_data": f"k|{key}|viral"}]]}
        mid = self.say(cid, f"รับ{label}แล้ว 🎬 คลิปนี้เป็นแบบไหน?\n"
                            f"(ถ้าไม่กด จะใช้ \"{KIND_TH[self.default_kind]}\" ใน 1 นาที)", kb)
        self.pending[key] = {"urls": urls, "note": note, "chat": cid, "msg": mid, "due": now + PENDING_SEC}

    def _maybe_pair(self, cid: int, m: dict, text: str):
        if not self.pair_code:
            return                                   # a stranger, or not pairing: say nothing at all
        if text == self.pair_code:
            self.chat_id = cid
            self.pair_code = None
            frm = m.get("from") or {}
            name = frm.get("first_name") or frm.get("username") or ""
            self.say(cid, "เชื่อมแล้ว ✓ ต่อจากนี้ส่งลิงก์คลิปมาที่นี่ได้เลย รับจากบัญชีนี้บัญชีเดียวนะครับ")
            self.on_paired(cid, name)
            return
        self.wrong += 1
        if self.wrong >= MAX_WRONG_CODES:
            self.pair_code = None
            self.on_pair_locked()
            self.say(cid, "รหัสผิดหลายครั้งแล้ว ระบบยกเลิกรหัสนี้ ให้กดสร้างรหัสใหม่ในโปรแกรม")
        else:
            self.say(cid, "รหัสไม่ถูกครับ ลองดูรหัส 4 หลักในหน้าตั้งค่าของโปรแกรมอีกที")

    def _callback(self, q: dict):
        msg = q.get("message") or {}
        cid = int((msg.get("chat") or {}).get("id", 0))
        if not self.chat_id or cid != self.chat_id:
            return
        try:
            _, key, kind = (q.get("data") or "").split("|")
        except ValueError:
            return
        item = self.pending.pop(key, None)
        try:
            self.api.call("answerCallbackQuery", {"callback_query_id": q.get("id"),
                                                  "text": "รับทราบ" if item else "หมดเวลาแล้ว"}, timeout=20)
        except TgError:
            pass
        if not item or kind not in KIND_TH:
            return
        self._edit(cid, item["msg"], f"เลือก \"{KIND_TH[kind]}\" แล้ว")
        self.on_add(item["urls"], item["note"], kind, cid)

    def tick(self, now: float | None = None):
        """Choices nobody pressed in time use the default kind."""
        now = time.time() if now is None else now
        for key in [k for k, v in self.pending.items() if v["due"] <= now]:
            item = self.pending.pop(key)
            self._edit(item["chat"], item["msg"], f"ใช้ \"{KIND_TH[self.default_kind]}\" ให้ (ไม่ได้กดเลือก)")
            self.on_add(item["urls"], item["note"], self.default_kind, item["chat"])

    def next_due(self, now: float | None = None) -> float | None:
        now = time.time() if now is None else now
        return min((v["due"] - now for v in self.pending.values()), default=None)


class Service(QObject):
    """Runs the Bot on a background thread and reports to the window by signals."""
    status = Signal(str)                      # off / paused / connecting / ok / offline / badtoken / conflict
    paired = Signal(int, str)                 # chat id, name
    pair_locked = Signal()
    add_request = Signal(list, str, str, int)  # urls, note, kind, chat id
    verified = Signal(bool, str)              # ok, bot name or easy-Thai message

    def __init__(self, transport=None):
        super().__init__()
        self._transport = transport
        self._bot: Bot | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.state = "off"
        self.last_error = ""
        self.token = ""
        self.code: str | None = None

    # ---- control
    @property
    def active(self) -> bool:
        return self.state in ("ok", "connecting", "offline", "conflict")

    def _set(self, st: str):
        if st != self.state:
            self.state = st
            self.status.emit(st)

    def verify(self, token: str):
        def work():
            try:
                me = Api(token.strip(), self._transport).call("getMe", timeout=20)
                self.verified.emit(True, f"{(me or {}).get('first_name', 'บอท')} (@{(me or {}).get('username', '')})")
            except TgError as e:
                msg = "รหัสบอทไม่ถูกต้อง ตรวจว่าคัดลอกมาครบทั้งหมด" if e.kind == "auth" else str(e)
                if e.detail:
                    msg += f"\n(รายละเอียดสำหรับช่างเทคนิค: {e.detail[:200]})"
                self.verified.emit(False, msg)
        threading.Thread(target=work, daemon=True).start()

    def configure(self, token: str, chat_id: int = 0, default_kind: str = "viral", pairing: bool = False,
                  start: bool = True):
        self.stop()
        self.token = token.strip()
        if not self.token:
            self._set("off")
            return
        if not start:
            self._set("paused")
            return
        self.code = new_code() if pairing else None
        bot = Bot(Api(self.token, self._transport), chat_id, default_kind, self.code)
        bot.on_add = lambda urls, note, kind, cid: self.add_request.emit(urls, note, kind, cid)
        bot.on_paired = self._on_paired
        bot.on_pair_locked = lambda: (setattr(self, "code", None), self.pair_locked.emit())
        self._bot = bot
        self._stop = threading.Event()
        self._set("connecting")
        self._thread = threading.Thread(target=self._loop, args=(bot, self._stop), daemon=True)
        self._thread.start()

    def new_pair_code(self) -> str | None:
        if not self._bot:
            return None
        self.code = new_code()
        self._bot.pair_code, self._bot.wrong = self.code, 0
        return self.code

    def set_default_kind(self, kind: str):
        if self._bot and kind in KIND_TH:
            self._bot.default_kind = kind

    def pause(self):
        self.stop()
        if self.token:
            self._set("paused")

    def stop(self):
        self._stop.set()
        self._thread = None
        self._bot = None

    def disconnect(self):
        self.stop()
        self.token = ""
        self.code = None
        self._set("off")

    def send(self, chat_id: int, text: str):
        if not self.token:
            return
        api = Api(self.token, self._transport)
        def work():
            try:
                api.call("sendMessage", {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}, timeout=20)
            except TgError:
                pass
        threading.Thread(target=work, daemon=True).start()

    def _on_paired(self, chat_id: int, name: str):
        self.code = None
        self.paired.emit(chat_id, name)

    # ---- the loop
    def _loop(self, bot: Bot, stop: threading.Event):
        def set_(st):
            if not stop.is_set():                 # an old thread must not change the state after it was stopped
                self._set(st)
        try:
            bot.api.call("deleteWebhook", {}, timeout=20)           # a leftover webhook would block getUpdates
        except TgError as e:
            if e.kind == "auth":
                set_("badtoken")
                return
        while not stop.is_set():
            try:
                due = bot.next_due()
                bot.poll(timeout=int(max(1, min(20, due if due is not None else 20))))
                if not stop.is_set():
                    set_("ok")
                bot.tick()
            except TgError as e:
                if e.kind == "auth":
                    set_("badtoken")
                    return
                self.last_error = e.detail
                set_("conflict" if e.kind == "conflict" else "offline")
                stop.wait(8 if e.kind == "conflict" else 10)
            except Exception:
                stop.wait(10)
