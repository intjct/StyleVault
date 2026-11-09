"""Only one StyleVault at a time (two copies would fight over the same Telegram bot).
A second launch just asks the first one to come to the front."""
from __future__ import annotations

from PySide6.QtNetwork import QLocalServer, QLocalSocket

NAME = "StyleVault-single-instance-v1"


def notify_existing() -> bool:
    """True when another copy is running (it has been asked to show its window)."""
    s = QLocalSocket()
    s.connectToServer(NAME)
    if s.waitForConnected(300):
        s.write(b"show")
        s.flush()
        s.waitForBytesWritten(300)
        s.disconnectFromServer()
        return True
    return False


class Listener:
    def __init__(self, on_show):
        self._on_show = on_show
        QLocalServer.removeServer(NAME)                  # clears a leftover from a crash
        self.server = QLocalServer()
        self.server.newConnection.connect(self._conn)
        self.ok = self.server.listen(NAME)

    def _ready(self):
        self._on_show()

    def _conn(self):
        sock = self.server.nextPendingConnection()
        if sock:
            sock.readyRead.connect(self._ready)              # the socket stays a child of the server: freed with it
