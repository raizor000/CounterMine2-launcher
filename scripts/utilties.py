import random
import re
from math import cos, sin, pi

import minecraft_launcher_lib
import requests
import win32gui
from PIL import Image
from PyQt6.QtCore import pyqtSignal, QPropertyAnimation, Qt, QEasingCurve, QRectF, QTimer, QPointF
from PyQt6.QtGui import QPainter, QColor, QBrush, QPainterPath, QCursor, QLinearGradient
from PyQt6.QtNetwork import QLocalSocket, QLocalServer
from PyQt6.QtWidgets import QWidget, QFrame, QVBoxLayout, QLabel, QGraphicsDropShadowEffect

from .constants import *
from .translations import translations


def get_server_url() -> str:
    return f"{backend}:{default_port}"  # запасной бекенд


def get_server1_url() -> str:
    return f"{backend1}"  # основной бекенд


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
    nums = [int(re.match(rf"{prefix}_(\d+)\.log", f).group(1)) for f in files if
            re.match(rf"{prefix}_(\d+)\.log", f)]  # парсим кол-во логов
    new_num = max(nums or [0]) + 1
    # if new_num >= 20:
    #     for f in files:
    #         os.remove(os.path.join(base_dir, f)) #сомнительная фигня, надо проверить, пока отключил
    #     new_num = 1
    return os.path.join(base_dir, f"{prefix}_{new_num}.log")


def is_fabric_installed(mc_path: str, vanilla_version: str) -> bool:  # тупо проверка
    try:
        installed = minecraft_launcher_lib.utils.get_installed_versions(mc_path) or []
        for v in installed:
            v_id = v.get("id", "")
            if v_id.startswith("fabric-loader") and vanilla_version in v_id:
                version_dir = os.path.join(mc_path, "versions", v_id)
                json_file = os.path.join(version_dir, f"{v_id}.json")
                jar_file = os.path.join(version_dir, f"{v_id}.jar")
                if os.path.isdir(version_dir) and os.path.isfile(json_file) and os.path.isfile(jar_file):
                    return True
        return False
    except Exception as e:
        print(f"[is_fabric_installed] Ошибка: {e}")
        return False


def is_mc_running() -> bool:  # так лучше т.к нет нагрузки на проц в отличии если перебор процессов
    def enum_callback(hwnd, result):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if "Minecraft" in title and VERSION in title:
                result.append(True)

    found = []
    win32gui.EnumWindows(enum_callback, found)
    return bool(found)


def t(lang, key):
    if key not in translations[lang]:
        return "???"
    return translations[lang].get(key, key)



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

def is_running():
    socket = QLocalSocket()
    socket.connectToServer("countermine_launcher")
    if socket.waitForConnected(100):
        return True
    return False

def create_server(window):
    server = QLocalServer()
    server.removeServer("countermine_launcher")
    server.listen("countermine_launcher")

    def handle_connection():
        client = server.nextPendingConnection()
        client.disconnectFromServer()

        window.showNormal()
        window.activateWindow()
        window.raise_()

    server.newConnection.connect(handle_connection)
    return server

class SwitchButton(QWidget):
    stateChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(52, 28)
        self._checked = False
        self._pos = 4
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._on_color = QColor("#45A049")
        self._off_color = QColor("#777777")

    def isChecked(self):
        return self._checked

    def setOnColor(self, color: str):
        self._on_color = QColor(color)
        self.update()

    def setOffColor(self, color: str):
        self._off_color = QColor(color)
        self.update()

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

        color = self._on_color if self._checked else self._off_color
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
        self._bg_color = QColor("#2E2E2E")
        self._border_color = QColor("#555")
        self._text_color = QColor("white")
        self._hover_color = "#3A3A3A"
        self._selected_color = "#45A049"

    def setBackgroundColor(self, color: str):
        self._bg_color = QColor(color)
        self.update()

    def setBorderColor(self, color: str):
        self._border_color = QColor(color)
        self.update()

    def setTextColor(self, color: str):
        self._text_color = QColor(color)
        self.update()

    def setHoverColor(self, color: str):
        self._hover_color = color

    def setSelectedColor(self, color: str):
        self._selected_color = color

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
        self.popup.setStyleSheet(f"""
            background-color: {self._bg_color.name()};
            border: 1px solid {self._border_color.name()};
            border-radius: 6px;
        """)
        layout = QVBoxLayout(self.popup)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for item in self.items:
            label = QLabel(item)
            label.setStyleSheet(f"""
                QLabel {{
                    color: {self._selected_color if item == self.current else self._text_color.name()};
                    padding: 6px 10px;
                }}
                QLabel:hover {{
                    background-color: {self._hover_color};
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

        painter.setBrush(self._bg_color)
        painter.setPen(self._border_color)
        painter.drawRoundedRect(0, 0, self.width(), 32, 8, 8)

        painter.setPen(self._text_color)
        painter.drawText(12, 21, self.current)

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

        self.setAttribute(Qt.WindowType.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WindowType.WA_TranslucentBackground)
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

from PyQt6.QtWidgets import QLabel, QScrollArea, QWidget, QHBoxLayout
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve

from PyQt6.QtCore import QTimer

class ScrollingNick(QScrollArea):
    def __init__(self, text, width):
        super().__init__()
        self.text = text
        self.setFixedWidth(width)
        self.setFixedHeight(22)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self.container = QWidget()
        self.layout = QHBoxLayout(self.container)
        self.layout.setContentsMargins(0,0,0,0)
        self.layout.setSpacing(0)

        self.label1 = QLabel(text)
        self.label2 = QLabel(2*" "+text)
        for lbl in (self.label1, self.label2):
            lbl.setStyleSheet("color: white;")
        self.layout.addWidget(self.label1)
        self.layout.addWidget(self.label2)
        text_width = self.label1.sizeHint().width()
        self.container.setMinimumWidth(text_width * 2 + 80)

        self.setWidget(self.container)
        self.setWidgetResizable(True)

        self.timer = QTimer()
        self.timer.timeout.connect(self.scroll_step)
        self.scroll_speed = 1
        self.timer.start(60)

    def scroll_step(self):
        if len(self.text) <= 7:
            return
        max_scroll = self.label1.sizeHint().width()
        half_width = max_scroll + self.layout.spacing()
        val = self.horizontalScrollBar().value() + self.scroll_speed
        if val >= half_width:
            val = 0
        self.horizontalScrollBar().setValue(val)

    def setText(self, text):
        self.text = text
        self.label1.setText(text)
        self.label2.setText(2 * " " + text)
        self.label1.adjustSize()
        self.label2.adjustSize()
        text_width = self.label1.sizeHint().width()
        self.container.setMinimumWidth(text_width * 2 + 80)
        self.horizontalScrollBar().setValue(0)



class GlassFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.radius = 22

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("GlassFrame")

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(50)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 130))
        self.setGraphicsEffect(shadow)

        self.setStyleSheet("""
            QFrame#GlassFrame {
                background: transparent;
                border: none;
            }
        """)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect())

        path = QPainterPath()
        path.addRoundedRect(rect, self.radius, self.radius)

        base_gradient = QLinearGradient(0, 0, 0, rect.height())
        base_gradient.setColorAt(0, QColor(255, 255, 255, 70))
        base_gradient.setColorAt(1, QColor(255, 255, 255, 25))

        painter.fillPath(path, base_gradient)

        highlight_rect = rect.adjusted(2, 2, -2, -rect.height() // 2)
        highlight_path = QPainterPath()
        highlight_path.addRoundedRect(highlight_rect, self.radius, self.radius)

        highlight_gradient = QLinearGradient(0, 0, 0, highlight_rect.height())
        highlight_gradient.setColorAt(0, QColor(255, 255, 255, 120))
        highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))

        painter.fillPath(highlight_path, highlight_gradient)
        painter.setPen(QColor(255, 255, 255, 140))
        painter.drawPath(path)

        super().paintEvent(event)