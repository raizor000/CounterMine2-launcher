# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

# Собираем данные
all_datas = []
all_datas += collect_data_files('panda3d')
all_datas += collect_data_files('simplepbr')
all_datas += collect_data_files('gltf')

# Собираем библиотеки
all_binaries = []
all_binaries += collect_dynamic_libs('panda3d')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=all_binaries,
    # ИСПРАВЛЕНИЕ ЗДЕСЬ: складываем списки через +
    datas=[('assets\\*', 'assets'), ('scripts\\*', 'scripts')] + all_datas,
    hiddenimports=['panda3d.core', 'panda3d.direct'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'unittest',
        'PyQt6.QtQml', 'PyQt6.QtSql', 'PyQt6.QtDesigner',
        'PyQt6.QtBluetooth', 'PyQt6.QtNfc', 'PyQt6.QtTest',
        'PyQt6.QtSensors', 'PyQt6.QtQuick'
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CounterMine2_v5.0.exe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icons\\ico.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],

    name='CounterMine2_v5.0.exe',
)