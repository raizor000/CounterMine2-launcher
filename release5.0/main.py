import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import traceback
import uuid
from pathlib import Path

import minecraft_launcher_lib
import requests
from packaging.version import parse
from psutil import virtual_memory
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QPoint, Qt, QCoreApplication, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QIcon, QMouseEvent, QPixmap
from PyQt6.QtWidgets import QMessageBox

from scripts.auth import CherryAuth
from scripts.constants import (
    LAUNCHER_DIR, LAUNCHER_VERSION, MC_DIR, MODS_DIR, VERSION,
    new_btn_style, new_dropdown_style, new_play_btn_style, new_play_menu_btn_style,
    new_switch_style, tabs_style_new,
)
from scripts.debug_console import DebugConsoleWindow
from scripts.fetcher import Fetcher
from scripts.game_files import sync_mods
from scripts.plugin_manager import PluginManager
from scripts.storage import atomic_write, remove_item, write_json
from scripts.ui import LauncherUI
from scripts.utilties import (
    SnowOverlay, create_server, create_servers_dat, download_with_progress,
    find_fabric_profile, get_new_logfile, get_resource_path, is_running, is_winter_period, t,
)


is_indev = not getattr(sys, "frozen", False) and not hasattr(sys, "_MEIPASS")
VERSION_PATTERN = re.compile(r"[1-9]\d*\.\d+(?:\.\d+)?")


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
        self._local = threading.local()

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
        buffer = getattr(self._local, "buffer", "") + text
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line.strip():
                level = self._detect_level(line, self._default_level)
                self._write(line, level)
        self._local.buffer = buffer
        return len(text)

    def flush(self):
        if self._original:
            try:
                self._original.flush()
            except Exception:
                pass
        buffer = getattr(self._local, "buffer", "").strip()
        if buffer:
            self._write(buffer, self._detect_level(buffer, self._default_level))
        self._local.buffer = ""

    def fileno(self):
        return self._original.fileno() if self._original else -1

    def isatty(self):
        return False


class LauncherApp(QtWidgets.QMainWindow):
    show_message_signal = pyqtSignal(str, str, QMessageBox.Icon)
    update_download_message = pyqtSignal(str)
    plugin_updates_checked = pyqtSignal(bool)
    log_signal = pyqtSignal(str, str)
    populate_versions_signal = pyqtSignal(list)
    auth_update_signal = pyqtSignal(object)
    game_task_finished = pyqtSignal()
    game_started = pyqtSignal()
    mods_changed = pyqtSignal()
    mod_task_finished = pyqtSignal()
    catalog_version_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.sound_enabled = True
        self.old_pos = None
        self._launching = False
        self._running = False
        self._deleting = False
        self._installing = False
        self.remote_plugins = []
        self.maintenance_data = []
        self.settings_data = {}
        self._mod_task_running = False
        self.process = None
        self._closing = False
        self.new_style = True
        self.show_debug_console = False
        self.plugin_states = {}
        self.nickname = None
        self.show_snow = True
        self.log_file = get_new_logfile(str(MC_DIR))
        self.lang = "ru_ru"
        self.ip = "0.0.0.0"
        self.minecraft_pid = -1
        self._auth_pending = True
        self.selected_version = VERSION
        self._launch_after_login = False

        self.setWindowTitle("CounterMine2 Launcher")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

        self.fetcher = Fetcher()
        self.ui = LauncherUI(LAUNCHER_VERSION, self.ip, self.lang, self)

        self.populate_versions_signal.connect(self.ui.fill_menu_items, QtCore.Qt.ConnectionType.QueuedConnection)
        self.auth_update_signal.connect(self.ui.update_auth_ui, QtCore.Qt.ConnectionType.QueuedConnection)

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

        self.ui.update_ui(self.lang)
        self.ui.header_frame.mousePressEvent = self.start_move
        self.ui.header_frame.mouseMoveEvent = self.do_move
        self.fetcher.set_lang(self.lang)

        self.icon_p = str(get_resource_path("assets/icons/ico.ico"))
        self.setWindowIcon(QIcon(self.icon_p))
        self.setCentralWidget(self.ui)

        html_path = Path(get_resource_path("scripts/html/cherryauth-index.html"))
        self.auth_manager = CherryAuth(LAUNCHER_DIR / "auth_token.json", html_path)

        self.snow = None
        if is_winter_period():
            self.snow = SnowOverlay(self.ui, QPixmap(get_resource_path("assets/pixmaps/snow1.png")))
            self.snow.setVisible(self.show_snow)
        else:
            self.ui.snow_label.hide()
            self.ui.snow_switch.hide()

        username = self.nickname or "user"
        offline_uuid = uuid.UUID(bytes=hashlib.md5(f"OfflinePlayer:{username}".encode()).digest(), version=3)
        self.options = minecraft_launcher_lib.types.MinecraftOptions(
            username=username,
            uuid=str(offline_uuid),
            token="",
            jvmArguments=["-Xmx1g"],
            launcherName="CounterMine2 Launcher by raizor",
            launcherVersion=LAUNCHER_VERSION,
            quickPlayMultiplayer="direct.cherry.pizza",
            server="direct.cherry.pizza",
            port="25565",
        )
        self.connect_signals()
        self.start_fetching()
        self.ui.set_play_enabled(False)
        threading.Thread(target=self.load_versions, daemon=True).start()
        threading.Thread(target=self._check_for_plugin_updates_async, daemon=True).start()

        self.mc_timer = QTimer()
        self.mc_timer.timeout.connect(self._check_mc_state)
        self.mc_timer.start(2000)

        threading.Thread(target=self.auth_manager.check_auth_status, daemon=True).start()

        self.apply_theme()

        self.plugin_manager.initialize_ui()

        QTimer.singleShot(50, lambda: (
            self.raise_(),
            self.activateWindow()
        ))

        QtCore.QTimer.singleShot(100, self.check_startup)

    def load_versions(self):
        versions = {VERSION, self.selected_version}
        try:
            versions.update(
                entry["id"] for entry in minecraft_launcher_lib.utils.get_version_list()
                if entry["type"] == "release" and VERSION_PATTERN.fullmatch(entry["id"])
                and parse(entry["id"]) >= parse(VERSION)
            )
        except Exception as exc:
            self.write_warn(f"Failed to get Minecraft versions: {exc}")
        self.populate_versions_signal.emit(sorted(versions, key=parse, reverse=True))

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
                self.plugin_states["CounterStrike2Theme"] = True
                self.save_settings()
                self.restart()

    def restart(self):
        self.write_log("Перезапуск лаунчера...")
        current_executable = sys.executable
        args = sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv
        self.instance_server.close()
        try:
            subprocess.Popen([current_executable, *args])
        except OSError as exc:
            self.instance_server = create_server(self)
            self.write_error(f"Could not restart launcher: {exc}")
            return
        self.close()

    def _check_for_plugin_updates_async(self):
        self.plugin_updates_checked.emit(self.fetch_remote_plugins())

    @property
    def is_cs2_theme_active(self) -> bool:
        return sys.platform == "win32" and any(
            type(plugin).__name__ == "CounterStrike2Theme" for plugin in self.plugin_manager.plugins
        )

    def fetch_remote_plugins(self):
        lang = self.lang
        filename = "plugins.json" if lang == "ru_ru" else "plugins_en.json"
        url = f"https://raw.githubusercontent.com/raizor000/CounterMine2-launcher-plugins/main/{filename}"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                entries = data.get("plugins", [])
                maintenance = data.get("maintenance", [])
            elif isinstance(data, list):
                entries = [entry for entry in data if isinstance(entry, dict) and entry.get("type") != "maintenance"]
                maintenance = [entry for entry in data if isinstance(entry, dict) and entry.get("type") == "maintenance"]
            else:
                raise ValueError("Unexpected marketplace format")
            if isinstance(entries, dict):
                entries = [entry for group in entries.values() if isinstance(group, list) for entry in group]
            if not isinstance(entries, list) or not isinstance(maintenance, list):
                raise ValueError("Unexpected marketplace format")
            if lang != self.lang:
                return False
            self.remote_plugins = [
                entry for entry in entries
                if isinstance(entry, dict) and isinstance(entry.get("id"), str)
                and isinstance(entry.get("name"), str)
            ]
            self.maintenance_data = [entry for entry in maintenance if isinstance(entry, dict)]
            return True
        except (ValueError, requests.RequestException) as exc:
            self.write_error(f"[Market] {exc}")
            return False

    def install_plugin_from_url(self, plugin_data):
        return self.plugin_manager.install_from_url(plugin_data, reload_plugins=False)

    def delete_external_plugin(self, plugin_id):
        return self.plugin_manager.delete_plugin(plugin_id)

    def on_auth_success(self, user_data):
        self.write_log(f"[Auth] Успешная авторизация: {user_data.get('nickname')}")
        self._auth_pending = False
        self.nickname = user_data.get("nickname")
        self.options["username"] = self.nickname
        self.options["uuid"] = str(user_data["id"])
        self.options["token"] = self.auth_manager.tokens.get("access_token", "")
        self.options["quickPlayMultiplayer"] = "direct.cherry.pizza"
        self.options["server"] = "direct.cherry.pizza"
        self.options["port"] = "25565"

        self.save_settings()

        self.auth_update_signal.emit(user_data)

        self._check_mc_state()

        if self._launch_after_login:
            self._launch_after_login = False
            self.write_log("[Auth] Продолжение запуска после входа в аккаунт...")
            self._start_game_launch(self._deleting)

    def on_auth_failed(self, error):
        self._auth_pending = False
        self.write_error(f"[Auth] {error}")
        if self._launch_after_login:
            self._launch_after_login = False
            self._finish_game_task()
        self._check_mc_state()
        if not self.auth_manager.user_data:
            self.auth_update_signal.emit({})
        self.show_message_signal.emit(t(self.lang, "login_title"), error, QMessageBox.Icon.Warning)

    def on_logged_out(self):
        self.write_log("[Auth] Пользователь вышел из аккаунта")
        self._auth_pending = False
        self.nickname = None
        offline_username = "user"
        offline_uuid = str(uuid.UUID(bytes=hashlib.md5(b"OfflinePlayer:user").digest(), version=3))
        self.options["username"] = offline_username
        self.options["uuid"] = offline_uuid
        self.options["token"] = ""
        self.options["quickPlayMultiplayer"] = "direct.cherry.pizza"
        self.options["server"] = "direct.cherry.pizza"
        self.options["port"] = "25565"

        self.save_settings()

        self.auth_update_signal.emit({})
        if self._launch_after_login:
            self._launch_after_login = False
            self._finish_game_task()
        self._check_mc_state()

    def on_settings_changed(self, key: str, value: object):
        try:
            if key == "lang":
                match value:
                    case "English":
                        self.lang = "en_us"
                    case "Русский":
                        self.lang = "ru_ru"
                self.save_settings()
                if not self._game_busy():
                    path = MC_DIR / "options.txt"
                    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
                    lines = [line for line in lines if not line.startswith("lang:")]
                    lines.append(f"lang:{self.lang}")
                    atomic_write(path, lambda stream: stream.write(("\n".join(lines) + "\n").encode("utf-8")))
                self.ui.update_ui(self.lang)
                self.console_window.update_ui(self.lang)
                self.fetcher.set_lang(self.lang)
                self.fetcher.fetch_news_now()
                for plugin in self.plugin_manager.plugins:
                    plugin.on_language_change(lang=self.lang)

            elif key == "snow" and self.snow is not None:
                self.show_snow = bool(value)
                self.save_settings()
                if self.show_snow:
                    self.snow.show()
                    self.ui.snow_switch.setChecked(bool(self.show_snow))
                else:
                    self.snow.hide()
                    self.ui.snow_switch.setChecked(bool(self.show_snow))

            elif key == "sound_enabled":
                self.sound_enabled = bool(value)
                self.save_settings()

            elif key == "debug_console":
                self.show_debug_console = bool(value)
                self.save_settings()
                if self.show_debug_console:
                    self.console_window.show()
                else:
                    self.console_window.hide()

            elif key == "plugin_state":
                plugin_id, enabled, restart_required = value

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
                reply = QMessageBox.question(self, "Плагины",
                                        f"Для применения изменений следующего плагина требуется перезапуск лаунчера: \n{plugin_id} \n\nПерезапустить сейчас?",
                                     QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Cancel
                                     )
                if reply == QMessageBox.StandardButton.Ok:
                    self.restart()

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
        self.ui.snow_switch.setOnColor(new_switch_style)
        self.ui.lang_dropdown.setSelectedColor(new_dropdown_style)
        self.ui.debug_console_switch.setStyleSheet(new_btn_style)

    def save_settings(self):
        settings = {
            "nickname": self.nickname,
            "lang": self.lang,
            "sound_enabled": self.sound_enabled,
            "snow": self.show_snow,
            "new_style": self.new_style,
            "plugin_states": self.plugin_states,
            "show_debug_console": self.show_debug_console,
            "selected_version": self.selected_version
        }
        try:
            write_json(LAUNCHER_DIR / "settings.json", settings)
        except OSError as exc:
            self.write_error(f"Could not save settings: {exc}")

    def load_settings(self):
        path = LAUNCHER_DIR / "settings.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
            if not isinstance(data, dict):
                raise ValueError("Expected a settings object")
        except (OSError, ValueError) as exc:
            self.write_warn(f"Could not load settings: {exc}")
            data = {}

        self.settings_data = data
        self.nickname = data.get("nickname") if isinstance(data.get("nickname"), str) else None
        self.lang = data["lang"] if data.get("lang") in ("en_us", "ru_ru") else self.lang
        self.show_snow = bool(data.get("snow", self.show_snow))
        self.sound_enabled = bool(data.get("sound_enabled", self.sound_enabled))
        self.new_style = bool(data.get("new_style", self.new_style))
        self.show_debug_console = bool(data.get("show_debug_console", self.show_debug_console))
        states = data.get("plugin_states")
        self.plugin_states = states if isinstance(states, dict) else {}
        self.plugin_states.setdefault("CurseForgePlugin", False)
        self.plugin_states.setdefault("ModrinthPlugin", not self.plugin_states["CurseForgePlugin"])
        if self.plugin_states["ModrinthPlugin"]:
            self.plugin_states["CurseForgePlugin"] = False
        self.plugin_states.setdefault("CounterStrike2Theme", False)
        saved_version = data.get("selected_version")
        if isinstance(saved_version, str) and VERSION_PATTERN.fullmatch(saved_version):
            self.selected_version = saved_version

        self.ui.snow_switch.setChecked(self.show_snow)
        self.ui.debug_console_switch.setChecked(self.show_debug_console)
        self.ui.lang_dropdown.current = "Русский" if self.lang == "ru_ru" else "English"

    def start_fetching(self):
        self.fetcher.fetch_news_async()
        self.fetcher.fetch_online_async()

    def connect_signals(self):
        self.ui.play_clicked.connect(self.on_play_clicked)
        self.ui.menu_item_clicked.connect(self.on_version_selected)
        self.ui.reinstall_client.connect(self.reinstall_client)
        self.ui.mod_action.connect(self.handle_mod_action)
        self.ui.shader_action.connect(self.handle_shader_action)
        self.ui.resourcepack_action.connect(self.handle_resourcepack_action)
        self.update_download_message.connect(self.ui.set_play_status)
        self.game_task_finished.connect(self._finish_game_task)
        self.game_started.connect(self._check_mc_state)
        self.mods_changed.connect(self._refresh_mods)
        self.mod_task_finished.connect(self._finish_mod_task)
        self.auth_manager.token_refreshed.connect(self._on_token_refreshed)
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

    def _on_plugin_updates_checked(self, success):
        if not success:
            return
        self.plugin_manager.check_for_updates()
        if self.ui.plugins_manager_container.isVisible():
            self.ui._populate_plugins()
        updates = [
            f"{plugin['name']} {plugin['version']} → {plugin['latest_version']}"
            for plugin in self.plugin_manager.discovered_plugins if plugin.get("update_available")
        ]
        if updates:
            self._show_message(
                t(self.lang, "plugin_update_confirm_title"), "\n".join(updates), QMessageBox.Icon.Information
            )

    def _on_token_refreshed(self, token):
        self.options["token"] = token

    def _game_busy(self):
        return self._launching or self._installing or self._deleting or self._running

    def _swap_mods(self, new_version, old_version):
        sync_mods(MODS_DIR, new_version, old_version)

    def on_version_selected(self, version_id: str):
        if self._game_busy() or self._mod_task_running or not VERSION_PATTERN.fullmatch(version_id):
            for action in self.ui.version_action_group.actions():
                action.setChecked(action.text() == self.selected_version)
            return
        if version_id == self.selected_version:
            return
        try:
            self._swap_mods(version_id, self.selected_version)
        except (OSError, ValueError) as exc:
            self._show_message(t(self.lang, "game_error_title"), str(exc))
            for action in self.ui.version_action_group.actions():
                action.setChecked(action.text() == self.selected_version)
            return
        self.selected_version = version_id
        self.save_settings()
        self._refresh_mods()
        self.catalog_version_changed.emit()

    def reinstall_client(self):
        if self._game_busy() or self._mod_task_running:
            return
        reply = QMessageBox.question(
            self, t(self.lang, "reinstall_title"), t(self.lang, "reinstall_text"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.on_play_clicked(reinstall=True)

    def open_game_directory(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(MC_DIR)))

    def handle_mod_action(self, name, action):
        self._remove_game_item(MODS_DIR / self.selected_version, name, action, sync=True)

    def _remove_game_item(self, directory, name, action, *, sync=False):
        if action != "remove" or self._game_busy() or self._mod_task_running:
            return
        try:
            if sync:
                self._swap_mods(self.selected_version, self.selected_version)
            remove_item(directory, name)
            if sync:
                self._swap_mods(self.selected_version, self.selected_version)
        except (OSError, ValueError) as exc:
            self._show_message(t(self.lang, "general_error_title"), str(exc))
        finally:
            self._refresh_mods()

    def _refresh_mods(self):
        self.ui.refresh_installed_mods_display()
        for plugin in self.plugin_manager.plugins:
            if hasattr(plugin, "refresh_signal"):
                plugin.refresh_signal.emit()

    def start_mod_task(self, task, *args):
        if self._game_busy() or self._mod_task_running:
            return
        self._mod_task_running = True
        version_id = self.selected_version
        self._check_mc_state()

        def run():
            try:
                self._swap_mods(version_id, version_id)
                task(*args, version_id)
                self._swap_mods(version_id, version_id)
            except Exception as exc:
                self.write_error(f"[Mods] {exc}")
                self.show_message_signal.emit(t(self.lang, "game_error_title"), str(exc), QMessageBox.Icon.Warning)
            finally:
                self.mod_task_finished.emit()

        threading.Thread(target=run, daemon=True).start()

    def _finish_mod_task(self):
        self._mod_task_running = False
        self._refresh_mods()
        self._check_mc_state()

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
        log_entry = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [{level}] {str(msg)}"
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry + "\n")
        except OSError:
            pass
        self.log_signal.emit(log_entry, level)

    def write_warn(self, msg: str):
        self.write_log(msg, "WARN")

    def write_error(self, msg: str):
        self.write_log(msg, "ERROR")

    def _start_game_launch(self, reinstall=False):
        mem = self.default_memory_mb()
        if mem == 0:
            self._finish_game_task()
            return
        options = dict(self.options, jvmArguments=[f"-Xmx{mem}M"])
        threading.Thread(
            target=self._install_and_launch,
            args=(self.selected_version, options, reinstall),
            daemon=True,
        ).start()

    def on_play_clicked(self, reinstall=False):
        if self._auth_pending or self._game_busy() or self._mod_task_running:
            return
        self._launching = True
        self._deleting = reinstall
        self._check_mc_state()
        if not self.options["token"] and not is_indev:
            reply = QMessageBox.question(
                self, t(self.lang, "login_title"), t(self.lang, "login_text"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._launch_after_login = True
                self.auth_manager.start_login()
            else:
                self._finish_game_task()
            return
        self._start_game_launch(reinstall)

    def _install_and_launch(self, version_id, options, reinstall):
        try:
            if reinstall:
                for name in ("versions", "libraries", "assets", "runtime"):
                    remove_item(MC_DIR, name)
            self._deleting = False
            self._swap_mods(version_id, version_id)

            try:
                create_servers_dat([
                    {"name": "Counter-Mine 2", "ip": "direct.cherry.pizza"},
                    {"name": "Counter-Mine 2 (резерв)", "ip": "auth-tcpshield.cherry.pizza"},
                    {"name": "Игры разума", "ip": "razum.dev"},
                ], str(MC_DIR))
            except OSError as exc:
                self.write_warn(f"Could not create servers.dat: {exc}")

            fabric_id = find_fabric_profile(str(MC_DIR), version_id)
            if not fabric_id:
                self._installing = True
                fabric_id = download_with_progress(
                    version_id, str(MC_DIR),
                    lambda progress: self.update_download_message.emit(
                        f"{t(self.lang, 'install_status')} {progress}"
                    ),
                )
                self._installing = False
                self.update_download_message.emit(t(self.lang, "launching_status"))

            if self.options["uuid"] == options["uuid"]:
                options["token"] = self.options["token"]
            elif not is_indev:
                raise ValueError("The Cherry account changed while preparing the game.")
            command = minecraft_launcher_lib.command.get_minecraft_command(fabric_id, str(MC_DIR), options)
            kwargs = {
                "cwd": str(MC_DIR), "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT,
                "text": True, "encoding": "utf-8", "errors": "replace",
            }
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            else:
                kwargs["start_new_session"] = True

            with subprocess.Popen(command, **kwargs) as process:
                self.process = process
                self.minecraft_pid = process.pid
                self.game_started.emit()
                self.write_log(f"[Launch] Minecraft PID {process.pid}")
                for line in process.stdout:
                    line = line.rstrip()
                    token = options["token"]
                    if token:
                        line = line.replace(token, "[redacted]")
                    if line:
                        self.write_log(f"[GAME] {line}", _StdoutRedirector._detect_level(line, "GAME"))
                exit_code = process.wait()
            if exit_code:
                self.write_error(f"Minecraft exited with code {exit_code}")
                self.show_message_signal.emit(
                    t(self.lang, "game_error_title"),
                    f"{t(self.lang, 'game_error_text')}({exit_code})",
                    QMessageBox.Icon.Critical,
                )
        except Exception as exc:
            self.write_error(f"[Launch] {traceback.format_exc()}")
            self.show_message_signal.emit(
                t(self.lang, "game_error_title"), str(exc), QMessageBox.Icon.Critical,
            )
        finally:
            self.game_task_finished.emit()

    def _finish_game_task(self):
        self._launching = self._installing = self._deleting = False
        self.process = None
        self.minecraft_pid = -1
        self._check_mc_state()

    def _show_message(self, title, text, icon_type=QMessageBox.Icon.Warning):
        if self._closing:
            return
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setTextFormat(Qt.TextFormat.PlainText)
        msg.setText(text)
        msg.setIcon(icon_type)
        msg.exec()

    def _check_mc_state(self):
        was_running = self._running
        self._running = self.process is not None and self.process.poll() is None
        self.fetcher.set_game(self._running)
        for plugin in self.plugin_manager.plugins:
            on_game_state = getattr(plugin, "on_game_state_changed", None)
            if on_game_state and was_running != self._running:
                on_game_state(self._running)
        self.ui.set_play_enabled(not (self._auth_pending or self._game_busy() or self._mod_task_running))
        self.ui.menu_btn.setEnabled(not (self._game_busy() or self._mod_task_running))
        self.ui.reinstall_btn.setEnabled(not (self._game_busy() or self._mod_task_running or self._auth_pending))
        if self._running:
            self.ui.set_play_status(t(self.lang, "in_game_status"))
            if not was_running:
                self.hide()
        else:
            if was_running and not self._closing:
                self.show()
            if self._deleting:
                self.ui.set_play_status(t(self.lang, "cleanup_status"))
            elif not self._installing:
                self.ui.set_play_status(t(self.lang, "launching_status" if self._launching else "play_button"))

    def start_move(self, event):
        if isinstance(event, QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton:
                self.old_pos = event.globalPosition()

    def do_move(self, event):
        if self.old_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
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

    def handle_shader_action(self, name, action):
        self._remove_game_item(MC_DIR / "shaderpacks", name, action)

    def handle_resourcepack_action(self, name, action):
        self._remove_game_item(MC_DIR / "resourcepacks", name, action)

    def closeEvent(self, event):
        self._closing = True
        self.mc_timer.stop()
        self.fetcher.stop()
        self.auth_manager.stop()
        self.plugin_manager.stop()
        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr
        self.console_window.hide()
        super().closeEvent(event)
        QCoreApplication.quit()

    def exit_launcher(self):
        self.close()

    def on_console_window_closed(self):
        self.ui.debug_console_switch.setChecked(False)
        self.on_settings_changed("debug_console", False)


def main():
    if sys.platform == "win32":
        os.environ.setdefault("QT_MULTIMEDIA_PREFERRED_PLUGINS", "windowsmediafoundation")
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QtWidgets.QApplication(sys.argv)
    if is_running():
        return 0

    window = LauncherApp()
    window.instance_server = create_server(window)
    window.show()
    window.raise_()
    window.activateWindow()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
