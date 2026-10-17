# PyInstaller recipe for Anchor.exe (run by build.ps1: pyinstaller --noconfirm anchor.spec).
# Builds a folder app in dist\Anchor\ with Python, Qt, the phone app and adb inside.

from pathlib import Path

desktop = Path(SPECPATH) / "desktop"

datas = [
    (str(desktop / "anchor-agent.apk"), "."),          # installed on the phone during setup
    (str(desktop / "placeholder-manifest.bin"), "."),  # template for Never allow placeholders
    (str(desktop / "icons"), "icons"),
]
if (desktop / "build-commit").exists():  # written by GitHub's build, for Menu → Check for updates…
    datas.append((str(desktop / "build-commit"), "."))
if (desktop / "platform-tools").exists():  # Google's adb.exe, downloaded by build.ps1
    datas.append((str(desktop / "platform-tools"), "platform-tools"))

a = Analysis(
    [str(desktop / "anchor.py")],
    pathex=[str(desktop)],
    datas=datas,
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml",
              "PySide6.QtQuick", "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtCharts"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Anchor",
    icon=str(desktop / "icons" / "anchor.ico"),
    console=False,  # a window app: no black console behind it
)
coll = COLLECT(exe, a.binaries, a.datas, name="Anchor")
