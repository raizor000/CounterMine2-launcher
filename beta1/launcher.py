import json
import os
import queue
import random
import shutil
import string
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import dns.resolver
import minecraft_launcher_lib
import psutil
from PyQt6 import QtCore
from mcstatus import JavaServer
from tkinter.messagebox import askokcancel, showinfo, showwarning

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QInputDialog, QFrame
)
from PyQt6.QtGui import QPixmap, QFont, QCursor
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtCore import QSize, QUrl
from PyQt6.QtGui import QDesktopServices, QIcon

def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

mc_path = os.path.join(os.getenv("APPDATA"), ".countermine")
if not os.path.exists(mc_path):
    os.makedirs(mc_path, exist_ok=True)

settings_file = os.path.join(mc_path, "launcher_settings.json")
version = "1.21.11"


def random_username(length=8):
    """Генерирует случайный никнейм из букв и цифр."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

nick = random_username()
# Опции запуска
options = {
    "username": f"{nick}",               # ник
    "uuid": f"{uuid.uuid5(uuid.uuid4(), nick)}",                         # для оффлайн режима
    "token": "0",                         # оффлайн токен
    "server": "play.cherry.pizza",      # сервер
    "port": 25565,                       # порт сервера
    "fullscreen": False,                 # полноэкранный режим
    "width": 1280,
    "height": 720,
    "jvm_arguments": ["-Xmx2G"],         # память для игры
    "resourcepack": True                 # скачивание ресурспаков
}
options = {k: str(v) if isinstance(v, int) else v for k, v in options.items()}
progress_queue = queue.Queue()

def load_settings():
    if os.path.exists(settings_file):
        with open(settings_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_settings(data):
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


if not os.path.exists(settings_file):
    save_settings({
        "memory_heap": 2048,
        "automem": True
    })
settings = load_settings()
def default_memory_mb():
    # если auto-подбор включен
    if settings.get("automem", True):
        mem = psutil.virtual_memory()
        used_percent = mem.percent
        free_mb = mem.available // (1024 * 1024)
        if used_percent > 50:
            mem_mb = free_mb // 4
        else:
            mem_mb = (mem.total // (1024 * 1024)) // 4
        # округление кратно 4
        mem_mb = (mem_mb // 4) * 4
        return mem_mb
    # иначе используем сохранённую память
    return settings.get("memory_heap", 2048)

def is_mc_running():
    for proc in psutil.process_iter(['name', 'pid', 'cmdline']):
        try:
            if 'java' in proc.info['name'].lower() and any('minecraft' in s.lower() for s in proc.info['cmdline']):
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

current_max = 0
debug = False

def set_max(new_max: int):
    global current_max
    current_max = new_max

def set_status(status):
    if debug:
        print(status)

def download_with_progress(version, mc_path, progress_callback):
    def safe_progress(progress):
        """
        Преобразуем входные аргументы в float от 0 до 1
        """

        if current_max != 0:
            progress_callback(str(progress)+"/"+str(current_max))

    callback = {
        "setStatus": set_status,
        "setProgress": safe_progress,
        "setMax": set_max
    }
    minecraft_launcher_lib.install.install_minecraft_version(version, mc_path, callback)

def is_version_installed(version: str, mc_path: str) -> bool:
    installed = minecraft_launcher_lib.utils.get_installed_versions(mc_path)
    return any(v["id"] == version for v in installed)

class Launcher(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.old_pos = None
        self.mc_state = "idle"
        self.download_progress = 0
        self.mc_timer = QTimer()
        self.mc_timer.timeout.connect(self.check_mc_state)
        self.mc_timer.start(2000)  # проверяем каждую секунду

    def check_mc_loop(self):
        if self.mc_state == "downloading":
            self.play_btn.setEnabled(False)
        elif self.mc_state == "starting":
            self.play_btn.setText("Запуск...")
            self.play_btn.setEnabled(False)
        elif self.mc_state == "memtest":
            self.mc_state = "memtest"
            self.play_btn.setText("Подбор памяти...")
            self.play_btn.setEnabled(False)
            mem = default_memory_mb()  # считаем сразу
            QTimer.singleShot(1300, lambda: self.play_btn.setText(f"Подбор: {mem} мб"))
            self.mc_state = "starting"
        elif is_mc_running() and self.mc_state != "starting" and self.mc_state != "memtest":
            self.mc_state = "running"
            self.play_btn.setText("Игра уже запущена")
            self.play_btn.setEnabled(False)
        else:
            self.mc_state = "idle"
            self.play_btn.setText("Играть")
            self.play_btn.setEnabled(True)



    def update_online_status(self):
        try:
            server = JavaServer.lookup("play.cherry.pizza")
            status = server.status()
            self.online_label.setText(f"ИГРАЮТ {status.players.online} ЧЕЛ.")
        except (TimeoutError, ConnectionError, ConnectionResetError, ConnectionRefusedError, ConnectionAbortedError):
            self.online_label.setText("ИГРАЮТ - ЧЕЛ.")

    def start_mc_checker(self):
        self.mc_timer = QtCore.QTimer()
        self.mc_timer.timeout.connect(lambda: self.check_mc_loop())
        self.mc_timer.start(1000)  # проверяем каждые 2 секунды



    def check_mc_state(self):
        running = is_mc_running()

        if self.mc_state == "downloading":
            self.play_btn.setEnabled(False)
        elif self.mc_state == "starting":
            # проверяем реально ли процесс запущен
            if running and self.mc_state != "memtest":
                self.mc_state = "running"
                self.play_btn.setText("Игра запущена")
                self.play_btn.setEnabled(False)
            else:
                # ещё не запущен, оставляем текст
                self.play_btn.setText("Запуск...")
                self.play_btn.setEnabled(False)

        elif self.mc_state == "memtest":
            self.mc_state = "memtest"
            self.play_btn.setText("Подбор памяти...")
            self.play_btn.setEnabled(False)
            mem = default_memory_mb()  # считаем сразу
            QTimer.singleShot(1300, lambda: self.play_btn.setText(f"Подбор: {mem} мб"))
            QTimer.singleShot(1500, lambda: setattr(self, "mc_state", "starting"))

        elif running and self.mc_state != "memtest":
            self.mc_state = "running"
            self.play_btn.setText("Игра запущена")
            self.play_btn.setEnabled(False)
        else:
            self.mc_state = "idle"
            self.play_btn.setText("Играть")
            self.play_btn.setEnabled(True)

    def init_ui(self):
        screen = QApplication.primaryScreen()
        screen_width = screen.size().width()
        screen_height = screen.size().height()

        window_width = int(screen_width * 0.4)
        window_height = int(window_width * 9 / 16)
        self.setGeometry(
            (screen_width - window_width) // 2,
            (screen_height - window_height) // 2,
            window_width, window_height
        )
        self.setWindowTitle("Counter`Mine2")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setFixedSize(window_width, window_height)
        try:
            server = JavaServer.lookup("play.cherry.pizza")
            status = server.status()
            print(f"Статус: Онлайн")
            print(f"Игроков: {status.players.online}/{status.players.max}")
        except (TimeoutError, ConnectionError, ConnectionResetError, ConnectionRefusedError, ConnectionAbortedError, dns.resolver.LifetimeTimeout, dns.resolver.NoNameservers):
            print("Не удается получить информацию о сервере!")
            print(f"Игроков: 0/0")
            status = "-"


        # Фон
        pixmap = QPixmap(resource_path("background.jpg")).scaled(
            window_width, window_height, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.bg_label = QLabel(self)
        self.bg_label.setPixmap(pixmap)
        self.bg_label.setGeometry(0, 0, window_width, window_height)


        # ================= Хедер =================
        self.header_frame = QFrame(self)
        self.header_frame.setGeometry(0, 0, window_width, 40)
        self.header_frame.setStyleSheet("background-color: rgba(50,50,50,200);")
        # self.header_frame.setCursor(QCursor(Qt.SizeAllCursor))

        # Кнопки закрытия и сворачивания
        close_btn = QPushButton("✕", self.header_frame)
        close_btn.setFont(QFont("sans-serif", 11, QFont.Weight.Bold))
        close_btn.setStyleSheet("""
            QPushButton {background-color: transparent; color: red; border: none;}
            QPushButton:hover {color: darkred;}
        """)
        close_btn.setGeometry(window_width - 40, 5, 30, 30)
        close_btn.clicked.connect(self.close)

        minimize_btn = QPushButton("—", self.header_frame)
        minimize_btn.setFont(QFont("sans-serif", 11, QFont.Weight.Bold))
        minimize_btn.setStyleSheet("""
            QPushButton {background-color: transparent; color: yellow; border: none;}
            QPushButton:hover {color: gray;}
        """)
        minimize_btn.setGeometry(window_width - 80, 5, 30, 30)
        minimize_btn.clicked.connect(self.showMinimized)

        pixmap_logo = QPixmap(resource_path("4.png"))
        self.logo_label = QLabel(self.header_frame)  # родитель — хедер
        self.logo_label.setPixmap(pixmap_logo)
        self.logo_label.setGeometry(10, 8, 168, 24)  # x=10, y=5, ширина=168, высота=24
        self.logo_label.setScaledContents(True)  # картинка растягивается под размер QLabel

        # online_layout.addWidget(self.online_label, alignment=Qt.AlignVCenter | Qt.AlignLeft)

        self.header_frame.mousePressEvent = self.start_move
        self.header_frame.mouseMoveEvent = self.do_move



        # ================= Онлайн блок =================

        # размеры и позиция блока
        block_width = 400  # фиксированная ширина
        block_x = 20
        block_y = 60

        # Родительский фрейм
        self.news_block = QFrame(self)
        self.news_block.setStyleSheet("""
            QFrame {
                background-color: rgba(50, 50, 50, 200);  /* менее прозрачный */
                border-radius: 10px;
            }
        """)
        self.news_block.setFrameShape(QFrame.Shape.StyledPanel)
        self.news_block.setGeometry(block_x, block_y, block_width, 10)  # высота временно 10

        # Заголовок
        self.news_title = QLabel("🎉 Обновление (Релиз 38.1)", self.news_block)
        self.news_title.setStyleSheet("color: white;")
        self.news_title.setFont(QFont("sans-serif", 18))
        self.news_title.setWordWrap(True)
        self.news_title.setFixedWidth(block_width - 20)  # внутренние отступы
        self.news_title.adjustSize()
        self.news_title.move(10, 10)

        # Текст
        self.news_text = QLabel(
            "- Переработана защита после респавна\n"
            "- После движения время защиты сокращается до 1 секунды\n"
            "- Добавлена защита на разминку в обычном режиме\n"
            "- Добавлен эффект позволяющий понять, что ты под защитой",
            self.news_block
        )
        self.news_text.setStyleSheet("color: white;")
        self.news_text.setFont(QFont("sans-serif", 14))
        self.news_text.setWordWrap(True)
        self.news_text.setFixedWidth(block_width - 20)
        self.news_text.move(10, self.news_title.height() + 15)  # 15px между заголовком и текстом
        self.news_text.adjustSize()

        # Динамическая высота блока
        block_height = self.news_text.y() + self.news_text.height() + 10
        self.news_block.setFixedHeight(block_height)

        button_size = 48
        spacing = 10
        top_offset = 60
        bottom_offset = 30
        right_offset = 20

        # Ссылки
        VK = "https://vk.com/countermine"
        DC = "https://discord.com/invite/counter-mine-2-935258545170047006"
        YT = "https://www.youtube.com/@CounterMine2"
        TG = "https://t.me/countermine2"
        CP = "https://cherry.pizza/"
        SETTINGS = "#"  # твоя ссылка на настройки

        # Создаем фрейм затемнения для кнопок
        # Высота блока = расстояние от верхней первой до нижней последней кнопки + отступы
        block_top = top_offset
        block_bottom = self.height() - bottom_offset - button_size
        block_height = block_bottom - block_top + button_size
        block_width = button_size + 4  # чуть больше кнопки, padding
        self.buttons_block = QFrame(self)
        self.buttons_block.setGeometry(
            self.width() - right_offset - block_width - 20,  # смещаем блок на 20 пикселей влево
            block_top,
            block_width + 20,  # увеличиваем ширину блока, чтобы кнопки остались внутри
            block_height + 20
        )

        self.buttons_block.setStyleSheet("""
            QFrame {
                background-color: rgba(50, 50, 50, 200);
                border-radius: 10px;
                padding: 2px;
            }
        """)

        # Функция создания кнопки
        def create_social_button(icon_path, link, parent, x, y):
            btn = QPushButton(parent)
            btn.setGeometry(x, y, button_size, button_size)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet("""
                QPushButton {
                    border: none;
                    background-color: #323232;
                }
                QPushButton:hover {
                    background-color: #454545;
                }
            """)
            btn.setIcon(QIcon(resource_path(icon_path)))
            btn.setIconSize(QSize(button_size, button_size))
            btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(link)))
            return btn

        # Первые 5 кнопок сверху
        icons_top = [TG, YT, DC, VK, CP]
        icon_files_top = ["tg.png", "yt.png", "dc.png", "vk.png", "cp.png"]
        for i, link in enumerate(icons_top):
            y_pos = i * (button_size + spacing)
            create_social_button(icon_files_top[i], link, self.buttons_block, 12, y_pos+10)

        # Последняя кнопка (Настройки) снизу
        create_social_button("settings.png", SETTINGS, self.buttons_block, 12, block_height - button_size)


        #блок2
        online_frame_width = 241
        online_frame_height = 64
        self.online_frame = QFrame(self)
        self.online_frame.setGeometry(
            20,  # слева
            window_height - 0 - online_frame_height - 10,
            online_frame_width,
            online_frame_height
        )
        self.online_frame.setStyleSheet("background-color: #323232; border: 2px solid #323232; border-radius: 8px;")

        online_layout = QHBoxLayout(self.online_frame)
        online_layout.setContentsMargins(10, 5, 10, 5)
        online_layout.setSpacing(10)

        # Гифка слева через QMovie
        from PyQt6.QtGui import QMovie
        self.online_gif_label = QLabel()
        movie = QMovie(resource_path("3.gif"))
        movie.setScaledSize(QtCore.QSize(55, 50))  # оставляем гифку почти в оригинале
        self.online_gif_label.setMovie(movie)
        movie.start()
        online_layout.addWidget(self.online_gif_label, alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        # Текст справа от гифки
        if status != "-":
            self.online_label = QLabel(f"ИГРАЮТ {status.players.online} ЧЕЛ.")
            self.online_label.setStyleSheet("color: white; font-weight: bold;")
            self.online_label.setFont(QFont("sans-serif", 11))
            online_layout.addWidget(self.online_label, alignment=Qt.AlignmentFlag | Qt.AlignmentFlag.AlignLeft)
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_online_status)
            self.timer.start(1000)
        else:
            self.online_label = QLabel(f"ИГРАЮТ - ЧЕЛ.")
            self.online_label.setStyleSheet("color: white; font-weight: bold;")
            self.online_label.setFont(QFont("sans-serif", 11))
            # self.play_btn.setEnabled(False)
            online_layout.addWidget(self.online_label, alignment=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)


        # ------------------ Play Button справа от экрана ------------------



        def play():
            self.mc_state = "downloading"
            self.download_progress = 0
            self.play_btn.setEnabled(False)


            def update_progress(progress):
                self.mc_state = "downloading"
                self.play_btn.setText(f"Загрузка {progress}")



            def start():


                if not is_version_installed("1.21.8", mc_path):
                    download_with_progress(version, mc_path, update_progress)
                else:
                    self.mc_state = "starting"

                # Команда запуска
                self.mc_state = "memtest"
                options['jvm_arguments'] = default_memory_mb()
                print(options['jvm_arguments'])
                cmd = minecraft_launcher_lib.command.get_minecraft_command(version, mc_path, options)



                # Запуск Minecraft

                self.mc_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


            threading.Thread(target=start, daemon=True).start()

            # if not hasattr(self, "mc_ui_timer"):
            #     self.mc_ui_timer = QTimer()
            #     self.mc_ui_timer.timeout.connect(self.update_mc_button)
            #     self.mc_ui_timer.start(500)

        right_margin = 120  # отступ от правого края, можно менять

        play_frame_width = 240
        play_frame_height = online_frame_height  # совпадает с блоком онлайн

        self.play_frame = QFrame(self)
        self.play_frame.setGeometry(
            self.width() - play_frame_width - right_margin,  # позиция по X с учётом отступа
            window_height - play_frame_height - 10,  # позиция по Y (от нижнего края)
            play_frame_width,
            play_frame_height
        )
        self.play_frame.setStyleSheet("background-color: rgba(0,0,0,0);")  # прозрачный фон

        # Кнопка
        self.play_btn = QPushButton("Играть", self.play_frame)
        self.play_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.play_btn.setFont(QFont("sans-serif", 13, QFont.Weight.Bold))
        self.play_btn.setStyleSheet("""
            QPushButton {
                background-color: #45A049;
                color: white;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #45a800;
            }
            QPushButton:disabled {
                background-color: #2e6b35;  /* темнее, когда неактивна  */
                color: #aaa;                 /* серый текст */
            }
        """)
        self.play_btn.setGeometry(0, 0, play_frame_width, play_frame_height)
        self.play_btn.clicked.connect(play)
        if status == "-":
            self.play_btn.setEnabled(False)
        # self.start_mc_checker()


        # Кнопка Играть
        play_btn = QPushButton("Играть", self)
        play_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        play_btn.setFont(QFont("sans-serif", 15, QFont.Weight.Bold))
        play_btn.setStyleSheet("""
            QPushButton {
                background-color: #57c200;
                color: white;
                border-radius: 25px;
                padding: 10px 25px;
            }
            QPushButton:hover {
                background-color: #45a800;
            }
        """)
        play_btn.setFixedHeight(50)
        play_btn.adjustSize()
        play_btn.move(window_width - play_btn.width() - 20, window_height - 0 + 5)
        play_btn.raise_()

    # ================= Драг окна за хедер =================
    def start_move(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPos()

    def do_move(self, event):
        if self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()




def download_java(url):
    path = os.path.join(tempfile.gettempdir(), "jdk17.exe")
    os.system(f'curl -L -o "{path}" "{url}"')
    return path

def setup_jre(url):
    file_path = download_java(url)
    showwarning("CounterMine2 Launcher", "После установки Java 17 на устройство перезапустите Лаунчер")
    subprocess.Popen([file_path], shell=True, encoding="UTF-8")

def is_java_installed():
    if shutil.which("java"):
        result = subprocess.run(
            ["java", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        output = result.stdout + result.stderr
        if "17" in output:
            return True
        else:
            return False
    else:
        return False

def check_java():
    if not is_java_installed():
        if askokcancel("CounterMine 2 Launcher", "Необходима установка Java 17 для работы игры. Установить её?"):
            if sys.platform.startswith("win"):
                url = "https://download.oracle.com/java/17/archive/jdk-17.0.12_windows-x64_bin.exe"
                jdwthread = threading.Thread(target=setup_jre, args=(url, ), daemon=True)
                jdwthread.start()
                jdwthread.join()
                sys.exit(0)
            else:
                showinfo("CounterMine 2 Launcher", f"Сожалеем, но мы не можем автоматически установить Java 17 на вашу операционную систему {sys.platform}")
                sys.exit(0)
        else:
            sys.exit(0)
    else:
        launcher.show()



app = QApplication(sys.argv)
launcher = Launcher()
# check_java()
launcher.show()
sys.exit(app.exec())
