import time
import threading

from pypresence import Presence, exceptions
from requests_cache import datetime
from scripts.plugin_manager import BasePlugin
from scripts.constants import MODRINTH_TAB_INDEX


class DiscordRPCPlugin(BasePlugin):
    name = "Discord Rich Presence"
    description = "Интеграция Discord RPC"
    author = "raizor"
    version = "1.0.0"
    icon = "discord.png"

    def on_load(self):
        print(f"[{self.name}] Плагин загружен.")
        self.rpc = None
        self.start_time = int(time.time())
        self.thread = None
        self.launcher = self.app

    def on_ui_ready(self):
        self.start_thread()

    def start_thread(self):
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        while True:
            if not self.rpc:
                try:
                    self.rpc = Presence("1493262434566144000")
                    self.rpc.connect()
                    self.launcher.write_log("[RPC] Discord Rich Presence подключен.")
                    self.update_presence()
                except (exceptions.InvalidPipe, exceptions.DiscordNotFound, ConnectionRefusedError):
                    self.rpc = None
                    time.sleep(15)
                    continue
                except Exception as e:
                    self.rpc = None
                    self.launcher.write_log(f"[RPC] Не удалось подключиться к Discord: {e}", level="WARN")
                    time.sleep(15)
                    continue

            self.update_presence()
            time.sleep(10)

    def update_presence(self, *args):
        logo = None
        if datetime.now().month in [9, 10, 11]:
            logo = "icon_autumn"
        elif datetime.now().month in [12, 1, 2]:
            logo = "icon_winter"
        elif datetime.now().month in [3, 4, 5]:
            logo = "icon_spring"
        elif datetime.now().month in [6, 7, 8]:
            logo = "icon_summer"

        state = "Бездействует"
        if self.launcher._running:
            state = "В игре"
        elif self.launcher._launching:
            state = "Входит в игру"
        elif self.launcher._installing:
            state = "Устанавливает игру"
        elif self.launcher.ui._current_tab_index == MODRINTH_TAB_INDEX:
            state = "Просматривает моды"

        if not self.rpc:
            return

        try:
            self.rpc.update(
                details="Версия: {self.launcher.selected_version}",
                state=f"{state}",
                large_image=f"{logo}",
                large_text="CounterMine2 Launcher",
                start=self.start_time,
                buttons=[
                    {"label": "Сайт", "url": "https://cherry.pizza"},
                    {"label": "Новости", "url": "https://cm2news.xyz/news"},
                    {"label": "Лаунчер", "url": "https://discord.gg/Gg2fy7VzEV"}
                ]
            )
        except Exception:
            self.rpc = None

    def disconnect(self):
        if self.rpc:
            try:
                self.rpc.close()
                self.launcher.write_log("[RPC] Discord Rich Presence отключен.")
            except Exception:
                pass
            finally:
                self.rpc = None

    def on_exit(self):
        self.disconnect()
