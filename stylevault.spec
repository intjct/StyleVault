# PyInstaller recipe for StyleVault.exe (used by the GitHub build).
# Expects build_tools/ffmpeg.exe, ffprobe.exe and yt-dlp.exe (the workflow downloads them).
import os

tools = [(f"build_tools/{n}", "tools") for n in ("ffmpeg.exe", "ffprobe.exe", "yt-dlp.exe", "FFMPEG-LICENSE.txt")
         if os.path.exists(f"build_tools/{n}")]

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=[],
    datas=[("assets/stylevault.ico", "assets"), ("assets/stylevault.png", "assets"),
           ("assets/fonts", "assets/fonts"), ("LICENSE", ".")] + tools,
    excludes=["tkinter", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQuick3D",
              "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner",
              "PySide6.QtUiTools", "PySide6.QtHelp", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.QtWebEngineQuick", "PySide6.Qt3DCore", "PySide6.QtCharts", "PySide6.QtDataVisualization",
              "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSensors", "PySide6.QtSerialPort",
              "PySide6.QtLocation", "PySide6.QtPositioning", "PySide6.QtRemoteObjects", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="StyleVault",
    icon="assets/stylevault.ico",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="StyleVault", upx=False)
