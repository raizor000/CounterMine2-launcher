# launcher.py
import platform
import queue
import subprocess
import threading
import urllib.request
import uuid

from PyQt6 import QtCore
from pypresence import Presence

from scripts.fetcher import *
from scripts.ui import *
from scripts.utilties import *

APPDATA = os.getenv("APPDATA") or os.path.expanduser("~")
MC_DIR = os.path.join(APPDATA, ".countermine")
MODS_DIR = os.path.join(MC_DIR, "mods")
MODS_CACHE = os.path.join(MC_DIR, "mods_cache")
os.makedirs(MODS_DIR, exist_ok=True)
os.makedirs(MODS_CACHE, exist_ok=True)
os.makedirs(MC_DIR, exist_ok=True)

VERSION = "1.21.8"


class LauncherApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.banned = False
        self.MC_DIR = MC_DIR
        self.log_file = get_new_logfile(MC_DIR)

        self.setWindowTitle("CounterMine2")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.write_log("Base app built")

        self._progress_q = queue.Queue()
        self.thread_pool = QThreadPool()

        self.ui = LauncherUI(self)
        self.setCentralWidget(self.ui)
        # self.ui.play_clicked.connect(self.on_play_clicked)
        self.write_log("UI loaded")
        # self.ui.mod_action.connect(self.handle_mod_action)
        # self.ui.reinstall_client.connect(self.reinstall_client)
        self.setWindowIcon(QIcon(self.ui.resource_path("assets/icon.ico")))

        self.ui.header_frame.mousePressEvent = self.start_move
        self.ui.header_frame.mouseMoveEvent = self.do_move
        self.write_log("Binded movements")

        self.old_pos = None
        self._launching = False
        self._deleting = False
        self._installing = False
        self.downloaded = 0
        self._active_toasts = 0

        nick = random_username()
        self.options = {
            "username": nick,
            "uuid": str(uuid.uuid4()),  # Добавляем UUID
            "token": "0",
            "quickPlayMultiplayer": "play.cherry.pizza",
            "jvm_arguments": [f"-Xmx2g"],
            "launcherName": "CounterMine2 Launcher",
            "launcherVersion": "Beta 1.0",
            "resourcepack": True
        }
        self.write_log(f"Generated nickname - {nick}")
        self.write_log(f"Options - {self.options}")
        self.load_initial_settings()  # Вызываем после полной инициализации options


        self.fetcher = Fetcher()
        self.fetcher.newsFetched.connect(self.ui.update_news)
        self.fetcher.onlineFetched.connect(self.ui.update_online_label)
        self.fetcher.fetch_news_async()
        self.write_log("News fetcher started")
        self.fetcher.fetch_online_async()
        self.write_log("Online fetcher started")

        self.progress_timer = QTimer()
        # noinspection PyUnresolvedReferences
        self.progress_timer.timeout.connect(self._flush_progress_queue)
        self.progress_timer.start(120)
        self.write_log("Progress queue started")

        self.ban_timer = QTimer()
        self.ban_timer.timeout.connect(self.check_for_ban)
        self.ban_timer.start(180000)
        self.write_log("Ban check timer started")

        self.mc_timer = QTimer()
        # noinspection PyUnresolvedReferences
        self.mc_timer.timeout.connect(self._check_mc_state)
        self.mc_timer.start(1000)
        self.write_log("State check started")

        self.rpc = None
        self.stream_process = None

        self.update_mod_info()

        disk_info = psutil.disk_usage('C:/')
        info = {
            "platform": sys.platform,
            "version": sys.getwindowsversion(),
            "time": time.time(),
            "tz": datetime.datetime.now().astimezone().utcoffset().total_seconds() / 3600,
            "cpu": psutil.cpu_stats()._asdict(),
            "cpu_name": platform.processor(),
            "disk_total_gb": disk_info.total // (1024 ** 3),
            "disk_used_gb": disk_info.used // (1024 ** 3),
            "disk_free_gb": disk_info.free // (1024 ** 3),
        }
        self.write_log(json.dumps(info, indent=2, ensure_ascii=False))

        self.connect_signals()
        try:
            self.rpc = Presence("1418604142422917330")
            self.rpc.connect()
            self.update_rpc(online=0)
            self.rpc.update(
                details="Играет в CounterMine2",
                state="Сервер: play.cherry.pizza",
                large_image="logo2",
                large_text="CounterMine2",
                start=int(time.time()),
                buttons=[
                    {"label": "Сайт", "url": "https://cherry.pizza"},
                    {"label": "Discord", "url": "https://discord.gg/2wbp5aYZtF"}
                ]
            )
            self.write_log(f"Установлена интеграция с дискордом ")
        except Exception as e:
            if not self.banned:
                self.ui.show_toast(
                    "Не удалось установить статус активности в Discord.\nПроверьте, установлен ли Discord и запущен ли он",
                    None, self.ui.resource_path("assets/warning.png"))
                self.write_log("Не удалось установить интеграцию с дискордом")
                self.rpc = None
                print(e)

    def connect_signals(self):
        """Подключение сигналов из LauncherUI"""
        self.ui.play_clicked.connect(self.on_play_clicked)
        self.ui.reinstall_client.connect(self.reinstall_client)
        self.ui.mod_action.connect(self.handle_mod_action)
        self.ui.nickname_changed.connect(self.update_nickname)
        self.ui.fullscreen_changed.connect(self.update_fullscreen)
        self.ui.window_size_changed.connect(self.update_window_size)
        self.ui.reset_settings.connect(self.reset_settings)

    def read_launcher_options(self):
        """Чтение настроек из launcher_options.txt"""
        options_file = os.path.join(self.MC_DIR, "launcher_options.txt")
        settings = {}
        try:
            if os.path.exists(options_file):
                with open(options_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if ":" in line:
                            key, value = line.strip().split(":", 1)
                            settings[key] = value
            return settings
        except Exception as e:
            self.write_log(f"Ошибка чтения launcher_options.txt: {e}")
            return settings

    def write_launcher_options(self, updates):
        """Обновление launcher_options.txt с новыми настройками"""
        options_file = os.path.join(self.MC_DIR, "launcher_options.txt")
        settings = self.read_launcher_options()
        settings.update(updates)
        try:
            os.makedirs(self.MC_DIR, exist_ok=True)
            with open(options_file, "w", encoding="utf-8") as f:
                for key, value in settings.items():
                    f.write(f"{key}:{value}\n")
            self.write_log(f"Настройки сохранены в launcher_options.txt: {updates}")
        except Exception as e:
            self.write_log(f"Ошибка записи launcher_options.txt: {e}")
            self.ui.show_toast(
                f"Ошибка сохранения настроек: {e}",
                icon_path=self.ui.resource_path("assets/error.png")
            )

    def update_nickname(self, nickname):
        """Обновление никнейма"""
        if nickname.strip():
            self.options["username"] = nickname
            self.write_launcher_options({"username": nickname})
            self.write_log(f"Никнейм обновлен: {nickname}")
        else:
            self.ui.show_toast(
                "Никнейм не может быть пустым",
                icon_path=self.ui.resource_path("assets/warning.png")
            )
            self.write_log("Попытка установить пустой никнейм")

    def update_fullscreen(self, enabled):
        self.write_launcher_options({"fullScreen": "true" if enabled else "false"})
        self.write_log(f"Полноэкранный режим: {'true' if enabled else 'false'}")

    def update_window_size(self, size):
        if size:
            width, height = map(int, size.split("x"))
            self.write_launcher_options({"screenWidth": str(width), "screenHeight": str(height)})
            self.write_log(f"Размер окна обновлен: {size}")

    def reset_settings(self):
        default_settings = {
            "username": self.options["username"],
            "fullScreen": "false",
            "screenWidth": "1280",
            "screenHeight": "720"
        }
        self.write_launcher_options(default_settings)
        self.ui.nickname_edit.setText(self.options["username"])
        self.ui.fullscreen_checkbox.setChecked(False)
        self.ui.window_size_combo.setCurrentText("1280x720")
        self.ui.show_toast("Настройки сброшены", timeout=5000)
        self.write_log("Настройки сброшены к значениям по умолчанию")

    def load_initial_settings(self):
        settings = self.read_launcher_options()
        if "username" in settings:
            self.options["username"] = settings["username"]
            self.ui.nickname_edit.setText(settings["username"])
        else:
            self.ui.nickname_edit.setText(self.options["username"])
        if "fullScreen" in settings:
            self.ui.fullscreen_checkbox.setChecked(settings["fullScreen"].lower() == "true")
        else:
            self.ui.fullscreen_checkbox.setChecked(False)
        if "screenWidth" in settings and "screenHeight" in settings:
            size = f"{settings['screenWidth']}x{settings['screenHeight']}"
            if size in [self.ui.window_size_combo.itemText(i) for i in range(self.ui.window_size_combo.count())]:
                self.ui.window_size_combo.setCurrentText(size)
            else:
                self.ui.window_size_combo.setCurrentText("1280x720")
        else:
            self.ui.window_size_combo.setCurrentText("1280x720")
        self.write_log("Начальные настройки загружены")

    def update_rpc(self, online):
        try:
            if is_mc_running():
                details = "Играет в CounterMine2"
                state = f"Сервер: play.cherry.pizza | Онлайн: {online}"
            else:
                if self.ui.mods_page.isVisible():
                    details = "Просматривает страницу Модов"
                elif self.ui.news_page.isVisible():
                    details = "Просматривает Главную страницу"

                if self._launching:
                    details = "Заходит в игру..."

                state = f"Онлайн на сервере: {online}"

            self.rpc.update(
                details=details,
                state=state,
                large_image="logo2",
                large_text="CounterMine2",
                start=int(time.time()),
                buttons=[
                    {"label": "Сайт", "url": "https://cherry.pizza"},
                    {"label": "Discord", "url": "https://discord.gg/2wbp5aYZtF"}
                ]
            )
            self.write_log(f"RPC обновлен: {details} | {state}")
        except Exception as e:
            self.write_log(f"Ошибка обновления RPC: {e}")


    def check_for_ban(self):
        ip = get_external_ip()
        banned_ips = get_banned_ips()
        is_banned = str(ip.strip()) in list(banned_ips)

        if is_banned and not self.banned:
            self.banned = True
            self.ui.set_play_status("[НЕТ ДОСТУПА]")
            self.ui.play_btn.setEnabled(False)
            self.ui.tab_mods_btn.hide()
            self.ui.reinstall_btn.hide()
            self.ui.show_toast(
                "Вы были забанены! \nЕсли вы считаете бан несправедливым - \nсвяжитесь с Администрацией в течении 72 часов. ",
                None,
                icon_path=self.ui.resource_path("assets/warning.png"))
            self.write_log(f"Бан активирован для IP: {ip}")
            if self.stream_process:
                self.stream_process.terminate()
                self.stream_process = None
                self.write_log("FFmpeg streaming stopped due to ban")

        elif not is_banned and self.banned:
            self.banned = False
            self.ui.set_play_status("Играть")
            self.ui.play_btn.setEnabled(True)
            self.ui.tab_mods_btn.show()
            self.ui.reinstall_btn.show()
            for toast in self.ui._toast_widgets:
                toast.destroy()
            self.write_log(f"Бан снят для IP: {ip}")


    def reinstall_client(self):
        reply = QtWidgets.QMessageBox.question(
            self,
            "Подтверждение переустановки",
            "Вы уверены, что хотите переустановить клиент? Данное действие нельзя отменить. \n\n✕ Переустановка НЕ затронет папку модов",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.Yes
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self._deleting = True
            QtCore.QTimer.singleShot(0,
                                     lambda: self.ui.set_play_status("Очистка..."))
            time.sleep(0.2)
            def process_delete():
                for file in os.listdir(MC_DIR):
                    file_path = os.path.join(MC_DIR, file)
                    if file_path != MODS_DIR:
                        try:
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                            elif os.path.isdir(file_path):
                                import shutil
                                shutil.rmtree(file_path)
                        except Exception as e:
                            self.write_log(f"Ошибка при удалении файла/папки {file}: {str(e)}")
                            return

                self.write_log("Все файлы и папки в каталоге удалены")
                self._deleting = False
                self.on_play_clicked()

            threading.Thread(target=process_delete, daemon=True).start()

    def update_mod_info(self, specific_slug=None):
        """Сканирует mods_dir и обновляет статусы по slug. Если specific_slug указан, обновляет только его."""
        if specific_slug:
            # Обновляем только указанный мод
            is_installed = is_mod_installed(MC_DIR, specific_slug)
            if specific_slug in self.ui.mod_buttons:
                self.ui.update_mod_status(specific_slug, is_installed)
        else:
            # Обновляем все моды (используется при начальной загрузке или поиске)
            installed_slugs = set()
            mods_dir = os.path.join(MC_DIR, "mods")
            if os.path.exists(mods_dir):
                for file in os.listdir(mods_dir):
                    if file.endswith(".jar"):
                        base_name = os.path.splitext(file)[0]
                        slug = base_name.rsplit('-', 1)[0] if '-' in base_name else base_name
                        installed_slugs.add(slug)
            for slug in self.ui.mod_buttons:
                is_installed = slug in installed_slugs
                self.ui.update_mod_status(slug, is_installed)
        QtWidgets.QApplication.processEvents()  # Обновляем UI

    def handle_mod_action(self, mod_slug: str, action: str):
        """Обработка установки/удаления мода с Modrinth API."""
        try:
            print(action)
            if action == "install":
                # Отключаем кнопку
                if mod_slug in self.ui.mod_buttons:
                    self.ui.mod_buttons[mod_slug].setEnabled(False)
                    QtWidgets.QApplication.processEvents()  # Обновляем UI немедленно

                # Получаем последнюю версию
                loaders_str = '[\"fabric\"]'
                game_versions_str = '[\"1.21.8\"]'
                version_url = f"https://api.modrinth.com/v2/project/{mod_slug}/version?loaders={urllib.parse.quote(loaders_str)}&game_versions={urllib.parse.quote(game_versions_str)}"
                print(f"Debug URL: {version_url}")  # Для отладки, удалите позже
                with urllib.request.urlopen(version_url) as response:
                    vdata = json.loads(response.read().decode('utf-8'))

                if not vdata:
                    raise Exception("Нет совместимой версии для Fabric 1.21.8")

                latest = vdata[0]
                files = latest['files']
                # Берем primary файл или первый
                primary_file = next((f for f in files if f.get('primary', False)), files[0])
                download_url = primary_file['url']
                filename = primary_file['filename']

                mod_dest_path = os.path.join(MODS_DIR, filename)
                urllib.request.urlretrieve(download_url, mod_dest_path)
                self.write_log(f"Установлен мод {mod_slug}: {filename}")
                self.ui.update_mod_status(mod_slug, True)

            elif action == "remove":
                mods_dir_path = os.path.join(MC_DIR, "mods")
                removed = 0
                for file in os.listdir(mods_dir_path):
                    if file.startswith(mod_slug + '-') and file.endswith('.jar'):
                        os.remove(os.path.join(mods_dir_path, file))
                        removed += 1
                if removed > 0:
                    self.write_log(f"Удалено {removed} файлов для мода {mod_slug}")
                    self.ui.update_mod_status(mod_slug, False)
                else:
                    self.write_log(f"Файлы для мода {mod_slug} не найдены")

            # time.sleep(0.3)
            # self.update_mod_info()
        except Exception as e:
            if action == "install" and mod_slug in self.ui.mod_buttons:
                self.ui.mod_buttons[mod_slug].setEnabled(True)
            self.ui.show_toast(f"Ошибка при {action} мода {mod_slug}: {str(e)}",
                               icon_path=self.ui.resource_path("assets/warning.png"))
            self.write_log(f"Ошибка при {action} мода {mod_slug}: {str(e)}")

    def default_memory_mb(self):
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

    def write_log(self, msg):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {str(msg)}\n")
        # try:
        #     send_log_line(msg, SERVER_URL)
        # except Exception as e:
        #     print(e)
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] " + msg)

    def _flush_progress_queue(self):
        while not self._progress_q.empty():
            try:
                msg = self._progress_q.get_nowait()
            except queue.Empty:
                break
            if msg:
                self.ui.set_play_status(msg)

    def on_play_clicked(self):
        if not self.banned:
            self._launching = True
            self.ui.set_play_enabled(False)
            mem = self.default_memory_mb()
            self.write_log(f"Memory for launching {mem}")
            self.options['jvm_arguments'] = [f"-Xmx{int(mem)}M"]
            QtCore.QTimer.singleShot(100,
                                     lambda: threading.Thread(target=self._install_and_launch, daemon=True).start())

    def _install_and_launch(self):
        try:
            os.makedirs(MC_DIR, exist_ok=True)

            def progress_callback(progress):
                self.ui.play_btn.setText(f"Установка {progress}")

            if not is_fabric_installed(MC_DIR, VERSION):
                self._launching = False
                self._installing = True

                self.write_log("Начата установка версии " + VERSION)
                download_with_progress(VERSION, MC_DIR, progress_callback)
                self._progress_q.put("Установка завершена")
                self.write_log("Установка завершена")

            self._launching = True
            self._installing = False
            self.write_log("Подготовка запуска " + VERSION)

            settings = self.read_launcher_options()
            if "username" in settings:
                self.options["username"] = settings["username"]
            jvm_args = self.options["jvm_arguments"]
            if "screenWidth" in settings and "screenHeight" in settings:
                jvm_args.append(f"-Dminecraft.window.width={settings['screenWidth']}")
                jvm_args.append(f"-Dminecraft.window.height={settings['screenHeight']}")
            if "fullScreen" in settings and settings["fullScreen"].lower() == "true":
                jvm_args.append("-Dminecraft.fullscreen=true")
            self.options["jvm_arguments"] = jvm_args

            fabric_version_id = None
            for v in minecraft_launcher_lib.utils.get_installed_versions(MC_DIR):
                if v["id"].startswith("fabric-loader") and VERSION in v["id"]:
                    fabric_version_id = v["id"]
                    break

            if fabric_version_id:
                # noinspection PyTypeChecker
                cmd = minecraft_launcher_lib.command.get_minecraft_command(fabric_version_id, MC_DIR, self.options)
            else:
                # noinspection PyTypeChecker
                cmd = minecraft_launcher_lib.command.get_minecraft_command(VERSION, MC_DIR, self.options)

            self.write_log("Команда запуска: " + " ".join(cmd))



            with open(get_new_logfile(MC_DIR, "game"), "w", encoding="utf-8") as f:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                    encoding="UTF-8"
                )
                self.write_log("Процесс запущен")

                for line in process.stdout:
                    print(line)
                    f.write(line.strip() + "\n")
                    f.flush()

            self.write_log("Процесс завершен")


        except Exception as e:
            print(e)

    def _check_mc_state(self):
        running = is_mc_running()

        if running:
            self.ui.set_play_status("Игра запущена")
            self.ui.set_play_enabled(False)
            self._launching = False
            self._installing = False
            # if not self.banned and not self.stream_process:
            #     try:
            #         # MODIFIED: Use exact or partial window title for Minecraft
            #         window_title = get_window_titles()
            #         print(window_title)# Adjust based on actual title
            #         ffmpeg_cmd = [
            #             'ffmpeg',
            #             '-f', 'gdigrab' if platform.system() == "Windows" else 'x11grab',
            #             '-i', f'title={window_title[0]}' if platform.system() == "Windows" else ':0.0',
            #
            #             '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
            #             '-b:v', '1500k', '-maxrate', '1500k', '-bufsize', '3000k',
            #             '-vf', 'scale=1280:720',  # 720p for bandwidth (~450 MB/hour)
            #             '-r', '30', '-g', '60',
            #             '-f', 'flv', f'rtmp://cm2news.xyz/live/game_{self.options["uuid"]}'
            #         ]
            #         self.stream_process = subprocess.Popen(
            #             ffmpeg_cmd,
            #             stdout=subprocess.PIPE,
            #             stderr=subprocess.STDOUT,
            #             text=True,
            #             creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            #         )
            #         self.write_log(f"Started FFmpeg streaming for UUID {self.options['uuid']}")
            #
            #         # NEW: Log FFmpeg output asynchronously
            #         def log_ffmpeg_output():
            #             for line in self.stream_process.stdout:
            #                 self.write_log(f"FFmpeg: {line.strip()}")
            #
            #         threading.Thread(target=log_ffmpeg_output, daemon=True).start()
            #     except Exception as e:
            #         self.write_log(f"Failed to start FFmpeg streaming: {e}")
            #         self.ui.show_toast(
            #             "Не удалось запустить стрим. Убедитесь, что FFmpeg установлен и окно Minecraft открыто.",
            #             None, self.ui.resource_path("assets/warning.png"))
            self.hide()
        elif self._launching and not self._installing:
            self.ui.set_play_status("Запуск...")
            self.ui.set_play_enabled(False)
        elif self._installing and not self._launching:
            self.ui.set_play_enabled(False)
        elif self._deleting and not self._launching:
            self.ui.set_play_status("Очистка...")
            self.ui.set_play_enabled(False)
        else:
            self.show()
            if not self.banned:
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
