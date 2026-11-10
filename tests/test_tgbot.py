import os
import time

import pytest
from PySide6.QtWidgets import QApplication

from stylevault import autostart, tgbot
from stylevault import library as L
from stylevault.settings import Settings
from stylevault.ui import theme
from stylevault.ui.mainwindow import MainWindow
from test_ui import wait_until  # noqa: F401  (shared helper)


class FakeTelegram:
    """Stands in for api.telegram.org. Records every call."""

    def __init__(self):
        self.calls = []
        self.updates = []
        self.next_id = 100
        self.fail = None

    def __call__(self, url, payload, timeout):
        method = url.rsplit("/", 1)[1]
        self.calls.append((method, payload))
        if self.fail:
            return self.fail
        if method == "getMe":
            return {"ok": True, "result": {"first_name": "คลังสไตล์", "username": "sv_bot"}}
        if method == "getUpdates":
            ups, self.updates = self.updates, []
            return {"ok": True, "result": ups}
        if method == "sendMessage":
            self.next_id += 1
            return {"ok": True, "result": {"message_id": self.next_id}}
        return {"ok": True, "result": True}

    def sent(self):
        return [p["text"] for m, p in self.calls if m == "sendMessage"]


def msg(text, chat=1, uid=1, typ="private"):
    return {"update_id": uid, "message": {"message_id": uid, "chat": {"id": chat, "type": typ}, "text": text,
                                          "from": {"first_name": "แตม"}}}


def make_bot(chat=1, code=None):
    t = FakeTelegram()
    bot = tgbot.Bot(tgbot.Api("TOKEN", t), chat_id=chat, default_kind="viral", pair_code=code)
    got = []
    bot.on_add = lambda urls, note, kind, cid: got.append((urls, note, kind, cid))
    return bot, t, got


def test_extract_links_and_note():
    urls, note = tgbot.extract("ดูอันนี้ https://vt.tiktok.com/ZSabc/ ชอบทรานซิชันวินาทีที่ 5")
    assert urls == ["https://vt.tiktok.com/ZSabc/"]
    assert note == "ดูอันนี้ ชอบทรานซิชันวินาทีที่ 5"
    assert tgbot.extract("ไม่มีลิงก์")[0] == []
    two, _ = tgbot.extract("https://a.com/x https://b.com/y. https://a.com/x")
    assert two == ["https://a.com/x", "https://b.com/y"]


def test_link_asks_for_kind_then_adds_on_button():
    bot, t, got = make_bot()
    bot.handle(msg("https://vt.tiktok.com/ZS1/ โน้ตนี้", uid=7))
    assert "คลิปนี้เป็นแบบไหน" in t.sent()[0]
    kb = [p for m, p in t.calls if m == "sendMessage"][0]["reply_markup"]["inline_keyboard"][0]
    assert [b["callback_data"] for b in kb] == ["k|7|effects", "k|7|viral"]
    bot.handle({"update_id": 8, "callback_query": {"id": "q", "data": "k|7|effects",
                                                  "message": {"chat": {"id": 1}, "message_id": 101}}})
    assert got == [(["https://vt.tiktok.com/ZS1/"], "โน้ตนี้", "effects", 1)]
    bot.handle({"update_id": 9, "callback_query": {"id": "q", "data": "k|7|viral",
                                                  "message": {"chat": {"id": 1}, "message_id": 101}}})
    assert len(got) == 1                                   # a second press does nothing


def test_no_button_uses_default_after_a_minute():
    bot, t, got = make_bot()
    now = time.time()
    bot.handle(msg("https://youtu.be/abcdefghijk"), now=now)
    bot.tick(now + 30)
    assert got == []
    bot.tick(now + 61)
    assert got and got[0][2] == "viral"
    assert bot.next_due() is None


def test_strangers_are_ignored_completely():
    bot, t, got = make_bot(chat=1)
    bot.handle(msg("https://vt.tiktok.com/ZS1/", chat=999))
    bot.handle({"update_id": 2, "callback_query": {"id": "q", "data": "k|1|viral",
                                                  "message": {"chat": {"id": 999}, "message_id": 5}}})
    assert t.calls == [] and got == []
    bot.handle(msg("https://vt.tiktok.com/ZS1/", chat=1, typ="group"))
    assert t.calls == []


def test_pairing_with_code_and_lockout():
    bot, t, got = make_bot(chat=0, code="4827")
    paired = []
    bot.on_paired = lambda cid, name: paired.append((cid, name))
    bot.handle(msg("https://vt.tiktok.com/ZS1/", chat=55))        # a link before pairing: not accepted
    assert got == [] and "เชื่อมแล้ว" not in " ".join(t.sent())
    bot.handle(msg("4827", chat=55))
    assert paired == [(55, "แตม")] and bot.chat_id == 55 and bot.pair_code is None
    bot.handle(msg("4827", chat=77))                               # someone else, now that it is paired
    assert paired == [(55, "แตม")]

    bot, t, got = make_bot(chat=0, code="1111")
    locked = []
    bot.on_pair_locked = lambda: locked.append(1)
    for i in range(tgbot.MAX_WRONG_CODES):
        bot.handle(msg("0000", chat=9, uid=i))
    assert locked == [1] and bot.pair_code is None and bot.chat_id == 0
    bot.handle(msg("1111", chat=9))
    assert bot.chat_id == 0                                        # the cancelled code no longer works


def test_not_pairing_and_no_chat_means_silence():
    bot, t, got = make_bot(chat=0, code=None)
    bot.handle(msg("hi", chat=3))
    assert t.calls == []


def test_error_kinds():
    t = FakeTelegram()
    t.fail = {"ok": False, "error_code": 401, "description": "Unauthorized"}
    with pytest.raises(tgbot.TgError) as e:
        tgbot.Api("x", t).call("getMe")
    assert e.value.kind == "auth"
    t.fail = {"ok": False, "error_code": 409, "description": "Conflict"}
    with pytest.raises(tgbot.TgError) as e:
        tgbot.Api("x", t).call("getUpdates")
    assert e.value.kind == "conflict"


def test_poll_advances_offset():
    bot, t, got = make_bot()
    t.updates = [msg("ไม่มีลิงก์", uid=41), msg("ก็ไม่มี", uid=42)]
    assert bot.poll(timeout=1) == 2
    assert bot.offset == 43


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    theme.load_fonts()
    a.setStyleSheet(theme.STYLE)
    return a


def make_window(tmp_path, **kw):
    os.environ["APPDATA"] = str(tmp_path / "appdata")
    s = Settings(library_dir=str(tmp_path / "lib"), first_run_done=True, **kw)
    return MainWindow(s)


def test_phone_link_goes_to_library_with_note_and_reports_back(app, tmp_path):
    w = make_window(tmp_path)
    sent = []
    w.tg.send = lambda chat, text: sent.append((chat, text))
    w.jobs.add_link = lambda cid, url: None                 # no real download in the test
    w._tg_add(["https://www.tiktok.com/@x/video/7600000000000000001"], "ชอบช่วงเปิด", "effects", 1)
    metas = w.lib.list_meta()
    assert len(metas) == 1 and metas[0]["kind"] == "effects"
    cid = metas[0]["id"]
    assert "ฝากจากมือถือ: ชอบช่วงเปิด" in open(w.lib.notes_path(cid), encoding="utf-8").read()
    assert sent[-1] == (1, "กำลังโหลดคลิปบนคอม…")
    w.lib.update_meta(cid, status="waiting", title="คลิปทดสอบ")
    w._tg_report(cid)
    assert sent[-1][0] == 1 and "เข้าคลังแล้ว" in sent[-1][1] and "#" in sent[-1][1]
    assert cid not in w._tg_clips

    w._tg_add(["https://www.tiktok.com/@x/video/7600000000000000001"], "", "viral", 1)   # same link again
    assert len(w.lib.list_meta()) == 1 and "มีในคลังแล้ว" in sent[-1][1]

    w._tg_add(["https://www.tiktok.com/@x/video/7600000000000000002"], "", "viral", 1)
    cid2 = [m["id"] for m in w.lib.list_meta() if m["id"] != cid][0]
    w.lib.update_meta(cid2, status="error", error="คลิปนี้ต้องล็อกอินก่อน")
    w._tg_report(cid2)
    assert "ไม่ได้" in sent[-1][1] and "ล็อกอิน" in sent[-1][1]


def test_close_hides_only_when_telegram_is_on(app, tmp_path):
    w = make_window(tmp_path)
    assert not w.hides_on_close()                           # no Telegram -> closing really closes
    w2 = make_window(tmp_path, tg_token="T", tg_chat_id=5)
    w2.tg.stop()
    if w2.tray:                                             # the test machine may have no tray at all
        w2.tray.setVisible(True)
        assert w2.hides_on_close() == w2.tray.isVisible()
    w2.s.tg_paused = True
    assert not w2.hides_on_close()


def test_settings_wizard_and_connected_state(app, tmp_path):
    w = make_window(tmp_path)
    fake = FakeTelegram()
    w.tg._transport = fake
    sp = w.settings_page
    sp.load()
    assert sp.tg_wizard.isVisibleTo(sp) and not sp.tg_done.isVisibleTo(sp)
    sp.tg_token_edit.setText("123:ABC")
    sp._tg_check()
    assert wait_until(app, lambda: sp.tg_step3.isVisibleTo(sp), 10)
    assert "คลังสไตล์" in sp.tg_result.text() and len(sp.tg_code.text()) == 4
    code = sp.tg_code.text()
    fake.updates = [msg(code, chat=42, uid=1)]
    assert wait_until(app, lambda: sp.tg_done.isVisibleTo(sp), 30)
    assert w.s.tg_chat_id == 42 and w.s.tg_token == "123:ABC"
    w.tg.stop()


def test_wrong_token_message(app, tmp_path):
    w = make_window(tmp_path)
    fake = FakeTelegram()
    fake.fail = {"ok": False, "error_code": 401, "description": "Unauthorized"}
    w.tg._transport = fake
    sp = w.settings_page
    sp.load()
    sp.tg_token_edit.setText("bad")
    sp._tg_check()
    assert wait_until(app, lambda: "ไม่ถูกต้อง" in sp.tg_result.text(), 10)
    assert not w.s.tg_token


def test_autostart_only_for_installed_program(app, tmp_path):
    assert autostart.command().endswith("--tray")
    assert autostart.set_enabled(True) is False             # not a frozen Windows build here


def test_second_copy_asks_first_to_show(app):
    from stylevault import single
    shown = []
    assert single.notify_existing() is False                # nobody running yet
    lst = single.Listener(lambda: shown.append(1))
    assert lst.ok
    assert single.notify_existing() is True
    assert wait_until(app, lambda: shown, 5)
    lst.server.close()


def test_network_failures_explain_themselves():
    import socket
    import urllib.error
    def boom(exc):
        def tr(url, payload, timeout):
            raise exc
        return tr
    # the real transport turns urllib errors into easy-Thai TgErrors
    api = tgbot.Api("T")
    import unittest.mock as mock
    with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError(socket.gaierror(11001, "getaddrinfo failed"))):
        with pytest.raises(tgbot.TgError) as e:
            api.call("getMe")
    assert e.value.kind == "net" and "บล็อก" in str(e.value) and "gaierror" in e.value.detail or "URLError" in e.value.detail
    with mock.patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        with pytest.raises(tgbot.TgError) as e:
            api.call("getMe")
    assert "หมดเวลา" in str(e.value)
    with mock.patch("urllib.request.urlopen", side_effect=ValueError("URL can't contain control characters")):
        with pytest.raises(tgbot.TgError) as e:
            api.call("getMe")
    assert e.value.kind == "auth"


def test_ssl_context_has_mozilla_roots_and_still_verifies():
    import ssl
    ctx = tgbot.ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname
    assert len(ctx.get_ca_certs()) > 100
    assert tgbot.Api("T")._ctx is not None


def test_bot_reports_what_it_saw_even_when_silent():
    bot, t, got = make_bot(chat=1)
    ev = []
    bot.on_event = ev.append
    bot.handle(msg("https://vt.tiktok.com/ZS1/", chat=999))
    assert "ไม่ใช่บัญชีที่เชื่อม" in ev[-1]
    bot.handle(msg("hello", chat=1))
    assert "ไม่เจอลิงก์" in ev[-1]
    bot.handle(msg("https://vt.tiktok.com/ZS1/", chat=1, uid=5))
    assert "เจอลิงก์ 1" in ev[-1]
    t.fail = {"ok": False, "error_code": 400, "description": "Bad Request: chat not found"}
    bot.say(1, "x")
    assert "ตอบกลับในแชตไม่ได้" in ev[-1] and "chat not found" in ev[-1]


def test_odd_message_does_not_vanish_silently():
    bot, t, got = make_bot(chat=1)
    ev = []
    bot.on_event = ev.append
    t.updates = [{"update_id": 3, "message": {"message_id": 3, "chat": {"id": "oops", "type": "private"}, "text": "x"}}]
    assert bot.poll(timeout=1) == 1 and bot.offset == 4
    assert any("อ่านข้อความไม่ได้" in e for e in ev)


def test_after_restart_the_saved_bot_answers_a_link(app, tmp_path):
    """The path the user hits every day: settings already hold token + chat, the program starts, a link arrives."""
    w = make_window(tmp_path, tg_token="123:ABC", tg_chat_id=42)
    w.tg.stop()
    fake = FakeTelegram()
    w.tg._transport = fake
    w.tg_start()
    fake.updates = [msg("https://vt.tiktok.com/ZSpU9CFWE/", chat=42, uid=1)]
    assert wait_until(app, lambda: any("คลิปนี้เป็นแบบไหน" in s for s in fake.sent()), 20)
    assert wait_until(app, lambda: "ได้รับข้อความจากบัญชีที่เชื่อม" in w.tg.last_event, 5)
    w.tg.stop()


def test_link_sent_while_program_was_closed_says_so():
    bot, t, got = make_bot()
    old = msg("https://vt.tiktok.com/ZSpU9CFWE/")
    old["message"]["date"] = time.time() - 3 * 3600
    bot.handle(old)
    reply = t.sent()[-1]
    assert "ตอนโปรแกรมปิดอยู่" in reply and "ฝากไว้ตั้งแต่" in reply
    fresh = msg("https://vt.tiktok.com/ZSnew/", uid=2)
    fresh["message"]["date"] = time.time() - 5
    bot.handle(fresh)
    assert "ตอนโปรแกรมปิดอยู่" not in t.sent()[-1]


def test_start_message_explains_waiting_while_pc_is_off():
    bot, t, _ = make_bot()
    bot.handle(msg("/start"))
    assert "24 ชั่วโมง" in t.sent()[-1]


def test_quit_tells_the_phone_chat_once(app, tmp_path):
    w = make_window(tmp_path, tg_token="123:ABC", tg_chat_id=42)
    w.tg.stop()
    fake = FakeTelegram()
    w.tg._transport = fake
    w.tg_start()
    assert wait_until(app, lambda: w.tg.active, 5)
    w._say_goodbye()
    w._say_goodbye()                                         # a second call must not send again
    bye = [s for s in fake.sent() if "ปิดโปรแกรมคลังสไตล์แล้ว" in s]
    assert len(bye) == 1
    w.tg.stop()


def test_quit_message_can_be_turned_off_and_stays_quiet_when_paused(app, tmp_path):
    w = make_window(tmp_path, tg_token="123:ABC", tg_chat_id=42, tg_notify_quit=False)
    w.tg.stop()
    fake = FakeTelegram()
    w.tg._transport = fake
    w.tg_start()
    assert wait_until(app, lambda: w.tg.active, 5)
    w._say_goodbye()
    assert not any("ปิดโปรแกรม" in s for s in fake.sent())
    w.tg.stop()
