# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import (
    collect_dynamic_libs,
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

block_cipher = None

datas = []
binaries = []
hiddenimports = []

# Panda3D
datas += collect_data_files("panda3d")
binaries += collect_dynamic_libs("panda3d")
hiddenimports += collect_submodules("direct")

# SimplePBR
datas += collect_data_files("simplepbr")
hiddenimports += collect_submodules("simplepbr")

# glTF
# glTF
datas += collect_data_files("gltf")
hiddenimports += collect_submodules("gltf")
datas += copy_metadata("panda3d-gltf") # <--- ДОБАВЬ ЭТУ СТРОЧКУ

# ---------- Твои ресурсы ----------

datas += [
    ("background.glb", "."),
    ("minecraft.ttf", "."),
    ("shaders", "shaders"),
]

excludes=[
    "tkinter", "unittest", "test", "pydoc", "matplotlib",
    "PyQt6.QtWebEngine", "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtMultimedia", "PyQt6.QtBluetooth", "PyQt6.QtDesigner",
    "PyQt6.QtHelp", "PyQt6.QtLocation", "PyQt6.QtNetworkAuth",
    "PyQt6.QtPositioning", "PyQt6.QtRemoteObjects", "PyQt6.QtSensors",
    "PyQt6.QtSerialPort", "PyQt6.QtSql", "PyQt6.QtSvg", "PyQt6.QtTest",
    "PyQt6.QtTextToSpeech", "PyQt6.QtWebChannel", "PyQt6.QtWebSockets",
]

a = Analysis(
    ["panda3dtest.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="panda3dtest",
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="panda3dtest",
)