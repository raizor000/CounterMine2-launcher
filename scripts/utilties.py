import datetime
import hashlib
import random
import re
import socket
import string
from math import cos, sin, pi

import minecraft_launcher_lib
import psutil
import requests
import win32gui
import win32process
from PyQt6.QtCore import pyqtSignal, QPropertyAnimation, Qt, QEasingCurve, QRectF, \
    QTimer, QPointF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPainterPath, QCursor
from PyQt6.QtWidgets import QWidget, QFrame, QVBoxLayout, QLabel

from .constants import *
from .translations import translations


def has_internet(timeout=2):
    try:
        with socket.create_connection(("cm2news.xyz", 443), timeout=timeout):
            return True
    except OSError:
        return False


def get_server_url() -> str:
    return backend


def get_server1_url() -> str:
    return backend1


def get_banned_ips() -> list:
    try:
        response = requests.get(f'{get_server_url()}/banned_ips')
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Ошибка при получении списка IP: {e}")
        return []


def get_external_ip() -> str:
    try:
        response = requests.get(external_ip_url, timeout=2)
        response.raise_for_status()
        ip_data = response.json()
        return ip_data['ip']
    except requests.RequestException as e:
        return "Неизвестный"


def is_mod_installed(mc_dir: str, slug: str) -> bool:
    mods_dir = os.path.join(mc_dir, "mods")
    if os.path.exists(mods_dir):
        for file in os.listdir(mods_dir):
            if file.endswith('.jar') and file.startswith(slug):
                return True
    return False


def download_with_progress(version: str, mc_path: str, progress_callback):
    def set_max(max):
        global total
        total = max

    def set_progress(current):
        percent = int((current / total) * 100)
        progress_callback(f"{min(percent, 100)}%")

    callback = {
        "setStatus": lambda *args: None,  # Для петрушки - нету необходимости, закинул заглушку через лямбду
        "setProgress": set_progress,
        "setMax": set_max,
    }
    try:
        minecraft_launcher_lib.install.install_minecraft_version(version, mc_path, callback)
        minecraft_launcher_lib.fabric.install_fabric(version, mc_path, callback=callback)
    except Exception as e:
        print(e)


def get_new_logfile(base_dir: str, prefix: str = "launcher") -> str:
    files = [f for f in os.listdir(base_dir) if f.startswith(prefix) and f.endswith(".log")]
    nums = [int(re.match(rf"{prefix}_(\d+)\.log", f).group(1)) for f in files if re.match(rf"{prefix}_(\d+)\.log", f)]
    new_num = max(nums or [0]) + 1
    if new_num >= 20:
        for f in files:
            os.remove(os.path.join(base_dir, f))
        new_num = 1
    return os.path.join(base_dir, f"{prefix}_{new_num}.log")


def send_log_line(msg: str, server_url: str):
    payload = {"log": f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg} \n"}
    try:
        requests.post(server_url, json=payload, timeout=3)
    except Exception as e:
        print("Ошибка отправки:", e)


def random_username(length: int = 8) -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def is_fabric_installed(mc_path: str, vanilla_version: str) -> bool:
    try:
        installed = minecraft_launcher_lib.utils.get_installed_versions(mc_path) or []
        for v in installed:
            vid = v.get("id", "")
            if vid.startswith("fabric-loader") and vanilla_version in vid:
                version_dir = os.path.join(mc_path, "versions", vid)
                json_file = os.path.join(version_dir, f"{vid}.json")
                jar_file = os.path.join(version_dir, f"{vid}.jar")
                if os.path.isdir(version_dir) and os.path.isfile(json_file) and os.path.isfile(jar_file):
                    return True
        return False
    except Exception as e:
        print(f"[is_fabric_installed] Ошибка: {e}")
        return False


def is_mc_running() -> bool:
    def enum_callback(hwnd, result):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "Minecraft" in title and "1.21.11" in title:
                result.append(True)

    found = []
    win32gui.EnumWindows(enum_callback, found)
    return bool(found)


def get_window_titles() -> list:
    titles = []

    def enum_cb(hwnd, results):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).lower()
            if title and ("minecraft" in title or "1.21.11" in title):
                results.append(title)

    win32gui.EnumWindows(enum_cb, titles)
    return titles


def find_minecraft_hwnd():
    def callback(hwnd, hwnds):
        if win32gui.IsWindowVisible(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                p = psutil.Process(pid)
                if "javaw.exe" in p.name().lower():
                    title = win32gui.GetWindowText(hwnd)
                    if "Minecraft" in title:
                        hwnds.append(hwnd)
            except psutil.NoSuchProcess:
                pass
        return True

    result = []
    win32gui.EnumWindows(callback, result)
    return result[0] if result else None


import platform


def generate_software_machine_id():
    os_info = platform.platform()
    processor_info = platform.processor()
    more = platform.node()
    unique_string = os_info + processor_info + more
    machine_id = hashlib.sha256(unique_string.encode()).hexdigest()
    return machine_id


def t(lang, key):
    if key not in translations[lang]:
        print("no key")
    return translations[lang].get(key, key)


def get_banned_hwids():
    try:
        response = requests.get(f'{get_server_url()}/banned_hwids', timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Ошибка при получении списка HWID: {e}")
        return []


def add_banned_hwid(hwid):
    try:
        response = requests.post(f'{get_server1_url()}/banned_hwids/add', json={'hwid': hwid}, timeout=5)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"Ошибка при добавлении HWID: {e}")
        return False


def get_queue_data():
    resp = requests.get(QUEUE_URL, timeout=3)
    if resp.status_code == 200:
        data = resp.json()
        players = data.get("queue", [])
        names = [(p["nickname"], p.get("elo", "—")) for p in players]
        return names
    return []


from PIL import Image


def check_mc_xray_textures(rp_path, limit=20):
    base = os.path.join(
        rp_path, "assets", "minecraft", "textures", "block"
    )
    if not os.path.isdir(base):
        return False, None

    checked = 0
    for root, _, files in os.walk(base):
        for fname in files:
            if not fname.lower().endswith(".png"):
                continue

            name = fname.lower()

            if any(ok in name for ok in XRAY_OK_WORDS):
                continue

            if not any(bad in name for bad in XRAY_BAD_BLOCKS):
                continue

            full = os.path.join(root, fname)
            try:
                with Image.open(full) as img:
                    if img.mode != "RGBA":
                        continue
                    alpha = img.getchannel("A")
                    if alpha.getextrema()[0] < 255:
                        return True, os.path.relpath(full, rp_path)
            except Exception:
                continue

            checked += 1
            if checked >= limit:
                return False, None

    return False, None


from datetime import date

def is_winter_period() -> bool:
    today = date.today()

    if today.month == 12:
        return today.day >= 1
    if today.month == 1:
        return today.day <= 14
    return False

def is_winter() -> bool:
    return date.today().month in (1, 2, 12)


def is_spring() -> bool:
    return date.today().month in (3, 4, 5)


def is_summer() -> bool:
    return date.today().month in (6, 7, 8)


def is_autumn() -> bool:
    return date.today().month in (9, 10, 11)


class SwitchButton(QWidget):
    stateChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(52, 28)
        self._checked = False
        self._pos = 4
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        if self._checked == checked:
            return
        self._checked = checked
        self._animate()
        self.stateChanged.emit(checked)

    def toggle(self):
        self.setChecked(not self._checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor("#45A049") if self._checked else QColor("#777777")
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, 52, 28, 14, 14)

        painter.setBrush(QColor("white"))
        painter.drawEllipse(self._pos, 4, 20, 20)

    def _animate(self):
        start = 28 if not self._checked else 4
        end = 4 if not self._checked else 28
        anim = QPropertyAnimation(self, b"_pos_anim", self)
        anim.setDuration(180)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(lambda v: setattr(self, '_pos', v) or self.update())
        anim.start()

    def _get_pos_anim(self):
        return self._pos

    def _set_pos_anim(self, value):
        self._pos = value
        self.update()

    _pos_anim = property(_get_pos_anim, _set_pos_anim)


class DropDown(QWidget):
    valueChanged = pyqtSignal(str)

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 32)
        self.items = items
        self.current = items[0] if items else ""
        self.expanded = False
        self.popup = None
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()
        super().mousePressEvent(event)

    def toggle(self):
        if self.expanded:
            self.close_popup()
        else:
            self.open_popup()

    def open_popup(self):
        if self.popup:
            self.popup.deleteLater()
        self.expanded = True

        self.popup = QFrame(self, flags=Qt.WindowType.Popup)
        self.popup.setStyleSheet("background-color: #2E2E2E; border: 1px solid #555; border-radius: 6px;")
        layout = QVBoxLayout(self.popup)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for item in self.items:
            label = QLabel(item)
            label.setStyleSheet(f"""
                QLabel {{
                    color: {'#45A049' if item == self.current else 'white'};
                    padding: 6px 10px;
                }}
                QLabel:hover {{
                    background-color: #3A3A3A;
                }}
            """)
            label.mousePressEvent = lambda e, text=item: self.select_item(text)
            label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

            layout.addWidget(label)

        self.popup.setLayout(layout)
        self.popup.setFixedWidth(self.width())
        self.popup.move(self.mapToGlobal(self.rect().bottomLeft()))
        self.popup.show()

    def close_popup(self):
        if self.popup:
            self.popup.close()
            self.popup.deleteLater()
            self.popup = None
        self.expanded = False
        self.update()

    def select_item(self, item):
        self.current = item
        self.valueChanged.emit(item)
        self.close_popup()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setBrush(QColor("#2E2E2E"))
        painter.setPen(QColor("#555"))
        painter.drawRoundedRect(0, 0, self.width(), 32, 8, 8)

        painter.setPen(QColor("white"))
        painter.drawText(12, 21, self.current)

        painter.setPen(QColor("white"))
        painter.drawText(self.width() - 20, 21, "▼")


class ShadowFrame(QFrame):
    def __init__(self, parent, x, y, w, h):
        super().__init__(parent)
        self.setGeometry(x, y, w, h)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(0, 0, 0, 150)
        blur = 40

        rect = QRectF(blur, blur, self.width() - 2 * blur, self.height() - 2 * blur)
        gradient = QBrush(color)
        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)

        for i in range(blur, 0, -1):
            alpha = int(150 * (i / blur))
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(rect.adjusted(-i, -i, i, i), 20, 20)


def draw_snowflake(painter, x, y, size):
    path = QPainterPath()
    for i in range(6):
        a = i * pi / 3
        path.moveTo(x, y)
        path.lineTo(
            x + cos(a) * size,
            y + sin(a) * size
        )
    painter.drawPath(path)


def snowflake_count() -> int:
    if date.today().month != 12:
        return 100
    return int(100 + (date.today().day - 1) * (100 / 30))

class SnowOverlay(QWidget):
    def __init__(self, parent, snow_img):
        super().__init__(parent)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.resize(1024, 580)

        self.snow_img = snow_img
        self.snow_img.setDevicePixelRatio(1)

        self.pixmaps = [
            self.snow_img.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            for size in (10, 14, 18)
        ]
        count = snowflake_count()
        self.snowflakes = [
            {
                "pos": QPointF(
                    random.randint(0, self.width()),
                    random.randint(-self.height(), self.height())
                ),
                "speed": random.uniform(0.8, 2.2),
                "pix": random.choice(self.pixmaps)
            }
            for _ in range(count)
        ]

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_snow)
        self.timer.start(20)  # ~40 FPS

    def update_snow(self):
        h = self.height()
        w = self.width()

        for s in self.snowflakes:
            s["pos"].setY(s["pos"].y() + s["speed"])
            if s["pos"].y() > h:
                s["pos"].setY(-20)
                s["pos"].setX(random.randint(0, w))

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        for s in self.snowflakes:
            pix = s["pix"]
            painter.drawPixmap(
                int(s["pos"].x() - pix.width() / 2),
                int(s["pos"].y() - pix.height() / 2),
                pix
            )
