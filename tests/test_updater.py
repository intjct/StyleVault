import http.server
import json
import os
import threading
import time

import pytest
from PySide6.QtWidgets import QApplication

from stylevault import VERSION, updater
from stylevault.ui import dialogs, theme
from stylevault.ui.update_bar import UpdateBar

INSTALLER = b"MZ" + os.urandom(300_000)


@pytest.fixture()
def server(monkeypatch):
    state = {"tag": "v9.9.9", "asset_size": len(INSTALLER), "asset_name": "StyleVault-Setup-9.9.9.exe", "fail": False}

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if state["fail"]:
                self.send_response(500); self.end_headers(); return
            if self.path == "/latest":
                body = json.dumps({"tag_name": state["tag"], "body": "เพิ่มระบบอัปเดต", "assets": [
                    {"name": "StyleVault-9.9.9-portable.zip", "browser_download_url": f"http://127.0.0.1:{port}/zip", "size": 5},
                    {"name": state["asset_name"], "browser_download_url": f"http://127.0.0.1:{port}/setup.exe",
                     "size": state["asset_size"]}]}).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
                self.wfile.write(body)
            elif self.path == "/setup.exe":
                self.send_response(200); self.send_header("Content-Length", str(len(INSTALLER))); self.end_headers()
                self.wfile.write(INSTALLER)
            else:
                self.send_response(404); self.end_headers()

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("STYLEVAULT_UPDATE_API", f"http://127.0.0.1:{port}/latest")
    yield state
    srv.shutdown()


def test_version_compare():
    assert updater.is_newer("v0.3.1", "0.3.0") and updater.is_newer("1.0.0", "0.9.9")
    assert not updater.is_newer("v0.3.0", "0.3.0") and not updater.is_newer("v0.2.9", "0.3.0")
    assert updater.parse_version("v1.2") == (1, 2, 0)
    assert not updater.is_newer("", "0.3.0")


def test_check_finds_installer_not_zip(server):
    info = updater.check()
    assert info["version"] == "9.9.9" and info["url"].endswith("/setup.exe") and info["size"] == len(INSTALLER)


def test_check_none_when_up_to_date_or_no_installer(server):
    server["tag"] = f"v{VERSION}"
    assert updater.check() is None
    server["tag"], server["asset_name"] = "v9.9.9", "something-else.zip"
    assert updater.check() is None


def test_check_failure_is_easy_thai(server):
    server["fail"] = True
    with pytest.raises(updater.UpdateError) as e:
        updater.check()
    assert "อินเทอร์เน็ต" in str(e.value)


def test_download_ok_and_incomplete(server):
    info = updater.check()
    seen = []
    path = updater.download(info, seen.append)
    assert open(path, "rb").read() == INSTALLER and seen[-1] == 1.0 and seen == sorted(seen)
    info["size"] += 10                                                      # server promised more than it sent
    with pytest.raises(updater.UpdateError):
        updater.download(info, lambda f: None)
    assert not os.path.exists(path + ".part")


def test_install_command_is_quiet_and_reopens():
    cmd = updater.install_command("C:\\x\\Setup.exe")
    assert cmd[0] == "C:\\x\\Setup.exe" and "/VERYSILENT" in cmd and "/RELAUNCH=1" in cmd


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    theme.load_fonts()
    a.setStyleSheet(theme.STYLE)
    return a


def wait_until(app, cond, secs=15):
    end = time.time() + secs
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.03)
    return False


def test_bar_appears_waits_for_user_then_installs(app, server, monkeypatch):
    bar = UpdateBar(is_busy=lambda: False)
    bar.check(manual=False)
    assert wait_until(app, lambda: bar.info is not None)
    assert not bar.isHidden() and "9.9.9" in bar.label.text() and "อัปเดตเลย" in bar.go.text()
    ran = []
    quit_called = []
    monkeypatch.setattr(updater, "can_install", lambda: True)
    monkeypatch.setattr(updater, "run_installer", lambda p: ran.append(p))
    monkeypatch.setattr(QApplication, "quit", staticmethod(lambda: quit_called.append(1)))
    assert not ran                                                          # nothing runs until the button is pressed
    bar.go.click()
    assert wait_until(app, lambda: ran and quit_called)
    assert open(ran[0], "rb").read() == INSTALLER


def test_bar_warns_when_busy_and_can_say_later(app, server, monkeypatch):
    bar = UpdateBar(is_busy=lambda: True)
    bar.check(manual=False)
    assert wait_until(app, lambda: bar.info is not None)
    asked = []
    monkeypatch.setattr(updater, "can_install", lambda: True)
    monkeypatch.setattr(dialogs, "message", lambda *a, **k: asked.append(a[1]) or False)
    bar.go.click()
    app.processEvents()
    assert asked == ["ตอนนี้ยังมีงานค้างอยู่"] and bar.go.isEnabled()      # said "wait": nothing was downloaded
    bar.later.click()
    assert bar.isHidden()


def test_bar_stays_hidden_when_up_to_date_or_offline(app, server):
    server["tag"] = f"v{VERSION}"
    bar = UpdateBar()
    bar.check(manual=False)
    assert wait_until(app, lambda: not bar.checking)
    assert bar.isHidden()
    server["fail"] = True
    bar.check(manual=False)
    assert wait_until(app, lambda: not bar.checking)
    assert bar.isHidden()                                                   # a failed quiet check shows nothing


def test_manual_check_reports_in_settings_text(app, server):
    server["tag"] = f"v{VERSION}"
    bar = UpdateBar()
    out = []
    bar.result_cb = out.append
    bar.check(manual=True)
    assert wait_until(app, lambda: out)
    assert out == ["คุณใช้เวอร์ชันล่าสุดอยู่แล้ว"]
