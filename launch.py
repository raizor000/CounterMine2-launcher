# launcher.py
import datetime
import os
import platform
import queue
import re
import shutil
import subprocess
import urllib.request
import uuid
import minecraft_launcher_lib
import psutil
import win32gui
from PyQt6 import QtCore, QtWidgets
from pypresence import Presence

from fetcher import *
from ui import *

APPDATA = os.getenv("APPDATA") or os.path.expanduser("~")
MC_DIR = os.path.join(APPDATA, ".countermine")
MODS_DIR = os.path.join(MC_DIR, "mods")
MODS_CACHE = os.path.join(MC_DIR, "mods_cache")  # Папка с файлами модов
os.makedirs(MODS_DIR, exist_ok=True)
os.makedirs(MODS_CACHE, exist_ok=True)
os.makedirs(MC_DIR, exist_ok=True)
SETTINGS_FILE = os.path.join(MC_DIR, "launcher_settings.json")

VERSION = "1.21.11"


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"memory_heap": 2048, "automem": True}


def save_settings(s):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=4)


settings = load_settings()


def random_username(length=8):
    import random, string
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


def is_version_installed(version: str, mc_path: str) -> bool:
    try:
        installed = minecraft_launcher_lib.utils.get_installed_versions(mc_path) or []
        if not any(v.get("id") == version for v in installed):
            return False

        version_dir = os.path.join(mc_path, "versions", version)
        json_file = os.path.join(version_dir, f"{version}.json")
        jar_file = os.path.join(version_dir, f"{version}.jar")

        return os.path.isdir(version_dir) and os.path.isfile(json_file) and os.path.isfile(jar_file)
    except Exception as e:
        print(f"[is_version_installed] Ошибка: {e}")
        return False

def is_fabric_installed(mc_path, vanilla_version):
    installed = minecraft_launcher_lib.utils.get_installed_versions(mc_path)
    return any(v['id'].startswith("fabric-loader") and vanilla_version in v['id'] for v in installed)

def is_mc_running():
    # ищем java процесс с minecraft в cmdline
    def enum_titles(hwnd, titles):
        text = win32gui.GetWindowText(hwnd)
        if text:
            titles.append(text.lower())
        return True

    window_titles = []
    win32gui.EnumWindows(enum_titles, window_titles)

    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            name = proc.info.get('name') or ""
            if 'java' in name.lower():
                cmd = proc.info.get('cmdline') or []
                if any('minecraft' in str(s).lower() for s in cmd):
                    if any("minecraft 1.21.8" in title for title in window_titles):
                        return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


# ------------ install + progress helpers ------------
_current_max = 0


def get_new_logfile(base_dir, prefix="launcher"):
    # ищем все логи с таким префиксом
    files = [f for f in os.listdir(base_dir) if f.startswith(prefix) and f.endswith(".log")]
    nums = []
    for f in files:
        m = re.match(rf"{prefix}_(\d+)\.log", f)
        if m:
            nums.append(int(m.group(1)))
    new_num = max(nums) + 1 if nums else 1
    if new_num >= 20:
        for f in files:
            os.remove(os.path.join(base_dir, f))
        new_num = 1

    return os.path.join(base_dir, f"{prefix}_{new_num}.log")


def get_new_chatlogfile(base_dir, prefix="chat"):
    # ищем все логи с таким префиксом
    files = [f for f in os.listdir(base_dir) if f.startswith(prefix) and f.endswith(".log")]
    nums = []
    for f in files:
        m = re.match(rf"{prefix}_(\d+)\.log", f)
        if m:
            nums.append(int(m.group(1)))
    new_num = max(nums) + 1 if nums else 1
    if new_num >= 20:
        for f in files:
            os.remove(os.path.join(base_dir, f))
        new_num = 1

    return os.path.join(base_dir, f"{prefix}_{new_num}.log")


def set_max(total):
    """Установить максимальное значение прогресса"""
    global max_value
    max_value = total


def set_status(*args):
    pass


def set_progress(progress, progress_callback):
    """Обновить прогресс, прогресс от 0 до 1"""
    if max_value:
        percent = int((progress / max_value) * 100)
        progress_callback(min(percent, 100))


def download_with_progress(version, mc_path, progress_callback):
    global max_value
    max_value = 0

    def set_progress(progress):
        # если dict -> берём current
        if isinstance(progress, dict):
            progress = progress.get("current", 0)
        try:
            if max_value:
                percent = (progress / max_value) * 100
                progress_callback(f"{percent}%")
        except Exception as e:
            print("Ошибка в set_progress:", e)

    callback = {
        "setStatus": set_status,
        "setProgress": set_progress,
        "setMax": set_max
    }
    try:
        minecraft_launcher_lib.install.install_minecraft_version(
            version, mc_path, callback
        )
    except Exception as e:
        print(e)

    try:
        minecraft_launcher_lib.fabric.install_fabric(version, mc_path, callback=callback)
    except Exception as e:
        print(e)

SERVER_URL = "https://cm2news.xyz/upload"


def send_log_line(msg: str):
    payload = {
        "log": f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg} \n"
    }
    try:
        requests.post(SERVER_URL, json=payload, timeout=3)
    except Exception as e:
        print("Ошибка отправки:", e)


# ------------ Launcher app ------------
class LauncherApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.log_file = get_new_logfile(MC_DIR, "launcher")
        self.setWindowTitle("CounterMine2")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.write_log("Base app built")
        # UI

        self._progress_q = queue.Queue()

        self.thread_pool = QThreadPool()
        self.ui = LauncherUI(self)
        self.setCentralWidget(self.ui)
        self.ui.play_clicked.connect(self.on_play_clicked)
        # self.ui.settings_clicked.connect(self.on_settings_clicked)
        self.write_log("UI loaded")
        self.ui.mod_action.connect(self.handle_mod_action)  # Подключаем сигнал mod_action


        self.ui.header_frame.mousePressEvent = self.start_move
        self.ui.header_frame.mouseMoveEvent = self.do_move
        self.write_log("Binded movements")
        # default options

        self._launching = False
        self._installing = False
        self.downloaded = 0
        self._active_toasts = 0

        nick = random_username()
        self.options = {
            "username": nick,
            "uuid": str(uuid.uuid4()),
            "token": "0",
            "quickPlayMultiplayer": "play.cherry.pizza",
            # "fullscreen": False,
            # "width": "1280",
            # "height": "720",
            "jvm_arguments": [f"-Xmx2g"],
            "launcherName": "CounterMine2 Launcher",
            "launcherVersion": "Beta 1.0",
            "resourcepack": True
        }
        self.write_log(f"Generated nickname - {nick}")
        self.write_log(f"Options - {self.options}")

        # news fetcher
        self.fetcher = Fetcher()
        self.fetcher.newsFetched.connect(self.ui.update_news)
        self.fetcher.onlineFetched.connect(self.ui.update_online_label)
        self.fetcher.fetch_news_async()
        self.write_log("News fetcher started")
        self.fetcher.fetch_online_async()
        self.write_log("Online fetcher started")

        # progress timer (очередь -> UI)
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self._flush_progress_queue)
        self.progress_timer.start(120)
        self.write_log("Progress queue started")

        # mc state timer
        self.mc_timer = QTimer()
        self.mc_timer.timeout.connect(self._check_mc_state)
        self.mc_timer.start(1000)
        self.write_log("State check started")

        self.rpc = None

        self.update_info()

        disk_info = psutil.disk_usage('C:/')
        info = {
            "platform": sys.platform,
            "version": sys.getwindowsversion(),
            "time": time.time(),
            "tz": datetime.datetime.now().astimezone().utcoffset().total_seconds() / 3600,  # смещение в часах
            "cpu": psutil.cpu_stats()._asdict(),
            "cpu_name": platform.processor(),
            # "mem" : psutil.virtual_memory()*1024*1024,
            "disk_total_gb": disk_info.total // (1024 ** 3),
            "disk_used_gb": disk_info.used // (1024 ** 3),
            "disk_free_gb": disk_info.free // (1024 ** 3),
        }
        self.write_log(json.dumps(info, indent=2, ensure_ascii=False))

        try:
            self.rpc = Presence("1418604142422917330")  # <-- твой Application ID
            self.rpc.connect()
            self.rpc.update(
                details="Играет в CounterMine2",
                state="Сервер: play.cherry.pizza",
                large_image="logo2",  # Имя картинки, загруженной в Discord App
                large_text="CounterMine2",
                start=int(time.time()),
                buttons=[
                    {"label": "Сайт", "url": "https://cherry.pizza"},
                    {"label": "Discord", "url": "https://discord.gg/2wbp5aYZtF"}
                ]
            )
            self.write_log(f"Установлена интеграция с дискордом ")
        except Exception:
            self.ui.show_toast(
                "Не удалось установить статус активности в Discord.\nПроверьте, установлен ли Discord и запущен ли он",
                None, self.ui.resource_path("warning.png"))
            self.write_log("Не удалось установить интеграцию с дискордом")
            self.rpc = None

    def update_info(self):
        for file in os.listdir(MODS_DIR):
            if file.endswith(".jar"):
                mod_name = os.path.splitext(file)[0]  # убираем .jar
                self.ui.update_mod_status(mod_name, True)

    def handle_mod_action(self, mod_name: str, action: str):
        """Обработчик действий с модами (установка/удаление)"""
        mod_file = f"{mod_name}.jar"
        mod_dest_path = os.path.join(MODS_DIR, mod_file)
        mod_links = {"ZoomSensitivityFix": "https://cdn.modrinth.com/data/SdthfC23/versions/RVxNUzM5/zoomsensitivityfix-fabric-1.0.1.jar",
                     "Optifine": ["https://mediafilez.forgecdn.net/files/6968/416/OptiFabric%201.21.8-6.8.1.zip", "https://optifine.net/downloadx?f=preview_OptiFine_1.21.8_HD_U_J6_pre16.jar&x=a722cfc0df9895ac7cc508eb8c554886"],
                     "BadOptimizations": "https://cdn.modrinth.com/data/g96Z4WVZ/versions/Zkvk6pH6/BadOptimizations-2.3.0-1.21.6-21.7.jar"}

        try:
            if action == "install":
                self.ui.mod_buttons[mod_name].setEnabled(False)
                urls = mod_links[mod_name]
                if isinstance(urls, str):
                    urls = [urls]  # превращаем одну строку в список

                for url in urls:
                    urllib.request.urlretrieve(url, mod_dest_path)
                self.ui.update_mod_status(mod_name, True)


            elif action == "remove":
                os.remove(MODS_DIR+"/"+mod_file)
                self.ui.update_mod_status(mod_name, False)

        except Exception as e:
            self.ui.show_toast(f"Ошибка при {action} мода {mod_name}: {str(e)}",
                               icon_path=self.ui.resource_path("warning.png"))
            self.write_log(f"Ошибка при {action} мода {mod_name}: {str(e)}")

    def default_memory_mb(self):
        if settings.get("automem", True):
            mem = psutil.virtual_memory()
            total_mb = mem.total // (1024 * 1024)
            available_gb = mem.available / (1024 ** 3)
            if available_gb < 2:
                self.ui.show_toast(
                    f"Не удалось запустить игру \n Слишком мало оперативной памяти \n Необходимо: 2 Гигабайта \n Свободно: {available_gb}",
                    icon_path=self.ui.resource_path("warning.png"))
            if available_gb > 16:
                return min(total_mb // 2, 8192)
            elif available_gb > 8:
                return min(total_mb // 3, 4096)
            else:
                return 2048

        return settings.get("memory_heap", 2048)

    def write_log(self, msg):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {str(msg)}\n")
        try:
            send_log_line(msg)
        except Exception as e:
            print(e)
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] " + msg)

    def on_settings_clicked(self):
        # заглушка — можно реализовать окно настроек
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Настройки", f"Настроек пока нет. Файл: {SETTINGS_FILE}")

    def _flush_progress_queue(self):
        while not self._progress_q.empty():
            try:
                msg = self._progress_q.get_nowait()
            except queue.Empty:
                break
            if msg:
                self.ui.set_play_status(msg)

    def on_play_clicked(self):
        self._launching = True
        self.ui.set_play_enabled(False)
        mem = self.default_memory_mb()
        self.write_log(f"Memory for launching {mem}")
        QtCore.QTimer.singleShot(900, lambda: self._after_memtest(mem))

    def _after_memtest(self, mem):
        self.options['jvm_arguments'] = [f"-Xmx{int(mem)}M"]
        QtCore.QTimer.singleShot(900,
                                 lambda: threading.Thread(target=self._install_and_launch, daemon=True).start())

        # Таймер для обновления UI

    def _install_and_launch(self):
        try:
            os.makedirs(MC_DIR, exist_ok=True)

            def progress_callback(progress):
                # self._progress_q.put(progress)
                self.ui.play_btn.setText(f"Установка {progress}")

            if not is_fabric_installed(MC_DIR, VERSION):
                self._launching = False
                self._installing = True

                # self.show_toast(
                #     "Скорость установки игры зависит от вашего оборудования и скорости интернета.\n"
                #     "Пожалуйста, подождите, пока идет установка.",
                #     icon_path=self.ui.resource_path("warning.png")
                # )

                self.write_log("Начата установка версии " + VERSION)
                download_with_progress(VERSION, MC_DIR, progress_callback)
                self._progress_q.put("Установка завершена")
                self.write_log("Установка завершена")

            # После установки запускаем Minecraft
            self._launching = True
            self._installing = False
            self.write_log("Подготовка запуска " + VERSION)

            fabric_version_id = None
            for v in minecraft_launcher_lib.utils.get_installed_versions(MC_DIR):
                if v["id"].startswith("fabric-loader") and VERSION in v["id"]:
                    fabric_version_id = v["id"]
                    break

            if fabric_version_id:
                cmd = minecraft_launcher_lib.command.get_minecraft_command(fabric_version_id, MC_DIR, self.options)
            else:
                cmd = minecraft_launcher_lib.command.get_minecraft_command(VERSION, MC_DIR, self.options)


            self.write_log("Команда запуска: " + " ".join(cmd))
            with open(get_new_chatlogfile(MC_DIR), "w", encoding="utf-8") as f:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                    encoding="UTF-8"
                )

                for line in process.stdout:
                    print(line)
                    f.write(line.strip() + "\n")  # пишем всё в файл
                    f.flush()

            self.write_log("Процесс запущен")


        except Exception as e:
            print(e)
            # self.write_log(e)
            QtCore.QTimer.singleShot(2000, lambda: self.ui.set_play_enabled(True))

    def _check_mc_state(self):
        running = is_mc_running()

        if running:
            self.ui.set_play_status("Игра запущена")
            self.ui.set_play_enabled(False)
            self._launching = False
            self._installing = False
            self.hide()
        elif self._launching and not self._installing:
            self.ui.set_play_status("Запуск...")
            self.ui.set_play_enabled(False)
        elif self._installing and not self._launching:
            self.ui.set_play_enabled(False)
        else:
            self.show()
            self.ui.set_play_status("Играть")
            self.ui.set_play_enabled(True)

    def start_move(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def do_move(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def minimize_window(self):
        self.showMinimized()


app = QtWidgets.QApplication(sys.argv)
win = LauncherApp()
win.show()
win.raise_()
win.activateWindow()
sys.exit(app.exec())
