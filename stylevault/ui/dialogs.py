from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget)

from . import theme


def ask_kind(parent, last: str, count: int = 1) -> str | None:
    d = QDialog(parent)
    d.setWindowTitle("เพิ่มคลิปเข้าคลัง")
    d.setMinimumWidth(440)
    lay = QVBoxLayout(d)
    lay.setContentsMargins(24, 22, 24, 20)
    lay.setSpacing(12)
    t = QLabel("คลิปนี้เป็นแบบไหน?" if count == 1 else f"คลิปทั้ง {count} ไฟล์นี้เป็นแบบไหน?")
    t.setObjectName("H2")
    lay.addWidget(t)
    chosen = {"kind": last}
    btns = {}

    def mk(key, name, desc):
        b = QPushButton(f"{name}\n{desc}")
        b.setCheckable(True)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet("text-align:left; padding:12px 14px; font-weight:400;")
        b.clicked.connect(lambda: pick(key))
        btns[key] = b
        lay.addWidget(b)

    def pick(key):
        chosen["kind"] = key
        for k, b in btns.items():
            b.setChecked(k == key)
            b.setStyleSheet("text-align:left; padding:12px 14px; font-weight:400;" +
                            (f"border:1.5px solid {theme.ACCENT.name()}; background:{theme.ACCENT_SOFT.name()};" if k == key else ""))

    mk("effects", "สไตล์เอฟเฟกต์", "คลิปที่เด่นเรื่องเอฟเฟกต์ ตัวหนังสือ ทรานซิชัน จังหวะตัดต่อ")
    mk("viral", "คลิปไวรัล", "คลิปยอดวิวสูง ที่อยากเรียนรู้ว่าเล่าเรื่องและเปิดคลิปยังไง")
    pick(last if last in btns else "effects")
    row = QHBoxLayout()
    row.addStretch(1)
    cancel = QPushButton("ยกเลิก")
    cancel.clicked.connect(d.reject)
    ok = QPushButton("เพิ่มเข้าคลัง")
    ok.setObjectName("Primary")
    ok.setDefault(True)
    ok.clicked.connect(d.accept)
    row.addWidget(cancel)
    row.addWidget(ok)
    lay.addLayout(row)
    return chosen["kind"] if d.exec() == QDialog.DialogCode.Accepted else None


def message(parent, title: str, text: str, ok_text: str = "ตกลง", cancel_text: str | None = None) -> bool:
    m = QMessageBox(parent)
    m.setWindowTitle(title)
    m.setText(text)
    m.setIcon(QMessageBox.Icon.NoIcon)
    okb = m.addButton(ok_text, QMessageBox.ButtonRole.AcceptRole)
    if cancel_text:
        m.addButton(cancel_text, QMessageBox.ButtonRole.RejectRole)
        m.setDefaultButton(m.buttons()[-1])
    m.exec()
    return m.clickedButton() is okb
