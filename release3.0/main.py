# main.py
import gzip
import io
import os.path
import urllib.request
import zipfile

import minecraft_launcher_lib.types
import pygame.mixer
from PyQt5 import QtCore
from PyQt5.QtWidgets import QMessageBox
from packaging import version
from pypresence import Presence

from scripts.fetcher import *
from scripts.ui import *
from scripts.utilties import *


class LauncherApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        pygame.mixer.init()

        self.sound_enabled = False
        self.check_for_updates_perm = True
        self.hidef = False
        self.enable_rpc = True
        self.nickname = None
        self.lang = "ru_ru"
        self.occupied_last = None
        self.banned = False
        self.dynamicbg = False
        self.moretabs = False
        self.MC_DIR = str(MC_DIR)
        self.LAUNCHER_DIR = LAUNCHER_DIR
        self.current_version = LAUNCHER_VERSION
        self.ip = get_external_ip()
        self.log_file = get_new_logfile(self.MC_DIR)

        self.setWindowTitle("CounterMine2")
        self.setWindowFlags(Qt.FramelessWindowHint)

        self.write_log("Base app built")
        self.fetcher = Fetcher()
        self.ui = LauncherUI(self.current_version, self.ip, self.lang, self.dynamicbg, self)
        self.load_settings()
        self.ui.update_ui(self.lang, self.dynamicbg, self.moretabs)
        self.ui.setup_mods_search()
        self.ui.setup_mods_label()
        self.write_log("UI loaded")
        self.setWindowIcon(QIcon(self.ui.resource_path("assets/icon.ico")))
        self.setCentralWidget(self.ui)

        self.old_pos = None
        self._launching = False
        self._deleting = False
        self._installing = False

        self.fetcher.set_lang(self.lang)
        self.fetcher.fetch_news_async()
        self.write_log("News fetcher started")
        self.fetcher.fetch_online_async()
        self.write_log("Online fetcher started")
        self.fetcher.fetch_queue_async()
        self.write_log("Queue fetcher started")
        self.fetcher.fetch_ban_async()
        self.write_log("Ban fetcher started")



        self.ui.header_frame.mousePressEvent = self.start_move
        self.ui.header_frame.mouseMoveEvent = self.do_move
        self.write_log("Binded movements")

        nick = self.nickname
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
        self.write_log(f"Options - {self.options}")

        self.connect_signals()

        self.mc_timer = QTimer()
        self.mc_timer.timeout.connect(self._check_mc_state)
        self.mc_timer.start(2000)
        self.write_log("State check started")

        self.rpc = None

        threading.Thread(target=self.update_mod_info(), daemon=True).start()

        threading.Thread(target=self.dump_info, daemon=True).start()

        threading.Thread(target=self.get_updates, daemon=True).start()

        if self.hidef:
            self.ui.waitlist.hide()
        else:
            self.ui.waitlist.show()

        if self.enable_rpc:
            threading.Thread(target=self.update_rpc(), daemon=True).start()

    def get_updates(self):
        self.server_url = get_server_url()
        self.updates_endpoint = f"{self.server_url}/updates/latest.json"
        self.updates_download_base = f"{self.server_url}/updates/downloader/"
        QtCore.QTimer.singleShot(300, self.check_for_updates)


    def dump_info(self):
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

    def on_settings_changed(self, key: str, value: object):
        try:
            if key == "nickname":
                self.nickname = str(value).strip()
                self.save_settings()
                self.options = minecraft_launcher_lib.types.MinecraftOptions(
                    username=self.nickname,
                    uuid=str(uuid.uuid4()),
                    token="0",
                    quickPlayMultiplayer="play.cherry.pizza",
                    jvmArguments=["-Xmx2g"],
                    launcherName="CounterMine2 Launcher",
                    launcherVersion=self.current_version,
                    resourcepack=True
                )

            elif key == "sound_enabled":
                self.sound_enabled = bool(value)
                if value:
                    pygame.mixer.music.load(self.ui.resource_path("assets/qjoin.mp3"))
                    pygame.mixer.music.play(fade_ms=1500)
                    pygame.mixer.music.set_volume(1)
                else:
                    pygame.mixer.music.load(self.ui.resource_path("assets/qleave.mp3"))
                    pygame.mixer.music.play(fade_ms=1000)
                    pygame.mixer.music.set_volume(1)
                self.save_settings()
                status = "включён" if self.sound_enabled else "выключен"
                self.write_log(f"[Настройки] Звук: {status}")

            elif key == "hide_faceit":
                self.hidef = not bool(value)
                self.save_settings()
                self.ui.show_faceit = not self.hidef

            elif key == "lang":
                match value:
                    case "English":
                        self.lang = "en_us"
                    case "Русский":
                        self.lang = "ru_ru"
                self.save_settings()
                self.ui.update_ui(self.lang, self.dynamicbg, self.moretabs)
                self.fetcher.set_lang(self.lang)

            elif key == "moretabs":
                self.moretabs = bool(value)
                self.ui.moretabs_switch.setChecked(bool(self.moretabs))
                if not self.moretabs:
                    self.ui.tab_resourcepacks_btn.hide()
                    self.ui.tab_shaders_btn.hide()
                else:
                    self.ui.tab_resourcepacks_btn.show()
                    self.ui.tab_shaders_btn.show()

                self.save_settings()

            elif key == "update":
                self.check_for_updates_perm = bool(value)
                self.save_settings()


            elif key == "rpc":
                self.enable_rpc = bool(value)
                if bool(value):
                    threading.Thread(target=self.update_rpc, daemon=True).start()
                else:
                    threading.Thread(target=self.update_rpc, args=[False,], daemon=True).start()
                self.save_settings()
        except Exception as e:
            self.write_log(str(e))

    def update_queue_ui(self, player_names):
        occupied = len(player_names)
        if self.occupied_last is None:
            self.occupied_last = occupied
        if occupied > self.occupied_last and self.sound_enabled:
            pygame.mixer.music.load(self.ui.resource_path("assets/qjoin.mp3"))
            pygame.mixer.music.play(fade_ms=1500)
            pygame.mixer.music.set_volume(1.5)
        elif occupied < self.occupied_last and self.sound_enabled:
            pygame.mixer.music.load(self.ui.resource_path("assets/qleave.mp3"))
            pygame.mixer.music.play(fade_ms=1000)
            pygame.mixer.music.set_volume(1)
        self.occupied_last = occupied
        self.ui.update_queue(occupied, 10)
        self.ui.update_names(occupied, player_names)

    def check_for_updates(self):
        try:
            if not self.check_for_updates_perm:
                return
            self.write_log("Проверка обновлений...")
            response = requests.get(self.updates_endpoint, timeout=3)
            response.raise_for_status()
            data = response.json()
            latest_version = data["version"]

            if version.parse(latest_version) > version.parse(self.current_version):
                self.write_log(f"Доступно обновление: {latest_version}")
                reply = QtWidgets.QMessageBox.question(
                    self,
                    "CounterMine2",
                    f"Доступна новая версия лаунчера - {latest_version}\n\nИзменения:\n{data.get('changelog', 'Общие улучшения')}\n\nЗагрузить и установить?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.Yes
                )
                if reply == QtWidgets.QMessageBox.Yes:
                    self.perform_update(data)
            else:
                self.write_log("Лаунчер актуален")
        except requests.exceptions.RequestException as e:
            self.write_log(f"Ошибка проверки обновлений: {str(e)}")
        except Exception as e:
            self.write_log(f"Неожиданная ошибка OTA: {str(e)}")

    def perform_update(self, update_data):
        version = update_data["version"]
        url = update_data["download_url_downloader"]
        path = os.path.join(self.LAUNCHER_DIR, f"CounterMine2_installer.exe")
        try:
            self.ui.set_play_status(t(self.lang, "download_update_status"))
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
                return
            self.submit_logfile()
            time.sleep(2)
            subprocess.Popen(
                [path, "--update"],
                cwd=self.LAUNCHER_DIR,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
                shell=False
            )
        except Exception as e:
            self.write_log(f"Ошибка обновления: {str(e)}")
            if os.path.exists(path):
                os.remove(path)
            self.ui.set_play_status("Играть")

    def save_settings(self):
        settings = {
            "nickname": self.nickname,
            "sound_enabled": self.sound_enabled,
            "hide_faceit": self.hidef,
            "lang": self.lang,
            "update_auto": self.check_for_updates_perm,
            "rpc": self.enable_rpc,
            "bg": True,
            "moretabs": self.moretabs
        }
        try:
            with open(LAUNCHER_DIR / "settings.json", "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            try:
                if os.path.exists(MC_DIR / "options.txt"):
                    with open(MC_DIR / "options.txt", "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        for i, line in enumerate(lines):
                            if line.startswith("lang:"):
                                lines[i] = f"lang:{self.lang}\n"
                                break
                        with open(MC_DIR / "options.txt", "w", encoding="utf-8") as f:
                            f.writelines(lines)
            except Exception as e:
                self.write_log(f"options.txt err - {str(e)}")
        except Exception as e:
            self.write_log(f"Ошибка сохранения настроек: {str(e)}")

    def load_settings(self):
        try:
            if not os.path.exists(LAUNCHER_DIR/"settings.json"):
                self.save_settings()

            with open(LAUNCHER_DIR / "settings.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                nick = data.get("nickname", "")
                sound = data.get("sound_enabled", True)
                hidef = data.get("hide_faceit", False)
                lang = data.get("lang", "ru_ru")
                update = data.get("update_auto", True)
                rpc = data.get("rpc", True)
                bg = data.get("bg", True)
                moretabs = data.get("moretabs", False)

                if nick:
                    self.nickname = nick
                    self.ui.nickname_input.setText(nick)
                self.sound_enabled = sound
                self.ui.sound_switch.setChecked(sound)
                self.hidef = hidef
                self.lang = lang
                self.fetcher.set_lang(lang)
                if self.hidef:
                    self.ui.waitlist.hide()
                else:
                    self.ui.waitlist.show()
                self.check_for_updates_perm = update
                self.ui.show_faceit = not self.hidef
                self.ui.hide_faceit_switch.setChecked(not bool(hidef))
                self.ui.update_switch.setChecked(bool(update))
                self.ui.rpc_switch.setChecked(rpc)
                self.ui.moretabs_switch.setChecked(bool(moretabs))
                self.enable_rpc = rpc
                self.moretabs = moretabs
                self.dynamicbg = bg
                self.ui.lang_dropdown.current = "Русский" if self.lang == "ru_ru" else "English"

        except FileNotFoundError:
            self.write_log("Файл настроек не найден — используются значения по умолчанию")
        except Exception as e:
            print(f"Ошибка загрузки настроек: {str(e)}")

    def connect_signals(self):
        self.ui.play_clicked.connect(self.on_play_clicked)
        self.ui.reinstall_client.connect(self.reinstall_client)
        self.ui.mod_action.connect(self.handle_mod_action)
        self.ui.settings_changed.connect(self.on_settings_changed)
        self.ui.shader_action.connect(self.handle_shader_action)
        self.ui.resourcepack_action.connect(self.handle_resourcepack_action)

        self.fetcher.newsFetched.connect(self.ui.update_news)
        self.fetcher.onlineFetched.connect(self.ui.update_online_and_ping_labels)
        self.fetcher.queueFetched.connect(self.update_queue_ui)
        self.fetcher.banFetched.connect(self.do_ban)

    def update_rpc(self, enable=True):
        global details
        if enable:
            if not self.rpc:
                try:
                    self.rpc = Presence("1418604142422917330")
                    self.rpc.connect()
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
                    self.rpc = None
                    self.write_log(str(e))
            if self.rpc:
                try:
                    details = "Играет в CounterMine2"
                    state = f"Сервер: play.cherry.pizza"
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
                    self.rpc = None
                    self.write_log(f"Ошибка обновления RPC: {str(e)}")
        else:
            try:
                if self.rpc:
                    self.rpc.close()
            except Exception: pass
            self.rpc = None

    def do_ban(self, is_banned, hwids, machine_id):
        if is_banned and not self.banned:
            if machine_id not in hwids:
                add_banned_hwid(machine_id)

            self.banned = True
            self.ui.set_play_status(t(self.lang, "no_permission"))
            self.ui.play_btn.setEnabled(False)
            self.ui.tab_mods_btn.hide()
            self.ui.tab_settings_btn.hide()
            self.ui.tab_news_btn.hide()
            self.ui.tab_installed_mods_btn.hide()
            self.ui.reinstall_btn.hide()
            self.ui._switch_tab(0)

        elif not is_banned and self.banned:
            self.banned = False
            self.ui.set_play_status(t(self.lang, "play_button"))
            self.ui.play_btn.setEnabled(True)
            self.ui.tab_mods_btn.show()
            self.ui.reinstall_btn.show()

    def reinstall_client(self):
        reply = QtWidgets.QMessageBox.question(
            self,
            t(self.lang, "reinstall_title"),
            t(self.lang, "reinstall_text"),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes
        )

        if reply == QtWidgets.QMessageBox.Yes:
            self._deleting = True
            QtCore.QTimer.singleShot(0,
                                     lambda: self.ui.set_play_status(t(self.lang, "cleanup_status")))
            time.sleep(0.2)

            def process_delete():
                for file in os.listdir(self.MC_DIR):
                    file_path = os.path.join(self.MC_DIR, file)
                    if Path(file_path) != MODS_DIR and Path(file_path) != Path(self.log_file):
                        try:
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                            elif os.path.isdir(file_path):
                                import shutil
                                shutil.rmtree(file_path)
                        except Exception as e:
                            self.write_log(f"Ошибка при удалении файла/папки {file}: {str(e)}")
                            continue

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
            self.write_log(f"Действие: {action} для мода {mod_slug}")
            mods_dir_path = os.path.join(self.MC_DIR, "mods")

            if action == "install":
                if mod_slug in self.ui.mod_buttons:
                    self.ui.mod_buttons[mod_slug].setEnabled(False)
                    QtWidgets.QApplication.processEvents()

                loaders_str = '[\"fabric\"]'
                game_versions_str = f'[\"{VERSION}\"]'
                version_url = f"https://api.modrinth.com/v2/project/{mod_slug}/version?loaders={urllib.parse.quote(loaders_str)}&game_versions={urllib.parse.quote(game_versions_str)}"
                self.write_log(f"Debug URL: {version_url}")
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

            self.write_log(f"Ошибка при {action} мода {mod_slug}: {str(e)}")

    def default_memory_mb(self):
        mem = psutil.virtual_memory()
        total_mb = mem.total // (1024 * 1024)
        available_gb = mem.available / (1024 ** 3)
        if available_gb < 2:
            msg = QMessageBox(self)
            msg.setWindowTitle(t(self.lang, "not_enough_mem_title"))
            msg.setText(
                t(self.lang, "not_enough_mem_text".format(free=available_gb))
            )
            msg.setIcon(QMessageBox.Warning)
            msg.exec_()
            return 0

        if available_gb > 16:
            return min(total_mb // 2, 8192)
        elif available_gb > 8:
            return min(total_mb // 3, 4096)
        else:
            return 2048

    def write_log(self, msg):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {str(msg)}\n")
            f.flush()
            f.close()

    def on_play_clicked(self):
        if not self.banned:
            self._launching = True
            self.ui.set_play_enabled(False)
            mem = self.default_memory_mb()
            if mem == 0:
                self._launching = False
                return
            self.write_log(f"Memory for launching {mem}")
            self.options['jvmArguments'] = [f"-Xmx{int(mem)}M"]
            QtCore.QTimer.singleShot(100,
                                     lambda: threading.Thread(target=self._install_and_launch, daemon=True).start())

    def submit_logfile(self):
        ts = int(time.time())
        formatted_time = f"<t:{ts}:T>"
        ip = getattr(self, "ip", "unknown")

        embed = {
            "title": "Лог",
            "description": f"\nВремя: {formatted_time}",
            "fields": [
                {"name": "IP компьютера", "value": ip, "inline": True},
            ],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(ts))
        }
        files = {}
        file_handles = []
        try:
            fh_log = open(self.log_file, "rb")
            files["file"] = (os.path.basename(self.log_file), fh_log)
            file_handles.append(fh_log)
            payload = {"embeds": [embed]}
            resp = requests.post(
                LOGS_WEBHOOK_URL,
                data={"payload_json": json.dumps(payload)},
                files=files,
                timeout=15
            )
            self.write_log("posted" if resp.ok else f"failed ({resp.status_code})")
        except Exception as e:
            self.write_log(f"Error submitting logfile: {str(e)}")
        finally:
            for fh in file_handles:
                fh.close()

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
                                    {"name": "Список всех ресурспаков", "value": rp_preview or "—", "inline": False},
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
                            return -1
            except Exception:
                continue
        return 0

    def _install_and_launch(self):
        try:
            if not self.nickname:
                self.ui.play_btn.setText(t(self.lang, "no_nick_found"))
                return 1

            def progress_callback(progress):
                self.ui.play_btn.setText(f"{t(self.lang, 'install_status')} {progress}")

            if not is_fabric_installed(self.MC_DIR, VERSION):
                self._launching = False
                self._installing = True

                self.write_log("Начата установка версии " + VERSION)
                download_with_progress(VERSION, self.MC_DIR, progress_callback)
                self.write_log("Установка завершена")

            self._launching = True
            self._installing = False
            self.write_log("Подготовка запуска " + VERSION)

            fabric_version_id = None
            for v in minecraft_launcher_lib.utils.get_installed_versions(self.MC_DIR):
                if v["id"].startswith("fabric-loader") and VERSION in v["id"]:
                    fabric_version_id = v["id"]
                    break

            with open(MC_DIR / "versions" / "1.21.8" / "1.21.8.jar", "rb") as f:
                hash = hashlib.sha256(f.read()).hexdigest()

                if hash.lower() != "EA74E9C5E92D01F95F3D39196DDB734E19A077A58B4C433C34109487D600276F".lower():
                    self._launching = False
                    self._installing = True
                    self.write_log("Начата ПЕРЕустановка версии " + VERSION)
                    self.write_log("hash не совпал")
                    download_with_progress(VERSION, self.MC_DIR, progress_callback)
                    self._install_and_launch()
                    return
                self.write_log("hash совпал")
            if fabric_version_id:
                # noinspection PyTypeChecker
                cmd = minecraft_launcher_lib.command.get_minecraft_command(fabric_version_id, self.MC_DIR, self.options)
            else:
                # noinspection PyTypeChecker
                cmd = minecraft_launcher_lib.command.get_minecraft_command(VERSION, self.MC_DIR, self.options)

            self.write_log("Команда запуска: " + " ".join(cmd))

            with open(self.log_file, "a", encoding="utf-8") as f:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=self.MC_DIR,
                    bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                    encoding="UTF-8"
                )
                self.write_log("Процесс запущен")

                for line in self.process.stdout:
                    f.write(line.strip() + "\n")
                    f.flush()

            self.write_log("Процесс завершен")
            self._launching = False
            self._installing = False
            self.submit_logfile()
            self.show()
            self.raise_()
            self.activateWindow()
            self.check_for_xray()

            if self.process.returncode:
                self._launching = False
                self._installing = False
                msg = QMessageBox(self)
                msg.setWindowTitle(t(self.lang, "game_error_title"))
                msg.setText(
                    t(self.lang, "game_error_text")
                )
                msg.setIcon(QMessageBox.Warning)
                msg.exec_()



        except Exception as e:
            self.write_log(str(e))

    def _check_mc_state(self):
        running = is_mc_running()

        if running:
            self.fetcher.set_game(True)
            self.ui.set_play_status(t(self.lang, "in_game_status"))
            self.ui.set_play_enabled(False)
            self._launching = False
            self._installing = False
            self.hide()
            if self.banned:
                try:
                    self.process.kill()
                    self.ui.set_play_status(t(self.lang, "no_permission"))
                    self.ui.play_btn.setEnabled(False)
                except Exception as e:
                    self.write_log(str(e))
        elif self._launching and not self._installing:
            self.fetcher.set_game(False)
            self.ui.set_play_status(t(self.lang, "launching_status"))
            self.ui.set_play_enabled(False)
            if self.banned:
                try:
                    self.process.kill()
                    self.ui.set_play_status(t(self.lang, "no_permission"))
                    self.ui.play_btn.setEnabled(False)
                except Exception as e:
                    self.write_log(str(e))
        elif self._installing and not self._launching:
            self.fetcher.set_game(False)
            self.ui.set_play_enabled(False)
            if self.banned:
                try:
                    self.process.kill()
                    self.ui.set_play_status(t(self.lang, "no_permission"))
                    self.ui.play_btn.setEnabled(False)
                except Exception as e:
                    self.write_log(str(e))
        elif self._deleting and not self._launching:
            self.fetcher.set_game(False)
            self.ui.set_play_status(t(self.lang, "cleanup_status"))
            self.ui.set_play_enabled(False)
        else:
            self.fetcher.set_game(False)
            self.show()
            if not self.banned:
                self.ui.set_play_status(t(self.lang, "play_button"))
                self.ui.set_play_enabled(True)
                if not self.nickname:
                    self.ui.play_btn.setText(t(self.lang, "no_nick_found"))
                    self.ui.set_play_enabled(False)
            else:
                self.ui.set_play_status(t(self.lang, "cleanup_status"))
                self.ui.play_btn.setEnabled(False)

    def start_move(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def do_move(self, event):
        if self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

    def minimize_window(self):
        self.showMinimized()

    def handle_shader_action(self, slug: str, action: str):
        dir_path = os.path.join(self.MC_DIR, "shaderpacks")
        os.makedirs(dir_path, exist_ok=True)

        if action == "install":
            if slug in self.ui.shader_buttons:
                self.ui.shader_buttons[slug].setEnabled(False)

            try:
                gvers = f'["{VERSION}"]'
                loaders = '["iris"]'
                url = f"https://api.modrinth.com/v2/project/{slug}/version?game_versions={urllib.parse.quote(gvers)}&loaders={urllib.parse.quote(loaders)}"

                with urllib.request.urlopen(url) as resp:
                    versions = json.loads(resp.read())
                    if not versions:
                        raise Exception("No Iris version for this MC version")

                    latest = versions[0]
                    file_url = latest["files"][0]["url"]
                    filename = latest["files"][0]["filename"]

                    urllib.request.urlretrieve(file_url, os.path.join(dir_path, filename))
                    self.ui.update_shader_status(slug, "install")
            except Exception as e:
                print(e)
                if slug in self.ui.shader_buttons:
                    self.ui.shader_buttons[slug].setEnabled(True)

        elif action == "remove":
            removed = False
            for file in os.listdir(dir_path):
                if slug.lower() in file.lower():
                    os.remove(os.path.join(dir_path, file))
                    removed = True
            if removed:
                self.ui.update_shader_status(slug, "remove")

    def handle_resourcepack_action(self, slug: str, action: str):
        dir_path = os.path.join(self.MC_DIR, "resourcepacks")
        os.makedirs(dir_path, exist_ok=True)

        if action == "install":
            if slug in self.ui.resourcepack_buttons:
                self.ui.resourcepack_buttons[slug].setEnabled(False)

            try:
                gvers = f'["{VERSION}"]'
                url = f"https://api.modrinth.com/v2/project/{slug}/version?game_versions={urllib.parse.quote(gvers)}"

                with urllib.request.urlopen(url) as resp:
                    versions = json.loads(resp.read())
                    if not versions:
                        raise Exception("No version found")

                    latest = versions[0]
                    file_url = latest["files"][0]["url"]
                    filename = latest["files"][0]["filename"]

                    urllib.request.urlretrieve(file_url, os.path.join(dir_path, filename))
                    self.ui.update_resourcepack_status(slug, "install")
            except Exception as e:
                print(e)
                if slug in self.ui.resourcepack_buttons:
                    self.ui.resourcepack_buttons[slug].setEnabled(True)

        elif action == "remove":
            removed = False
            for file in os.listdir(dir_path):
                if slug.lower() in file.lower():
                    os.remove(os.path.join(dir_path, file))
                    removed = True
            if removed:
                self.ui.update_resourcepack_status(slug, "remove")

    def exit_launcher(self):
        self.write_log("Closing...")
        self.write_log(self.options)
        self.write_log(self.options["username"])

app = QtWidgets.QApplication(sys.argv)
win = LauncherApp()
win.show()
win.raise_()
win.activateWindow()
win.setFocus()
sys.exit(app.exec_())
