# main.py
import gzip
import io
import os.path
import queue
import urllib.request
import zipfile

import minecraft_launcher_lib.types
from PyQt6 import QtCore
from PyQt6.QtCore import QThreadPool
from packaging import version
from pypresence import Presence

from scripts.fetcher import *
from scripts.ui import *
from scripts.utilties import *


class LauncherApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.banned = False
        self.MC_DIR = str(MC_DIR)
        self.LAUNCHER_DIR = LAUNCHER_DIR
        self.current_version = LAUNCHER_VERSION
        self.ip = get_external_ip()
        self.log_file = get_new_logfile(self.MC_DIR)
        self.software_machine_id = generate_software_machine_id()

        self.setWindowTitle("CounterMine2")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.write_log("Base app built")

        self._progress_q = queue.Queue()
        self.thread_pool = QThreadPool()

        self.ui = LauncherUI(self.current_version, self.ip, self)
        self.setCentralWidget(self.ui)
        self.ui._setup_mods_search()
        self.write_log("UI loaded")
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
        self.options = minecraft_launcher_lib.types.MinecraftOptions(
            username=nick,
            uuid=str(uuid.uuid4()),
            token="0",
            quickPlayMultiplayer="play.cherry.pizza",
            jvmArguments=["-Xmx2g"],
            launcherName="CounterMine2 Launcher",
            launcherVersion=self.current_version,
            resourcepack=True
        )
        self.write_log(f"Generated nickname - {nick}")
        self.write_log(f"Options - {self.options}")

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
        self.ban_timer.start(10000)
        self.write_log("Ban check timer started")

        self.mc_timer = QTimer()
        # noinspection PyUnresolvedReferences
        self.mc_timer.timeout.connect(self._check_mc_state)
        self.mc_timer.start(1000)
        self.write_log("State check started")

        self.output_file = os.path.join(LAUNCHER_DIR,
                                        f"{self.ui.ip}-{datetime.datetime.now().strftime('%d/%m/%y-%H:%M:%S')}.mp4")
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

        self.server_url = get_server_url()
        self.updates_endpoint = f"{self.server_url}/updates/latest.json"
        self.updates_download_base = f"{self.server_url}/updates/downloader/"
        QtCore.QTimer.singleShot(1000, self.check_for_updates)

        self.connect_signals()
        self.stream_thread = None
        self.ws = None
        self.sio = None
        self.stream_active = False
        self.video_queue = queue.Queue()
        self.audio_queue = queue.Queue()
        self.ffmpeg_process = None
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

    def check_for_updates(self):
        try:
            self.write_log("Проверка обновлений...")
            response = requests.get(self.updates_endpoint, timeout=10)
            response.raise_for_status()
            data = response.json()
            latest_version = data["version"]

            if version.parse(latest_version) > version.parse(self.current_version):
                self.write_log(f"Доступно обновление: {latest_version}")
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "CounterMine2",
                    f"Доступна новая версия лаунчера - {latest_version}\n\nИзменения:\n{data.get('changelog', 'Общие улучшения')}\n\nЗагрузить и установить?",
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.Yes
                )
                if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                    self.perform_update(data)
            else:
                self.write_log("Лаунчер актуален")
        except requests.exceptions.RequestException as e:
            self.write_log(f"Ошибка проверки обновлений: {e}")
        except Exception as e:
            self.write_log(f"Неожиданная ошибка OTA: {e}")

    def perform_update(self, update_data):
        """Скачивание, распаковка и установка обновления"""
        version = update_data["version"]
        url = update_data["download_url_downloader"]
        path = os.path.join(self.LAUNCHER_DIR, f"CounterMine2_installer.exe")
        try:
            self.ui.set_play_status("Скачивание обновления...")
            if os.path.exists(path):
                os.remove(path)
            self.write_log(f"Скачивание: {url}")

            response = requests.get(url, stream=True, timeout=10)
            response.raise_for_status()
            with open(path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            with open(path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()



            if file_hash.lower() != update_data["checksum_downloader"].lower():
                self.ui.show_toast(f"Файл поврежден! Обновление отменено", timeout=15000)
                return

            self.ui.show_toast(f"Обновление {version} скачано. Перезапуск...", timeout=15000)
            time.sleep(3)
            subprocess.Popen(
                [path, "--update"],  # Команда с аргументом
                cwd=self.LAUNCHER_DIR,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
                shell=False  # Без shell для чистоты
            )
        except Exception as e:
            self.write_log(f"Ошибка обновления: {e}")
            if os.path.exists(path):
                os.remove(path)
            self.ui.show_toast(
                f"Ошибка установки обновления: {e}",
                icon_path=self.ui.resource_path("assets/warning.png"),
                timeout=10000
            )
            self.ui.set_play_status("Играть")

    def connect_signals(self):
        self.ui.play_clicked.connect(self.on_play_clicked)
        self.ui.reinstall_client.connect(self.reinstall_client)
        self.ui.mod_action.connect(self.handle_mod_action)

    def update_rpc(self, online):
        global details
        try:
            details = "Играет в CounterMine2"
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

                else:
                    details = "Играет с приватного лаунчера"
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
        is_banned_ip = str(ip).strip() in list(banned_ips)
        is_banned_hwid = str(self.software_machine_id) in list(get_banned_hwids())

        is_banned = is_banned_ip or is_banned_hwid
        if is_banned and not self.banned:
            if self.software_machine_id not in get_banned_hwids():
                add_banned_hwid(self.software_machine_id)
            self.banned = True
            self.ui.set_play_status("[НЕТ ДОСТУПА]")
            self.ui.play_btn.setEnabled(False)
            self.ui.tab_mods_btn.hide()
            self.ui.tab_settings_btn.hide()
            self.ui.tab_news_btn.hide()
            self.ui.tab_moderator_btn.hide()
            self.ui.tab_installed_mods_btn.hide()
            self.ui.reinstall_btn.hide()
            self.ui._switch_tab(0)
            self.ui.show_toast(
                "Вы были забанены! \nЕсли вы считаете бан несправедливым - \nсвяжитесь с Администрацией в течении 72 часов. ",
                None,
                icon_path=self.ui.resource_path("assets/warning.png"))
        elif not is_banned and self.banned:
            self.banned = False
            self.ui.set_play_status("Играть")
            self.ui.play_btn.setEnabled(True)
            self.ui.tab_mods_btn.show()
            self.ui.reinstall_btn.show()
            for toast in getattr(self.ui, "_toast_widgets", []):
                try:
                    toast.destroy()
                except Exception:
                    pass

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
                for file in os.listdir(self.MC_DIR):
                    file_path = os.path.join(self.MC_DIR, file)
                    if Path(file_path) != MODS_DIR:
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
                self._install_and_launch()

            threading.Thread(target=process_delete, daemon=True).start()

    def update_mod_info(self, specific_slug=None):
        if specific_slug:
            is_installed = is_mod_installed(self.MC_DIR, specific_slug)
            if specific_slug in self.ui.mod_buttons:
                self.ui.update_mod_status(specific_slug, is_installed)
        else:
            installed_slugs = set()
            mods_dir = os.path.join(self.MC_DIR, "mods")
            if os.path.exists(mods_dir):
                for file in os.listdir(mods_dir):
                    if file.endswith(".jar"):
                        base_name = os.path.splitext(file)[0]
                        slug = base_name.rsplit('-', 1)[0] if '-' in base_name else base_name
                        installed_slugs.add(slug)
            for slug in self.ui.mod_buttons:
                is_installed = slug in installed_slugs
                self.ui.update_mod_status(slug, is_installed)
        QtWidgets.QApplication.processEvents()

    def handle_mod_action(self, mod_slug: str, action: str):
        try:
            print(f"Действие: {action} для мода {mod_slug}")
            mods_dir_path = os.path.join(self.MC_DIR, "mods")

            if action == "install":
                if mod_slug in self.ui.mod_buttons:
                    self.ui.mod_buttons[mod_slug].setEnabled(False)
                    QtWidgets.QApplication.processEvents()

                # Получаем последнюю версию
                loaders_str = '[\"fabric\"]'
                game_versions_str = f'[\"{VERSION}\"]'
                version_url = f"https://api.modrinth.com/v2/project/{mod_slug}/version?loaders={urllib.parse.quote(loaders_str)}&game_versions={urllib.parse.quote(game_versions_str)}"
                print(f"Debug URL: {version_url}")
                with urllib.request.urlopen(version_url) as response:
                    vdata = json.loads(response.read().decode('utf-8'))

                if not vdata:
                    raise Exception(f"Нет совместимой версии для Fabric {VERSION}")

                latest = vdata[0]
                files = latest['files']
                primary_file = next((f for f in files if f.get('primary', False)), files[0])
                download_url = primary_file['url']
                filename = primary_file['filename']

                mod_dest_path = os.path.join(mods_dir_path, filename)
                urllib.request.urlretrieve(download_url, mod_dest_path)
                self.write_log(f"Установлен мод {mod_slug}: {filename}")
                self.ui.update_mod_status(mod_slug, "install")
            elif action == "remove":
                removed = 0
                for file in os.listdir(mods_dir_path):
                    if file.endswith('.jar') and (mod_slug in file or mod_slug.lower() in file.lower()):
                        os.remove(os.path.join(mods_dir_path, file))
                        removed += 1
                if removed > 0:
                    self.write_log(f"Удалено {removed} файлов для мода {mod_slug}")
                    self.ui.update_mod_status(mod_slug, "remove")
                else:
                    self.write_log(f"Файлы для мода {mod_slug} не найдены")

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
            self.options['jvmArguments'] = [f"-Xmx{int(mem)}M"]
            QtCore.QTimer.singleShot(100,
                                     lambda: threading.Thread(target=self._install_and_launch, daemon=True).start())

    def check_for_xray(self):
        found_rp_name = None
        try:
            for entry in os.scandir(RP_DIR):
                if entry.is_file() or entry.is_dir():
                    name = entry.name.lower()
                    if "xray" in name or "x-ray" in name:
                        found_rp_name = entry.name
                        break
        except Exception:
            return 0
        if not found_rp_name:
            return 0
        try:
            rp_list = sorted(os.listdir(RP_DIR))
        except Exception:
            rp_list = [found_rp_name]
        for log_entry in os.scandir(LOGS_DIR):
            if log_entry.is_dir():
                continue
            log_path = log_entry.path
            try:
                open_mode_text = "rt"
                open_func = gzip.open if log_entry.name.endswith(".gz") else open
                with open_func(log_path, open_mode_text, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if "xray" in line.lower():
                            ts = int(time.time())
                            formatted_time = f"<t:{ts}:T>"
                            ip = getattr(self, "ip", "unknown")
                            rp_preview = "\n ".join(rp_list)
                            if len(rp_preview) > 800:
                                rp_preview = rp_preview[:780] + "…"
                            embed = {
                                "title": "Обнаружен xray",
                                "description": f"Найден resource-pack: `{found_rp_name}`\nВремя: {formatted_time}",
                                "fields": [
                                    {"name": "IP компьютера", "value": ip, "inline": True},
                                    {"name": "Список ресурспаков", "value": rp_preview or "—", "inline": False},
                                    {"name": "Лог (файл)", "value": log_entry.name, "inline": True},
                                ],
                                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ts))
                            }
                            files = {}
                            file_handles = []
                            try:
                                fh_log = open(log_path, "rb")
                                files["log_file"] = (log_entry.name, fh_log)
                                file_handles.append(fh_log)
                            except Exception:
                                pass
                            rp_path = os.path.join(RP_DIR, found_rp_name)
                            try:
                                if os.path.isfile(rp_path):
                                    fh_rp = open(rp_path, "rb")
                                    files["rp_file"] = (found_rp_name, fh_rp)
                                    file_handles.append(fh_rp)
                                elif os.path.isdir(rp_path):
                                    bio = io.BytesIO()
                                    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
                                        for root, _, fnames in os.walk(rp_path):
                                            for fname in fnames:
                                                full = os.path.join(root, fname)
                                                arcname = os.path.relpath(full, rp_path)
                                                try:
                                                    zf.write(full, arcname)
                                                except Exception:
                                                    continue
                                    bio.seek(0)
                                    files["rp_file"] = (f"{found_rp_name}.zip", bio.read())
                            except Exception:
                                pass
                            payload = {"embeds": [embed]}
                            try:
                                payload_json = {"payload_json": json.dumps(payload)}
                                multipart = {}
                                multipart.update(payload_json)
                                files_for_requests = {}
                                for key, val in files.items():
                                    if isinstance(val, tuple):
                                        files_for_requests[key] = val
                                    else:
                                        continue
                                requests.post(WEBHOOK_URL, data=payload_json, files=files_for_requests, timeout=15)
                            except Exception:
                                pass
                            finally:
                                for fh in file_handles:
                                    try:
                                        fh.close()
                                    except Exception:
                                        pass
                            print("xray обнаружен")
                            return -1
            except Exception:
                continue
        return 0

    def _install_and_launch(self):

        try:
            def progress_callback(progress):
                self.ui.play_btn.setText(f"Установка {progress}")
            if not is_fabric_installed(self.MC_DIR, VERSION):
                self._launching = False
                self._installing = True

                self.write_log("Начата установка версии " + VERSION)
                download_with_progress(VERSION, self.MC_DIR, progress_callback)
                self._progress_q.put("Установка завершена")
                self.write_log("Установка завершена")

            self._launching = True
            self._installing = False
            self.write_log("Подготовка запуска " + VERSION)

            fabric_version_id = None
            for v in minecraft_launcher_lib.utils.get_installed_versions(self.MC_DIR):
                if v["id"].startswith("fabric-loader") and VERSION in v["id"]:
                    fabric_version_id = v["id"]
                    break

            if fabric_version_id:
                # noinspection PyTypeChecker
                cmd = minecraft_launcher_lib.command.get_minecraft_command(fabric_version_id, self.MC_DIR, self.options)
            else:
                # noinspection PyTypeChecker
                cmd = minecraft_launcher_lib.command.get_minecraft_command(VERSION, self.MC_DIR, self.options)

            self.write_log("Команда запуска: " + " ".join(cmd))

            with open(get_new_logfile(self.MC_DIR, "game"), "w", encoding="utf-8") as f:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=self.MC_DIR,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0 | subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                    encoding="UTF-8"
                )
                self.write_log("Процесс запущен")

                for line in self.process.stdout:
                    # print(line)
                    f.write(line.strip() + "\n")
                    f.flush()

            self.write_log("Процесс завершен")
            self.check_for_xray()


        except Exception as e:
            print(e)

    def _check_mc_state(self):
        running = is_mc_running()

        if running:
            self.ui.set_play_status("Игра запущена")
            self.ui.set_play_enabled(False)
            self._launching = False
            self._installing = False
            self.hide()
            if self.banned:
                try:
                    self.process.kill()
                    self.ui.set_play_status("[НЕТ ДОСТУПА]")
                    self.ui.play_btn.setEnabled(False)
                except Exception as e:
                    print(e)
        elif self._launching and not self._installing:
            self.ui.set_play_status("Запуск...")
            self.ui.set_play_enabled(False)
            if self.banned:
                try:
                    self.process.kill()
                    self.ui.set_play_status("[НЕТ ДОСТУПА]")
                    self.ui.play_btn.setEnabled(False)
                except Exception as e:
                    print(e)
        elif self._installing and not self._launching:
            self.ui.set_play_enabled(False)
            if self.banned:
                try:
                    self.process.kill()
                    self.ui.set_play_status("[НЕТ ДОСТУПА]")
                    self.ui.play_btn.setEnabled(False)
                except Exception as e:
                    print(e)
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
