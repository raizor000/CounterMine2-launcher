from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

root = Path(SPECPATH)
datas = [
    (str(root / "assets"), "assets"),
    (str(root / "scripts" / "html"), "scripts/html"),
    (str(root / "scripts" / "internal" / "3D" / "*.glb"), "scripts/internal/3D"),
    (str(root / "scripts" / "internal" / "3D" / "minecraft.ttf"), "scripts/internal/3D"),
    (str(root / "scripts" / "internal" / "3D" / "shaders"), "scripts/internal/3D/shaders"),
]
for package in ("panda3d", "simplepbr", "gltf"):
    datas += collect_data_files(package)

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=collect_dynamic_libs("panda3d"),
    datas=datas,
    hiddenimports=[
        "pypresence",
        "scripts.internal.modrinth_plugin",
        "scripts.internal.curseforge_plugin",
        "scripts.internal.ranked_plugin",
        "scripts.internal.counterstrike2theme",
    ],
    excludes=["tkinter", "PyQt6.QtQml", "PyQt6.QtQuick"],
)

# Qt uses the ICU exported by Windows. A foreign ICU on PATH can shadow it.
system_icu = {"icuuc.dll", "icuin.dll"}
a.binaries = [entry for entry in a.binaries if entry[0].lower() not in system_icu]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CounterMine2_v5.0",
    console=False,
    icon=str(root / "assets" / "icons" / "ico.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="CounterMine2_v5.0")
