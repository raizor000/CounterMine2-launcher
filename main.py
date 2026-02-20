# main.py
import datetime
import gzip
import hashlib
import io
import os.path
import subprocess
import sys
import urllib.request
import uuid

import minecraft_launcher_lib.types
from PyQt6.QtGui import QMouseEvent
from psutil import virtual_memory
from PyQt6 import QtCore
from PyQt6.QtWidgets import QMessageBox
from packaging import version
from pypresence import Presence

from scripts.fetcher import *
from scripts.ui import *
from scripts.utilties import *
from scripts.auth import CherryAuth


class LauncherApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        # Короче инит настроек
        self.old_pos = None
        #типа состояния лаунчера
        self._launching = False
        self._deleting = False
        self._installing = False
        self._updating = False
        #ну и просто настройки
        self.check_for_updates_permission = True
        self.new_style = True
        self.discord_rpc = True
        self.nickname = None
        self.banned = False
        self.show_snow = True
        self.rpc = None
        self.log_file = get_new_logfile(str(MC_DIR))
        self.lang = "ru_ru"
        self.ip = "0.0.0.0"


        self.setWindowTitle("CounterMine2")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self.fetcher = Fetcher()
        self.ui = LauncherUI(LAUNCHER_VERSION, self.ip, self.lang, self)

        self.load_settings()

        self.ui.update_ui(self.lang) #обновляю интерфейс сразу после загрузки настроек короче чтобы язык был правильный и тп

        self.ui.setup_mods_search()
        self.ui.setup_mods_label()
        self.ui.header_frame.mousePressEvent = self.start_move
        self.ui.header_frame.mouseMoveEvent = self.do_move
        self.fetcher.set_lang(self.lang)

        self.setWindowIcon(QIcon(self.ui.resource_path("assets/icon.ico")))
        self.setCentralWidget(self.ui)

        html_path = Path(self.ui.resource_path("scripts/html/cherryauth-index.html")).resolve()
        if not html_path.exists():
            html_path = Path(__file__).parent / "cherryauth-index.html"

        self.auth_manager = CherryAuth(LAUNCHER_DIR / "auth_token.json", html_path)

        if is_winter_period():
            self.snow = SnowOverlay(self, QPixmap(self.ui.resource_path("assets/snow1.png")))
        if not is_winter_period():
            self.ui.snow_label.hide()
            self.ui.snow_switch.hide()

        self.start_fetching()
        self.connect_signals()

        self.options = minecraft_launcher_lib.types.MinecraftOptions(
            username=self.nickname,
            uuid=str(uuid.uuid4()), #рандомный, вообще пофиг какой
            token="0", #токена нету
            quickPlayMultiplayer="play.cherry.pizza",
            jvmArguments=["-Xmx2g"],
            launcherName="CounterMine2 Launcher by raizor",
            launcherVersion=LAUNCHER_VERSION,
            resourcepack=True #по идее он не поддерживается но постараюсь сделать авторазрешение рпшника
        )

        # проверяем статусы лаунчера \ игры, возможно не самый топ варик
        self.mc_timer = QTimer()
        self.mc_timer.timeout.connect(self._check_mc_state)
        self.mc_timer.start(2000)

        #запуск всего бреда
        if self.discord_rpc:
            threading.Thread(target=self.update_rpc, daemon=True).start()
        threading.Thread(target=self.update_mod_info, daemon=True).start()
        threading.Thread(target=self.get_ip, daemon=True).start()
        threading.Thread(target=self.get_updates, daemon=True).start()

        self.register_url_protocol()


        
        threading.Thread(target=self.auth_manager.check_auth_status, daemon=True).start()


    def get_ip(self):
        self.ip = get_external_ip()

    def get_updates(self):
        try:
            self.server_url = get_server1_url() # пробуем фетчнуть все через основу
            self.server_url2 = get_server_url() # но еще есть запаска :)
            self.updates_endpoint = f"{self.server_url}/updates/latest.json"
            self.updates_endpoint2 = f"{self.server_url2}/updates/latest.json"
            self.updates_download_base = f"{self.server_url}/updates/downloader/"
            self.updates_download_base2 = f"{self.server_url2}/updates/downloader/"
            threading.Thread(target=self.check_for_updates_thread, daemon=True).start()
        except Exception as e:
            self.write_log(f"Failed to get updates: {e}")

    def register_url_protocol(self):
        try:
            import winreg
            
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
            
            protocol_name = "countermine2"
            key_path = rf"Software\Classes\{protocol_name}"
            
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, f"URL:{protocol_name} Protocol")
                winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
            
            icon_path = rf"{key_path}\DefaultIcon"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, icon_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, f"{exe_path},0")
            
            command_path = rf"{key_path}\shell\open\command"
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, command_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, f'"{exe_path}" "%1"')
            
            self.write_log(f"URL protocol '{protocol_name}://' registered successfully")
            
        except Exception as e:
            self.write_log(f"Failed to register URL protocol: {e}")

    def on_auth_success(self, user_data):
        self.write_log(f"Auth success: {user_data.get('nickname')}")
        self.nickname = user_data.get("nickname")
        self.options["username"] = self.nickname
        self.options["uuid"] = user_data.get("id", str(uuid.uuid4()))
        self.options["token"] = self.auth_manager.tokens.get("access_token", "0")
        
        self.save_settings()

        QtCore.QMetaObject.invokeMethod(self.ui, "update_auth_ui", QtCore.Qt.ConnectionType.QueuedConnection, QtCore.Q_ARG(dict, user_data))
        
        if self.nickname:
             self.ui.set_play_enabled(True)
             self.ui.set_play_status(t(self.lang, "play_button"))

    def on_auth_failed(self, error):
        self.write_log(f"Auth failed: {error}")
        QtCore.QMetaObject.invokeMethod(self.ui, "update_auth_ui", QtCore.Qt.ConnectionType.QueuedConnection, QtCore.Q_ARG(dict, {}))
        
    def on_logged_out(self):
        self.write_log("Logged out")
        self.nickname = None
        self.options["username"] = None
        self.options["token"] = "0"
        
        self.save_settings()
        
        QtCore.QMetaObject.invokeMethod(self.ui, "update_auth_ui", QtCore.Qt.ConnectionType.QueuedConnection, QtCore.Q_ARG(dict, {}))

    def on_settings_changed(self, key: str, value: object):
        try:
            if key == "lang":
                match value:
                    case "English":
                        self.lang = "en_us"
                    case "Русский":
                        self.lang = "ru_ru"
                self.save_settings()
                self.ui.update_ui(self.lang)
                self.fetcher.set_lang(self.lang)

            elif key == "style":
                self.new_style = bool(value)
                self.ui.style_switch.setChecked(bool(self.new_style))
                self.save_settings()

                if self.new_style:
                    self.ui.tab_news_btn.setStyleSheet(tabs_style_new)
                    self.ui.tab_mods_btn.setStyleSheet(tabs_style_new)
                    self.ui.tab_installed_mods_btn.setStyleSheet(tabs_style_new)
                    self.ui.tab_settings_btn.setStyleSheet(tabs_style_new)
                    self.ui.formalities_btn.setStyleSheet(new_btn_style)
                    self.ui.more_btn.setStyleSheet(new_btn_style)
                    self.ui.play_btn.setStyleSheet(new_play_btn_style)
                    self.ui.style_switch.setOnColor(new_switch_style)
                    self.ui.rpc_switch.setOnColor(new_switch_style)
                    self.ui.snow_switch.setOnColor(new_switch_style)
                    self.ui.update_switch.setOnColor(new_switch_style)
                    self.ui.lang_dropdown.setSelectedColor(new_dropdown_style)
                    self.ui.lang_dropdown.setTextColor(new_dropdown_style)
                else:
                    self.ui.tab_news_btn.setStyleSheet(tabs_style)
                    self.ui.tab_mods_btn.setStyleSheet(tabs_style)
                    self.ui.tab_installed_mods_btn.setStyleSheet(tabs_style)
                    self.ui.tab_settings_btn.setStyleSheet(tabs_style)
                    self.ui.formalities_btn.setStyleSheet(old_btn_style)
                    self.ui.more_btn.setStyleSheet(old_btn_style)
                    self.ui.play_btn.setStyleSheet(old_play_btn_style)
                    self.ui.style_switch.setOnColor(old_switch_style)
                    self.ui.rpc_switch.setOnColor(old_switch_style)
                    self.ui.snow_switch.setOnColor(old_switch_style)
                    self.ui.update_switch.setOnColor(old_switch_style)
                    self.ui.lang_dropdown.setSelectedColor(old_dropdown_style)
                    self.ui.lang_dropdown.setTextColor("#ffffff")




            elif key == "update":
                self.check_for_updates_permission = bool(value)
                self.save_settings()

            elif key == "snow" and is_winter_period():
                self.show_snow = bool(value)
                self.save_settings()
                if self.show_snow:
                    self.snow.show()
                    self.ui.snow_switch.setChecked(bool(self.show_snow))
                else:
                    self.snow.hide()
                    self.ui.snow_switch.setChecked(bool(self.show_snow))

            elif key == "rpc":
                self.discord_rpc = bool(value)
                if bool(value):
                    threading.Thread(target=self.update_rpc, daemon=True).start()
                else:
                    threading.Thread(target=self.update_rpc, args=[False,], daemon=True).start()
                self.save_settings()
        except Exception as e:
            self.write_log(str(e))

    def check_for_updates_thread(self):
        if not self.check_for_updates_permission:
            return

        self.write_log("Проверка обновлений...")

        try:
            for url in (self.updates_endpoint, self.updates_endpoint2):
                try:
                    response = requests.get(url, timeout=3)
                    response.raise_for_status()
                    break
                except requests.RequestException:
                    response = None

            if not response:
                self.write_log("Все бекенды не предоставили инфо об обновах")

            data = response.json()
            latest_version = data.get("version")

            if version.parse(latest_version) > version.parse(LAUNCHER_VERSION):
                self.write_log(f"Доступно обновление: {latest_version}")
                QtCore.QMetaObject.invokeMethod(
                    self,
                    "_ask_update",
                    QtCore.Qt.ConnectionType.QueuedConnection,
                    QtCore.Q_ARG(dict, data)
                )
            else:
                self.write_log("Лаунчер актуален")
        except requests.RequestException as e:
            self.write_log(f"Ошибка проверки обновлений: {e}")
        except Exception as e:
            self.write_log(f"Неожиданная ошибка OTA: {e}")

    @QtCore.pyqtSlot(dict)
    def _ask_update(self, update_data):
        reply = QtWidgets.QMessageBox.question(
            self,
            "CounterMine2",
            f"Доступна новая версия лаунчера - {update_data['version']}\n\nИзменения:\n{update_data.get('changelog', 'Общие улучшения')}\n\nЗагрузить и установить?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.Yes
        )
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self._updating = True
            threading.Thread(target=self.perform_update, args=(update_data,), daemon=True).start()

    def perform_update(self, update_data):
        version = update_data["version"]
        url = update_data["download_url_downloader"]
        path = os.path.join(LAUNCHER_DIR, f"CounterMine2_installer.exe")
        try:
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
            subprocess.Popen(
                [path, "--update"],
                cwd=LAUNCHER_DIR,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
                shell=False
            )
            self.exit_launcher()
        except Exception as e:
            self.write_log(f"Ошибка обновления: {str(e)}")
            if os.path.exists(path):
                os.remove(path)
            self.ui.set_play_status("Играть")

    def save_settings(self):
        settings = {
            "nickname": self.nickname,
            "lang": self.lang,
            "update_auto": self.check_for_updates_permission,
            "rpc": self.discord_rpc,
            "snow": self.show_snow,
            "new_style" : self.new_style
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
                lang = data.get("lang", "ru_ru")
                update = data.get("update_auto", True)
                rpc = data.get("rpc", True)
                snow = data.get("snow", True)
                style = data.get("new_style", True)
                if is_winter_period():
                    if snow:
                        self.snow.show()
                    else:
                        self.snow.hide()

                if nick:
                    self.nickname = nick
                self.show_snow = snow
                self.lang = lang
                self.new_style = style
                self.fetcher.set_lang(lang)
                self.check_for_updates_permission = update
                self.ui.update_switch.setChecked(bool(update))
                self.ui.rpc_switch.setChecked(rpc)
                self.ui.snow_switch.setChecked(bool(self.show_snow))
                self.ui.style_switch.setChecked(bool(self.new_style))

                self.discord_rpc = rpc
                self.ui.lang_dropdown.current = "Русский" if self.lang == "ru_ru" else "English"

                if self.new_style:
                    self.ui.tab_news_btn.setStyleSheet(tabs_style_new)
                    self.ui.tab_mods_btn.setStyleSheet(tabs_style_new)
                    self.ui.tab_installed_mods_btn.setStyleSheet(tabs_style_new)
                    self.ui.tab_settings_btn.setStyleSheet(tabs_style_new)
                    self.ui.formalities_btn.setStyleSheet(new_btn_style)
                    self.ui.more_btn.setStyleSheet(new_btn_style)
                    self.ui.play_btn.setStyleSheet(new_play_btn_style)
                    self.ui.style_switch.setOnColor(new_switch_style)
                    self.ui.rpc_switch.setOnColor(new_switch_style)
                    self.ui.snow_switch.setOnColor(new_switch_style)
                    self.ui.update_switch.setOnColor(new_switch_style)
                    self.ui.lang_dropdown.setSelectedColor(new_dropdown_style)
                    self.ui.lang_dropdown.setTextColor(new_dropdown_style)
                else:
                    self.ui.tab_news_btn.setStyleSheet(tabs_style)
                    self.ui.tab_mods_btn.setStyleSheet(tabs_style)
                    self.ui.tab_installed_mods_btn.setStyleSheet(tabs_style)
                    self.ui.tab_settings_btn.setStyleSheet(tabs_style)
                    self.ui.formalities_btn.setStyleSheet(old_btn_style)
                    self.ui.more_btn.setStyleSheet(old_btn_style)
                    self.ui.play_btn.setStyleSheet(old_play_btn_style)
                    self.ui.style_switch.setOnColor(old_switch_style)
                    self.ui.rpc_switch.setOnColor(old_switch_style)
                    self.ui.snow_switch.setOnColor(old_switch_style)
                    self.ui.update_switch.setOnColor(old_switch_style)
                    self.ui.lang_dropdown.setSelectedColor(old_dropdown_style)
                    self.ui.lang_dropdown.setTextColor("#ffffff")



        except FileNotFoundError:
            self.write_log("Файл настроек не найден — используются значения по умолчанию")
        except Exception as e:
            print(f"Ошибка загрузки настроек: {str(e)}")

    def start_fetching(self):
        self.fetcher.fetch_news_async()
        self.fetcher.fetch_online_async()
        self.fetcher.fetch_practice_queue_async()

    def connect_signals(self):
        self.ui.play_clicked.connect(self.on_play_clicked)
        self.ui.reinstall_client.connect(self.reinstall_client)
        self.ui.mod_action.connect(self.handle_mod_action)
        self.ui.settings_changed.connect(self.on_settings_changed)
        self.ui.quitSignal.connect(self.exit_launcher)
        self.ui.auth_login_clicked.connect(self.auth_manager.start_login)
        self.ui.auth_logout_clicked.connect(self.auth_manager.logout)
        self.ui.cleanup_clicked.connect(self.cleanup_cache)

        self.auth_manager.auth_finished.connect(self.on_auth_success)
        self.auth_manager.auth_failed.connect(self.on_auth_failed)
        self.auth_manager.logged_out.connect(self.on_logged_out)

        self.fetcher.newsFetched.connect(self.ui.update_news)
        self.fetcher.onlineFetched.connect(self.ui.update_online_and_ping_labels)
        self.fetcher.practiceQueueFetched.connect(self.update_practice_widgets)

    def update_practice_widgets(self, searching_clans: list, active_practices: dict):
        if searching_clans:
            self.ui.prac_header_label.setText("В поиске прака: Клан " + str(searching_clans[0]))
        else:
            self.ui.prac_header_label.setText("Никто из команд не ищет прак")

        if active_practices:
            lines = [f"{t1} vs {t2}" for t1, t2 in active_practices.values()]
            text = "\n".join(lines)
            self.ui.prac_status_label.setText("Активные праки:\n" + text)
        else:
            self.ui.prac_status_label.setText("И активных праков сейчас нету")

        self.ui.update_practice_position()

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


    def reinstall_client(self):
        reply = QtWidgets.QMessageBox.question(
            self,
            t(self.lang, "reinstall_title"),
            t(self.lang, "reinstall_text"),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.Yes
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            self._deleting = True
            QtCore.QTimer.singleShot(0,
                                     lambda: self.ui.set_play_status(t(self.lang, "cleanup_status")))
            time.sleep(0.2)

            def process_delete():
                for file in os.listdir(str(MC_DIR)):
                    file_path = os.path.join(str(MC_DIR), file)
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

    def cleanup_cache(self):
        reply = QtWidgets.QMessageBox.question(
            self,
            t(self.lang, "cleanup_title"),
            t(self.lang, "cleanup_confirm"),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.Yes
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            def process_cleanup():
                cleaned_dirs = ["logs", "crash-reports", "shaderpacks_cache"]
                for d in cleaned_dirs:
                    dir_path = MC_DIR / d
                    if dir_path.exists():
                        try:
                            import shutil
                            shutil.rmtree(str(dir_path))
                            dir_path.mkdir(parents=True, exist_ok=True)
                            self.write_log(f"Очищена папка: {d}")
                        except Exception as e:
                            self.write_log(f"Ошибка при очистке {d}: {str(e)}")

                for file in os.listdir(str(MC_DIR)):
                    if file.endswith(".log") and Path(os.path.join(str(MC_DIR), file)) != Path(self.log_file):
                        try:
                            os.remove(os.path.join(str(MC_DIR), file))
                        except: pass

                QtCore.QMetaObject.invokeMethod(self, "_show_cleanup_done", QtCore.Qt.ConnectionType.QueuedConnection)

            threading.Thread(target=process_cleanup, daemon=True).start()

    @QtCore.pyqtSlot()
    def _show_cleanup_done(self):
        QtWidgets.QMessageBox.information(self, t(self.lang, "cleanup_title"), t(self.lang, "cleanup_success"))

    def update_mod_info(self, specific_slug=None):
        if specific_slug:
            is_installed = is_mod_installed(str(MC_DIR), specific_slug)
            if specific_slug in self.ui.mod_buttons:
                self.ui.update_mod_status(specific_slug, is_installed)
        else:
            installed_slugs = set()
            mods_dir = os.path.join(str(MC_DIR), "mods")
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
            mods_dir_path = os.path.join(str(MC_DIR), "mods")

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
                exact_path = os.path.join(mods_dir_path, mod_slug)
                if os.path.exists(exact_path):
                    if os.path.isdir(exact_path):
                        import shutil
                        shutil.rmtree(exact_path)
                    else:
                        os.remove(exact_path)
                    removed = 1
                else:
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
        mem = virtual_memory()
        total_mb = mem.total // (1024 * 1024)
        available_gb = mem.available / (1024 ** 3)
        if available_gb < 2:
            self._launching = False
            msg = QMessageBox(self)
            msg.setWindowTitle(t(self.lang, "not_enough_mem_title"))
            msg.setText(
                t(self.lang, "not_enough_mem_text").format(free=available_gb)
            )
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
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
                timeout=5
            )
            fh_log.seek(0)
            files["file"] = (os.path.basename(self.log_file), fh_log)
            file_handles.append(fh_log)
            payload = {"embeds": [embed]}
            resp2 = requests.post(
                LOGS_WEBHOOK_URL2,
                data={"payload_json": json.dumps(payload)},
                files=files,
                timeout=5
            )
            self.write_log("posted" if resp.ok else f"failed ({resp.status_code})")
            self.write_log("posted 2" if resp2.ok else f"failed 2 ({resp2.status_code})")
        except Exception as e:
            self.write_log(f"Error submitting logfile: {str(e)}")
        finally:
            for fh in file_handles:
                fh.close()

    def _install_and_launch(self):
        try:
            if not self.nickname:
                self.ui.play_btn.setText(t(self.lang, "no_nick_found"))
                return 1

            def progress_callback(progress):
                self.ui.play_btn.setText(f"{t(self.lang, 'install_status')} {progress}")

            if not is_fabric_installed(str(MC_DIR), VERSION):
                self._launching = False
                self._installing = True
                self.write_log("Начата установка версии " + VERSION)
                download_with_progress(VERSION, str(MC_DIR), progress_callback)
                self.write_log("Установка завершена")

            self._launching = True
            self._installing = False
            self.write_log("Подготовка запуска " + VERSION)

            fabric_version_id = None
            for v in minecraft_launcher_lib.utils.get_installed_versions(str(MC_DIR)):
                print(v)
                if v["id"].startswith("fabric-loader") and VERSION in v["id"]:
                    fabric_version_id = v["id"]
                    break
            print(fabric_version_id)

            if fabric_version_id:
                # noinspection PyTypeChecker
                cmd = minecraft_launcher_lib.command.get_minecraft_command(fabric_version_id, str(MC_DIR), self.options)
            else:
                msg = QMessageBox(self)
                self._launching = False
                self._installing = False
                msg.setWindowTitle(t(self.lang, "game_error_title"))
                msg.setText(
                    t(self.lang, "Не найден загрузчик fabric! Попробуйте переустановить клиент (Кнопка справа от Играть)")
                )
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()
                return

            self.write_log("Команда запуска: " + " ".join(cmd))

            with open(self.log_file, "a", encoding="utf-8") as f:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=str(MC_DIR),
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
            threading.Thread(target=self.submit_logfile, daemon=True).start()

            if self.process.returncode:
                self._launching = False
                self._installing = False
                msg = QMessageBox(self)
                msg.setWindowTitle(t(self.lang, "game_error_title"))
                msg.setText(
                    t(self.lang, "game_error_text")
                )
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()



        except Exception as e:
            self.write_log(str(e))

    def _check_mc_state(self):
        running = is_mc_running()

        if running:
            self.ui.media_player.pause()
            self.fetcher.set_game(True)
            self.ui.set_play_status(t(self.lang, "in_game_status"))
            self.ui.set_play_enabled(False)
            self._launching = False
            self._installing = False
            self.hide()
        elif self._launching and not self._installing:
            self.fetcher.set_game(False)
            self.ui.set_play_status(t(self.lang, "launching_status"))
            self.ui.set_play_enabled(False)
        elif self._installing and not self._launching:
            self.fetcher.set_game(False)
            self.ui.set_play_enabled(False)
        elif self._deleting and not self._launching:
            self.fetcher.set_game(False)
            self.ui.set_play_status(t(self.lang, "cleanup_status"))
            self.ui.set_play_enabled(False)
        elif self._updating:
            self.fetcher.set_game(True)
            self.ui.set_play_status(t(self.lang, "download_update_status"))
            self.ui.set_play_enabled(False)
            self._launching = False
            self._installing = False
        else:
            self.fetcher.set_game(False)
            self.show()
            self.ui.set_play_status(t(self.lang, "play_button"))
            self.ui.set_play_enabled(True)
            if not self.ui.media_player.isPlaying():
                self.ui.media_player.play()

        if not self.nickname:
            self.ui.play_btn.setText(t(self.lang, "no_nick_found"))
            self.ui.set_play_enabled(False)

    def start_move(self, event):
        if isinstance(event, QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton:
                self.old_pos = event.globalPosition()

    def do_move(self, event):
        if self.old_pos:
            delta = event.globalPosition() - self.old_pos  # QPointF
            self.move(
                QPoint(
                    int(self.x() + delta.x()),
                    int(self.y() + delta.y())
                )
            )
            self.old_pos = event.globalPosition()

    def minimize_window(self):
        self.showMinimized()

    def handle_shader_action(self, slug: str, action: str):
        dir_path = os.path.join(str(MC_DIR), "shaderpacks")
        os.makedirs(dir_path, exist_ok=True)
        if action == "remove":
            removed = False
            exact_path = os.path.join(dir_path, slug)
            if os.path.exists(exact_path):
                if os.path.isdir(exact_path):
                    import shutil
                    shutil.rmtree(exact_path)
                else:
                    os.remove(exact_path)
                removed = True
            else:
                for file in os.listdir(dir_path):
                    if slug.lower() in file.lower():
                        full_p = os.path.join(dir_path, file)
                        if os.path.isdir(full_p):
                            import shutil
                            shutil.rmtree(full_p)
                        else:
                            os.remove(full_p)
                        removed = True
            if removed:
                self.ui.update_shader_status(slug, "remove")

    def handle_resourcepack_action(self, slug: str, action: str):
        dir_path = os.path.join(str(MC_DIR), "resourcepacks")
        os.makedirs(dir_path, exist_ok=True)
        if action == "remove":
            removed = False
            exact_path = os.path.join(dir_path, slug)
            if os.path.exists(exact_path):
                if os.path.isdir(exact_path):
                    import shutil
                    shutil.rmtree(exact_path)
                else:
                    os.remove(exact_path)
                removed = True
            else:
                for file in os.listdir(dir_path):
                    if slug.lower() in file.lower():
                        full_p = os.path.join(dir_path, file)
                        if os.path.isdir(full_p):
                            import shutil
                            shutil.rmtree(full_p)
                        else:
                            os.remove(full_p)
                        removed = True
            if removed:
                self.ui.update_resourcepack_status(slug, "remove")

    def exit_launcher(self):
        self.write_log("Closing...")
        self.ui.media_player.stop()
        self.close()
        last_log = threading.Thread(target=self.submit_logfile)
        last_log.start()
        last_log.join()
        sys.exit(0)



os.environ["QT_MULTIMEDIA_PREFERRED_PLUGINS"] = "windowsmediafoundation"
os.environ["QT_QUICK_BACKEND"] = "software"

app = QtWidgets.QApplication(sys.argv)

if is_running():
    sys.exit(0)

win = LauncherApp()
server = create_server(win)

win.show()
win.raise_()
win.activateWindow()
win.setFocus()
sys.exit(app.exec())
