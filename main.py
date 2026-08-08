# main.py
import datetime
import gzip
import hashlib
import threading
import time
import io
import json
import os.path
import requests
import subprocess
import sys
import urllib.request
import uuid
import zipfile
import shutil
import sys

if sys.platform == 'win32':
    import winreg
else:
    winreg = None
import minecraft_launcher_lib.types
from PyQt6.QtCore import QPoint, Qt, QCoreApplication, pyqtSignal
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtGui import QMouseEvent, QGuiApplication, QPalette, QIcon, QPixmap
from PyQt6.QtWidgets import QMessageBox, QGraphicsOpacityEffect, QProgressDialog, QPushButton
from packaging import version
from psutil import virtual_memory
from pypresence import Presence
import urllib
from scripts.plugin_manager import PluginManager
from scripts.auth import CherryAuth
from scripts.fetcher import *
from scripts.ui import *
from scripts.utilties import *
from scripts.debug_console import DebugConsoleWindow

QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)


class _StdoutRedirector:
    _ERROR_KEYWORDS = (
        "error", "exception", "traceback", "fatal", "crash",
        "failed to", "failure", "could not", "cannot", "unable to",
        "connectionerror", "httperror", "winError", "oserror",
        "max retries", "newconnectionerror",
    )
    _WARN_KEYWORDS = (
        "warn", "warning", "deprecated", "fallback", "retry",
        "timeout", "skipping", "missing",
    )

    def __init__(self, write_fn, original_stream, default_level="INFO"):
        self._write = write_fn
        self._original = original_stream
        self._default_level = default_level
        self._buffer = ""

    @staticmethod
    def _detect_level(line: str, floor_level: str = "INFO") -> str:
        low = line.lower()
        if any(k in low for k in _StdoutRedirector._ERROR_KEYWORDS):
            return "ERROR"
        if any(k in low for k in _StdoutRedirector._WARN_KEYWORDS):
            return "WARN" if floor_level == "INFO" else floor_level
        return floor_level

    def write(self, text):
        if self._original:
            try:
                self._original.write(text)
            except Exception:
                pass
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line.strip():
                level = self._detect_level(line, self._default_level)
                self._write(line, level)

    def flush(self):
        if self._original:
            try:
                self._original.flush()
            except Exception:
                pass
        if self._buffer.strip():
            level = self._detect_level(self._buffer, self._default_level)
            self._write(self._buffer.strip(), level)
            self._buffer = ""

    def fileno(self):
        return self._original.fileno() if self._original else -1

    def isatty(self):
        return False


class LauncherApp(QtWidgets.QMainWindow):
    show_message_signal = pyqtSignal(str, str, QMessageBox.Icon)
    update_download_progress = pyqtSignal(int, int, int)
    update_download_message = pyqtSignal(str)
    plugin_updates_checked = pyqtSignal()
    log_signal = pyqtSignal(str, str)
    populate_versions_signal = pyqtSignal(list)
    auth_update_signal = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.sound_enabled = True
        self.old_pos = None
        self._launching = False
        self._deleting = False
        self._installing = False
        self.remote_plugins = []
        self.maintenance_data = []
        self._update_cancelled = threading.Event()
        self.update_progress_dialog = None
        self.new_style = True
        self.discord_rpc = True
        self.show_debug_console = False
        self.plugin_states = {}
        self.nickname = None
        self.banned = False
        self.show_snow = True
        self.rpc = None
        self.log_file = get_new_logfile(str(MC_DIR))
        self.lang = "ru_ru"
        self.ip = "0.0.0.0"
        self.minecraft_pid = -1
        self.selected_version = VERSION

        self.setWindowTitle("CounterMine2 Launcher")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

        self.fetcher = Fetcher()
        self.ui = LauncherUI(LAUNCHER_VERSION, self.ip, self.lang, self)

        def load_versions():
            try:
                self.write_log("Fetching Minecraft version list...")
                all_versions = minecraft_launcher_lib.utils.get_version_list()
                release_versions = [v['id'] for v in all_versions if v['type'] == 'release']

                start_v = version.parse("1.21.11")

                filtered_versions = [v for v in release_versions if version.parse(v) >= start_v]
                sorted_versions = sorted(filtered_versions, key=version.parse, reverse=True)

                if not sorted_versions:
                    self.write_warn("Could not find versions >= 1.21.11, using fallback.")
                    sorted_versions = ["1.21.11"]

                self.write_log(f"Found {len(sorted_versions)} versions to display.")
                self.populate_versions_signal.emit(sorted_versions)
            except Exception as e:
                self.write_error(f"Failed to get Minecraft versions: {e}")
                self.populate_versions_signal.emit(["1.21.11"])

        threading.Thread(target=load_versions, daemon=True).start()

        self.load_settings()

        self.console_window = DebugConsoleWindow()
        self.console_window.closed_signal.connect(self.on_console_window_closed)
        self.log_signal.connect(self.console_window.append_log)
        self.console_window.update_ui(self.lang)

        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr

        def _routed_write(msg: str, level: str):
            self.write_log(f"[stdout] {msg}", level)

        def _routed_write_err(msg: str, level: str):
            self.write_log(f"[stderr] {msg}", level if level == "ERROR" else "WARN")

        sys.stdout = _StdoutRedirector(_routed_write, self._orig_stdout, default_level="INFO")
        sys.stderr = _StdoutRedirector(_routed_write_err, self._orig_stderr, default_level="WARN")

        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        self.console_window.append_log(line.rstrip(), "INFO")
            except Exception as e:
                print(f"Error pre-filling console: {e}")

        if self.show_debug_console:
            self.console_window.show()

        self.plugin_manager = PluginManager(self)
        self.plugin_manager.load_internal_plugins()
        self.plugin_manager.load_plugins()

        self.populate_versions_signal.connect(self.ui.fill_menu_items, QtCore.Qt.ConnectionType.QueuedConnection)
        self.auth_update_signal.connect(self.ui.update_auth_ui, QtCore.Qt.ConnectionType.QueuedConnection)

        threading.Thread(target=self._check_for_plugin_updates_async, daemon=True).start()

        self.ui.update_ui(self.lang)
        self.ui.header_frame.mousePressEvent = self.start_move
        self.ui.header_frame.mouseMoveEvent = self.do_move
        self.fetcher.set_lang(self.lang)

        self.icon_p = str(get_resource_path("assets/icons/ico.ico"))
        self.setWindowIcon(QIcon(self.icon_p))
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

        if sys.platform == 'win32':
            self.register_url_protocol()
        else:
            self.write_log("URL protocol registration skipped: non-Windows platform")

        self.start_fetching()
        self.connect_signals()
        self.options = minecraft_launcher_lib.types.MinecraftOptions(
            username=str(self.nickname),
            uuid=str(uuid.uuid4()),
            token="0",
            quickPlayMultiplayer="direct.cherry.pizza",
            jvmArguments=["-Xmx1g"],
            launcherName="CounterMine2 Launcher by raizor",
            launcherVersion=LAUNCHER_VERSION,
        )

        self.mc_timer = QTimer()
        self.mc_timer.timeout.connect(self._check_mc_state)
        self.mc_timer.start(2000)

        if self.discord_rpc:
            threading.Thread(target=self.update_rpc, daemon=True).start()

        threading.Thread(target=self.auth_manager.check_auth_status, daemon=True).start()

        self.apply_theme()

        for plugin in self.plugin_manager.plugins:
            plugin.on_ui_ready()

        QTimer.singleShot(50, lambda: (
            self.raise_(),
            self.activateWindow()
        ))

        QtCore.QTimer.singleShot(100, self.check_startup)

    def check_startup(self):
        if not os.path.exists(Path(LAUNCHER_DIR) / "first_launch"):
            self.write_log("Первый запуск лаунчера - показываем сводку")
            with open(Path(LAUNCHER_DIR) / "first_launch", "w") as f:
                f.write("This file indicates that the launcher has been run at least once. Do not delete it")

            result = QMessageBox.information(
                self,
                "CounterMine2 Launcher - Обновление 5.0",
                "Данная версия 5.0 - Последнее официальное обновление. \n\n\nВ лаунчер была добавлена система плагинов, чтобы пользователи могли модифицировать лаунчер под свое усмотрение. \n\nРекомендуем включить плагин CounterStrike2Theme, чтобы получить новый интерфейс лаунчера. \n\nНастройки плагинов можно найти в разделе 'Плагины' во вкладке настройки.\n\nЧтобы включить плагин Counter-Strike2 Theme, нажмите OK.",
                QMessageBox.StandardButton.Ok,
                QMessageBox.StandardButton.Cancel
            )
            if result == QMessageBox.StandardButton.Ok:
                self.plugin_states["UI_Modifier"] = True
                self.save_settings()
                self.restart()

    def restart(self):
        self.write_log("Перезапуск лаунчера...")
        current_executable = sys.executable
        os.execl(current_executable, current_executable, *sys.argv)

    def _check_for_plugin_updates_async(self):
        self.write_log("[Update] Starting background check for plugin updates...")
        if self.fetch_remote_plugins():
            self.plugin_manager.check_for_updates()
            self.write_log("[Update] Background plugin update check finished.")
            self.plugin_updates_checked.emit()
            have_updates = []

            for plugin in self.plugin_manager.discovered_plugins:
                local_id = plugin.get('id')
                local_id = str(local_id).replace("main.", "")
                if local_id in {p['id']: p for p in self.remote_plugins}:
                    if hasattr(plugin, "update_available"):
                        have_updates.append(f"{plugin['name']}\n{plugin['version']} → {plugin['latest_version']}\n")

            if len(have_updates) > 0:
                updates_text = "\n".join(have_updates)
                self.show_message_signal.emit(
                    t(self.lang, "plugin_update_confirm_title"),
                    f"Доступны обновления для следующих плагинов:\n\n{updates_text}",
                    QMessageBox.Icon.Information
                )
        else:
            self.write_warn("[Update] Could not fetch remote plugin list for update check.")

    @property
    def is_cs2_theme_active(self) -> bool:
        from scripts.internal.counterstrike2theme import UI_Modifier
        return any(isinstance(p, UI_Modifier) for p in self.plugin_manager.plugins) and sys.platform == "win32"

    def register_url_protocol(self):
        if sys.platform != 'win32':
            self.write_log("URL protocol registration is only supported on Windows")
            return

        try:
            import winreg

            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'

            protocol_name = "countermine2"
            key_path = rf"Software\Classes\{protocol_name}"

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.SetValue(key, "", winreg.REG_SZ, f"CounterMine2 Launcher")
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

    def fetch_remote_plugins(self):
        repo_url = "https://raw.githubusercontent.com/raizor000/CounterMine2-launcher-plugins/main/plugins.json"
        try:
            self.write_log(f"[Market] Fetching plugins from: {repo_url}")
            response = requests.get(repo_url, timeout=5)
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict):
                self.remote_plugins = data.get("plugins", [])
                self.maintenance_data = data.get("maintenance", [])
            elif isinstance(data, list):
                self.remote_plugins = [p for p in data if p.get('type') != 'maintenance']
                self.maintenance_data = [p for p in data if p.get('type') == 'maintenance']
            else:
                self.remote_plugins = []
                self.maintenance_data = []

            self.write_log(f"[Market] Successfully fetched {len(self.remote_plugins)} plugins.")
            return True
        except Exception as e:
            self.write_error(f"[Market] Error fetching remote plugins: {e}")
            return False

    def install_plugin_from_url(self, plugin_data):
        return self.plugin_manager.install_from_url(plugin_data)

    def delete_external_plugin(self, plugin_id):
        return self.plugin_manager.delete_plugin(plugin_id)

    def on_auth_success(self, user_data):
        self.write_log(f"[Auth] Успешная авторизация: {user_data.get('nickname')}")
        self.nickname = user_data.get("nickname")
        self.options["username"] = self.nickname
        self.options["uuid"] = user_data.get("id", str(uuid.uuid4()))
        self.options["token"] = self.auth_manager.tokens.get("access_token", "0")

        self.save_settings()

        self.auth_update_signal.emit(user_data)

        if self.nickname:
            self.ui.set_play_enabled(True)
            self.ui.set_play_status(t(self.lang, "play_button"))

    def on_auth_failed(self, error):
        self.write_error(f"[Auth] Ошибка авторизации: {error}")
        self.auth_update_signal.emit({})

    def on_logged_out(self):
        self.write_log(f"[Auth] Пользователь вышел из аккаунта")
        self.nickname = None
        self.options["username"] = None
        self.options["token"] = "0"

        self.save_settings()

        self.auth_update_signal.emit({})

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
                self.console_window.update_ui(self.lang)
                self.fetcher.set_lang(self.lang)
                for plugin in self.plugin_manager.plugins:
                    plugin.on_language_change(lang=self.lang)

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
                    threading.Thread(target=self.update_rpc, args=[False, ], daemon=True).start()
                self.save_settings()


            elif key == "debug_console":
                self.show_debug_console = bool(value)
                self.save_settings()
                if self.show_debug_console:
                    self.console_window.show()
                else:
                    self.console_window.hide()

            elif key == "plugin_state":
                plugin_id, enabled = value

                if enabled:
                    if plugin_id == "ModrinthPlugin":
                        self.plugin_states["CurseForgePlugin"] = False
                    elif plugin_id == "CurseForgePlugin":
                        self.plugin_states["ModrinthPlugin"] = False

                self.plugin_states[plugin_id] = enabled
                self.save_settings()
                self.ui._populate_plugins()
                action = "включен" if enabled else "выключен"
                self.write_log(f"[Плагины] {plugin_id} {action}. Требуется перезапуск.")
                QMessageBox.information(self, "Плагины",
                                        "Для применения изменений (включения/выключения) плагинов требуется перезапуск лаунчера.")
        except Exception as e:
            self.write_error(f"[Настройки] Ошибка при изменении '{key}': {str(e)}")

    def apply_theme(self):
        self.ui.tab_news_btn.setStyleSheet(tabs_style_new)
        self.ui.tab_installed_mods_btn.setStyleSheet(tabs_style_new)
        self.ui.tab_settings_btn.setStyleSheet(tabs_style_new)
        if self.ui.modrinth_plugin_tab_btn:
            self.ui.modrinth_plugin_tab_btn.setStyleSheet(tabs_style_new)
        self.ui.formalities_btn.setStyleSheet(new_btn_style)
        self.ui.more_btn.setStyleSheet(new_btn_style)
        self.ui.plugins_btn.setStyleSheet(new_btn_style)
        self.ui.play_btn.setStyleSheet(new_play_btn_style)
        self.ui.menu_btn.setStyleSheet(new_play_menu_btn_style)
        self.ui.rpc_switch.setOnColor(new_switch_style)
        self.ui.snow_switch.setOnColor(new_switch_style)
        self.ui.lang_dropdown.setSelectedColor(new_dropdown_style)
        self.ui.debug_console_switch.setStyleSheet(new_btn_style)

    def save_settings(self):
        settings = {
            "nickname": self.nickname,
            "lang": self.lang,
            "sound_enabled": self.sound_enabled,
            "rpc": self.discord_rpc,
            "snow": self.show_snow,
            "new_style": self.new_style,
            "plugin_states": self.plugin_states,
            "show_debug_console": self.show_debug_console
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
            if not os.path.exists(LAUNCHER_DIR / "settings.json"):
                self.save_settings()

            with open(LAUNCHER_DIR / "settings.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                nick = data.get("nickname", "")
                lang = data.get("lang", "ru_ru")
                rpc = data.get("rpc", True)
                snow = data.get("snow", True)
                style = data.get("new_style", True)
                sound = data.get("sound_enabled", True)
                self.plugin_states = data.get("plugin_states", {})
                self.show_debug_console = data.get("show_debug_console", False)

                if "ModrinthPlugin" not in self.plugin_states and "CurseForgePlugin" not in self.plugin_states:
                    self.plugin_states["ModrinthPlugin"] = True
                    self.plugin_states["CurseForgePlugin"] = False
                elif self.plugin_states.get("ModrinthPlugin") and self.plugin_states.get("CurseForgePlugin"):
                    self.plugin_states["CurseForgePlugin"] = False

                if is_winter_period():
                    if snow:
                        self.snow.show()
                    else:
                        self.snow.hide()

                if nick:
                    self.nickname = nick

                self.show_snow = snow
                self.sound_enabled = sound
                self.lang = lang
                self.new_style = style
                self.fetcher.set_lang(lang)
                self.ui.rpc_switch.setChecked(rpc)
                if is_winter_period():
                    self.ui.snow_switch.setChecked(self.show_snow)

                self.discord_rpc = rpc
                self.ui.debug_console_switch.setChecked(self.show_debug_console)
                self.ui.lang_dropdown.current = "Русский" if self.lang == "ru_ru" else "English"



        except FileNotFoundError:
            self.write_log("Файл настроек не найден — используются значения по умолчанию")
        except Exception as e:
            print(f"Ошибка загрузки настроек: {str(e)}")

    def start_fetching(self):
        self.fetcher.fetch_news_async()
        self.fetcher.fetch_online_async()

    def connect_signals(self):
        self.ui.play_clicked.connect(self.on_play_clicked)
        self.ui.menu_item_clicked.connect(self.on_version_selected)
        self.ui.reinstall_client.connect(self.reinstall_client)
        self.ui.mod_action.connect(self.handle_mod_action)
        self.ui.settings_changed.connect(self.on_settings_changed)
        self.ui.quitSignal.connect(self.exit_launcher)
        self.ui.auth_login_clicked.connect(self.auth_manager.start_login)
        self.ui.auth_logout_clicked.connect(self.auth_manager.logout)
        self.ui.open_directory_clicked.connect(self.open_game_directory)

        self.auth_manager.auth_finished.connect(self.on_auth_success)
        self.auth_manager.auth_failed.connect(self.on_auth_failed)
        self.auth_manager.logged_out.connect(self.on_logged_out)

        self.plugin_updates_checked.connect(self._on_plugin_updates_checked)
        self.fetcher.newsFetched.connect(self.ui.update_news)
        self.fetcher.onlineFetched.connect(self.ui.update_online_and_ping_labels)

        self.show_message_signal.connect(self._show_message)

    def _on_plugin_updates_checked(self):
        if self.ui.plugins_manager_container.isVisible() and not self.ui.plugin_market_view:
            self.ui._populate_plugins()

    def on_version_selected(self, version_id: str):
        self.write_log(f"Выбрана версия для запуска: {version_id}")
        self.selected_version = version_id

    def update_rpc(self, enable=True):
        if enable:
            if not self.rpc:
                try:
                    self.rpc = Presence("1493262434566144000")
                    self.rpc.connect()
                    self.rpc.update(
                        details="CounterMine2",
                        state=f"direct.cherry.pizza | Версия: {self.selected_version}",
                        large_image="logo2",
                        large_text="CounterMine2 Client",
                        start=int(time.time()),
                        buttons=[
                            {"label": "Сайт", "url": "https://cherry.pizza"},
                            {"label": "Discord", "url": "https://discord.gg/2wbp5aYZtF"},
                            {"label": "Лаунчер", "url": "https://discord.gg/Gg2fy7VzEV"}
                        ]
                    )
                    self.write_log(f"Установлена интеграция с дискордом ")
                except Exception as e:
                    self.rpc = None
                    self.write_log(f"Ошибка установки RPC: {str(e)}", level="ERROR")

            if self.rpc:
                try:
                    self.rpc.update(
                        details="CounterMine2",
                        state=f"direct.cherry.pizza | Версия: {self.selected_version}",
                        large_image="logo2",
                        large_text="CounterMine2 Client",
                        start=int(time.time()),
                        buttons=[
                            {"label": "Сайт", "url": "https://cherry.pizza"},
                            {"label": "Discord", "url": "https://discord.gg/2wbp5aYZtF"},
                            {"label": "Лаунчер", "url": "https://discord.gg/Gg2fy7VzEV"}

                        ]
                    )
                except Exception as e:
                    self.rpc = None
                    self.write_log(f"Ошибка обновления RPC: {str(e)}", level="ERROR")
        else:
            try:
                if self.rpc:
                    self.rpc.close()
            except Exception:
                pass
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

            def process_delete():
                for file in os.listdir(str(MC_DIR)):
                    file_path = os.path.join(str(MC_DIR), file)
                    if Path(file_path) != MODS_DIR and Path(file_path) != Path(self.log_file):
                        try:
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                        except Exception as e:
                            self.write_log(f"Ошибка при удалении файла/папки {file}: {str(e)}")
                            continue

                self.write_log("Все файлы и папки в каталоге удалены")
                self._deleting = False
                self._installing = True
                self.on_play_clicked()
                self._install_and_launch()

            threading.Thread(target=process_delete, daemon=True).start()

    def open_game_directory(self):
        subprocess.Popen(['explorer.exe', str(MC_DIR)])

    def handle_mod_action(self, mod_slug: str, action: str):
        try:
            self.write_log(f"Действие: {action} для мода {mod_slug}")
            mods_dir_path = os.path.join(str(MC_DIR), "mods")
            removed = 0
            exact_path = os.path.join(mods_dir_path, mod_slug)
            if os.path.exists(exact_path):
                if os.path.isdir(exact_path):
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
            else:
                self.write_log(f"Файлы для мода {mod_slug} не найдены")

            self.ui.refresh_installed_mods_display()
        except Exception as e:
            self.write_log(f"Ошибка при {action} мода {mod_slug}: {str(e)}")

    def default_memory_mb(self):
        mem = virtual_memory()
        total_mb = mem.total // (1024 * 1024)
        available_gb = mem.available / (1024 ** 3)
        if available_gb < 1:
            self._launching = False
            msg = QMessageBox(self)
            msg.setWindowTitle(t(self.lang, "not_enough_mem_title"))
            msg.setText(
                t(self.lang, "not_enough_mem_text").format(free=available_gb.__round__(1))
            )
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return 0

        if available_gb > 16:
            return min(total_mb // 2, 8192)
        elif available_gb > 8:
            return min(total_mb // 3, 4096)
        else:
            return 1024

    def write_log(self, msg: str, level: str = "INFO"):
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        log_entry = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [{level}] {str(msg)}"
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
            f.flush()
        self.log_signal.emit(log_entry, level)

    def write_warn(self, msg: str):
        self.write_log(msg, "WARN")

    def write_error(self, msg: str):
        self.write_log(msg, "ERROR")

    def on_play_clicked(self):
        self._launching = True
        self.ui.set_play_enabled(False)

        if not self.nickname:
            reply = QtWidgets.QMessageBox.question(
                self,
                t(self.lang, "login_title"),
                t(self.lang, "login_text"),
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.Yes
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self.auth_manager.start_login()
            else:
                self._launching = False
                self.ui.set_play_enabled(True)
                return 1

        mem = self.default_memory_mb()
        if mem == 0:
            self._launching = False
            self.write_warn("Недостаточно памяти для запуска")
            return
        self.write_log(f"[Память] Выделяем {mem} MB для Minecraft")
        self.options['jvmArguments'] = [f"-Xmx{int(mem)}M"]
        QtCore.QTimer.singleShot(100,
                                 lambda: threading.Thread(target=self._install_and_launch, daemon=True).start())

    def submit_logfile(self):
        ts = int(time.time())
        formatted_time = f"<t:{ts}:T>"
        with open(self.log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        skip = (
            "codepoint '20' declared multiple times",
            "missing textures in model",
            "missing texture references in model",
            "particle",
            "minecraft:block_or_item:cstrike",
            "tournamentadmin",
            "worlddownloader",
            "saved chunk nbt for",
            "ignoring chunk since",
            "unable to play unknown",
            "codepoint"
        )

        filtered = []
        for line in lines:
            clean_line = line.strip().lower()

            if not any(s in clean_line for s in skip):
                filtered.append(line)

        with open(self.log_file, "w", encoding="utf-8") as f:
            f.writelines(filtered)

        embed = {
            "title": "Лог",
            "description": f"\nВремя: {formatted_time}",
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
                timeout=3
            )
            fh_log.seek(0)
            self.write_log("[logs] log posted" if resp.ok else f"failed posting log ({resp.status_code})",
                           "INFO" if resp.ok else "ERROR")
        except Exception as e:
            self.write_log(f"Error submitting logfile: {str(e)}")
        finally:
            for fh in file_handles:
                fh.close()

    def _install_and_launch(self):
        try:
            if not self.nickname:
                self.write_warn("[Запуск] Нельзя запустить: никнейм не установлен")
                return 1

            def progress_callback(progress):
                self.ui.play_btn.setText(f"{t(self.lang, 'install_status')} {progress}")

            # Add servers to server list
            servers_to_add = [
                {"name": "Counter-Mine 2", "ip": "direct.cherry.pizza"},
                {"name": "Counter-Mine 2 (резерв)", "ip": "auth-tcpshield.cherry.pizza"}
            ]
            try:
                create_servers_dat(servers_to_add, str(MC_DIR))
                self.write_log(f"Файл servers.dat успешно создан с {len(servers_to_add)} серверами.")
            except Exception as e:
                self.write_error(f"Не удалось создать servers.dat: {e}")

            if not is_fabric_installed(str(MC_DIR), self.selected_version):
                self._launching = False
                self._installing = True
                self.write_log(f"[Установка] Начата загрузка Minecraft Fabric {self.selected_version}...")
                download_with_progress(self.selected_version, str(MC_DIR), progress_callback)
                self.write_log(f"[Установка] Minecraft Fabric {self.selected_version} успешно установлен")

            self._launching = True
            self._installing = False
            self.write_log(f"[Запуск] Подготовка запуска Minecraft {self.selected_version}...")

            fabric_version_id = None
            for v in minecraft_launcher_lib.utils.get_installed_versions(str(MC_DIR)):
                print(v)
                if v["id"].startswith("fabric-loader") and self.selected_version in v["id"]:
                    fabric_version_id = v["id"]
                    break
            print(fabric_version_id)

            if fabric_version_id:
                self.write_log(f"[Запуск] Найден загрузчик: {fabric_version_id}")
                cmd = minecraft_launcher_lib.command.get_minecraft_command(fabric_version_id, str(MC_DIR), self.options)
            else:
                self.write_error("[Запуск] Не найден загрузчик Fabric! Попробуйте переустановить клиент")
                self._launching = False
                self._installing = False
                self.show_message_signal.emit(
                    t(self.lang, "game_error_title"),
                    "Не найден загрузчик Fabric!Попробуйте переустановить клиент",
                    QMessageBox.Icon.Critical
                )
                return

            self.write_log(f"[Запуск] Java-команда: {cmd[0]}")

            with open(self.log_file, "a", encoding="utf-8") as f:
                popen_kwargs = {
                    'cwd': str(MC_DIR),
                    'stdout': subprocess.PIPE,
                    'stderr': subprocess.STDOUT,
                    'text': True,
                    'bufsize': 1,
                    'encoding': "UTF-8",
                }
                if sys.platform == 'win32':
                    popen_kwargs[
                        'creationflags'] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                else:
                    popen_kwargs['start_new_session'] = True

                self.process = subprocess.Popen(cmd, **popen_kwargs)
                self.minecraft_pid = self.process.pid
                self.write_log("[Запуск] Процесс Minecraft запущен (PID: " + str(self.process.pid) + ")")

                for line in self.process.stdout:
                    clean_line = line.strip()
                    f.write(clean_line + "\n")
                    f.flush()
                    if clean_line:
                        lower = clean_line.lower()
                        if any(k in lower for k in ("error", "exception", "crash", "fatal")):
                            self.log_signal.emit(f"[GAME] {clean_line}", "ERROR")
                        elif "warn" in lower:
                            self.log_signal.emit(f"[GAME] {clean_line}", "WARN")
                        else:
                            self.log_signal.emit(f"[GAME] {clean_line}", "GAME")

            ret = self.process.returncode
            if ret:
                self.write_error(f"[Запуск] Minecraft завершился с ошибкой, exit code: {ret}")
            else:
                self.write_log("[Запуск] Minecraft завершился успешно")

            self._launching = False
            self._installing = False

            threading.Thread(target=self.submit_logfile, daemon=True).start()

            if ret:
                self.show_message_signal.emit(
                    t(self.lang, "game_error_title"),
                    t(self.lang, "game_error_text"),
                    QMessageBox.Icon.Critical
                )

        except Exception as e:
            self.write_error(f"[Запуск] Непредвиденная ошибка: {e}")

    def _show_message(self, title, text, icon_type=QMessageBox.Icon.Warning):
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(icon_type)
        msg.exec()

    def _check_mc_state(self):
        running = is_mc_running(pid=self.minecraft_pid, version_str=self.selected_version)

        if running:
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
        else:
            if self._launching or self._installing or self._deleting:
                return
            self.fetcher.set_game(False)
            self.ui.set_play_status(t(self.lang, "play_button"))
            self.ui.set_play_enabled(True)
            if not self.isVisible():
                self.show()

    def start_move(self, event):
        if isinstance(event, QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton:
                self.old_pos = event.globalPosition()

    def do_move(self, event):
        if self.old_pos:
            delta = event.globalPosition() - self.old_pos
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
                    shutil.rmtree(exact_path)
                else:
                    os.remove(exact_path)
                removed = True
            else:
                for file in os.listdir(dir_path):
                    if slug.lower() in file.lower():
                        full_p = os.path.join(dir_path, file)
                        if os.path.isdir(full_p):
                            shutil.rmtree(full_p)
                        else:
                            os.remove(full_p)
                        removed = True
            if removed:
                self.ui.update_shader_status(slug, "remove")
        self.ui.refresh_installed_mods_display()

    def handle_resourcepack_action(self, slug: str, action: str):
        dir_path = os.path.join(str(MC_DIR), "resourcepacks")
        os.makedirs(dir_path, exist_ok=True)
        if action == "remove":
            removed = False
            exact_path = os.path.join(dir_path, slug)
            if os.path.exists(exact_path):
                if os.path.isdir(exact_path):
                    shutil.rmtree(exact_path)
                else:
                    os.remove(exact_path)
                removed = True
            else:
                for file in os.listdir(dir_path):
                    if slug.lower() in file.lower():
                        full_p = os.path.join(dir_path, file)
                        if os.path.isdir(full_p):
                            shutil.rmtree(full_p)
                        else:
                            os.remove(full_p)
                        removed = True
            if removed:
                self.ui.update_resourcepack_status(slug, "remove")
        self.ui.refresh_installed_mods_display()

    def exit_launcher(self):
        try:
            self.write_log("Closing...")
            self.hide()
            # Restore stdout/stderr before exit
            try:
                sys.stdout = self._orig_stdout
                sys.stderr = self._orig_stderr
            except Exception:
                pass
            self.mc_timer.stop()
            self.fetcher.stop()
            self.close()
            try:
                last_log = threading.Thread(target=self.submit_logfile)
                last_log.start()
                last_log.join()
            except:
                pass
            sys.exit(0)
        except Exception as e:
            print(e)

    def on_console_window_closed(self):
        self.ui.debug_console_switch.setChecked(False)


os.environ["QT_MULTIMEDIA_PREFERRED_PLUGINS"] = "windowsmediafoundation"


# os.environ["QT_QUICK_BACKEND"] = "software"



try:
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
except Exception as e:
    print(e)
finally:
    sys.exit(0)
