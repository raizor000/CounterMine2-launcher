import os
import sys
import shutil
from pathlib import Path

APPDATA = os.getenv("APPDATA") or os.path.expanduser("~")

def res_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

BASE_DIR = Path(res_path("."))
LAUNCHER_DIR = Path(APPDATA) / ".countermine-launcher"

TARGET_DIR = Path(LAUNCHER_DIR/"CounterMine2_v4.3.exe\_internal\scripts")
TARGET_DIR2 = Path(LAUNCHER_DIR/"CounterMine2_v4.3.exe")


FILES = ["fetcher.py", "constants.py"]

if not TARGET_DIR.exists():
    raise FileNotFoundError(f"Не найдена папка: {TARGET_DIR}")

for file in FILES:
    src = BASE_DIR / file
    dst = TARGET_DIR / file

    if not src.exists():
        print(f"[!] Нет файла в _MEIPASS: {file}")
        continue

    try:
        shutil.copy2(src, dst)
        print(f"[OK] Заменен: {file}")
    except Exception as e:
        print(f"[ERR] {file}: {e}")

shutil.copy2()