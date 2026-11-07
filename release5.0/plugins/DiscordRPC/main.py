from datetime import datetime
import threading
import time

from pypresence import Presence, exceptions

from scripts.constants import MODRINTH_TAB_INDEX
from scripts.plugin_manager import BasePlugin


class DiscordRPCPlugin(BasePlugin):
    name = "Discord Rich Presence"
    description = "Интеграция Discord RPC"
    author = "raizor"
    version = "1.0.1"
    icon = "discord.png"

    def on_load(self):
        self.start_time = int(time.time())
        self._stop_event = threading.Event()
        self._thread = None

    def on_ui_ready(self):
        if not self._thread or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def on_unload(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=0.5)

    def _run(self):
        while not self._stop_event.is_set():
            rpc = None
            try:
                rpc = Presence("1493262434566144000")
                rpc.connect()
                while not self._stop_event.is_set():
                    rpc.update(**self._presence())
                    self._stop_event.wait(15)
            except (exceptions.InvalidPipe, exceptions.DiscordNotFound, ConnectionRefusedError):
                pass
            except Exception as exc:
                self.app.write_warn(f"[RPC] {exc}")
            finally:
                if rpc is not None and getattr(rpc, "sock_writer", None) is not None:
                    try:
                        rpc.close()
                    except Exception as exc:
                        self.app.write_warn(f"[RPC] Could not close Discord connection: {exc}")
            self._stop_event.wait(15)

    def _presence(self):
        season = ("winter", "spring", "summer", "autumn")[(datetime.now().month % 12) // 3]
        state = "Бездействует"
        if self.app._running:
            state = "В игре"
        elif self.app._deleting or self.app._installing:
            state = "Устанавливает игру"
        elif self.app._launching:
            state = "Входит в игру"
        elif getattr(self.app.ui, "_current_tab_index", 0) == MODRINTH_TAB_INDEX:
            state = "Просматривает моды"
        return {
            "details": f"Версия: {self.app.selected_version}",
            "state": state,
            "large_image": f"icon_{season}",
            "large_text": "CounterMine2 Launcher",
            "start": self.start_time,
            "buttons": [
                {"label": "Сайт", "url": "https://cherry.pizza"},
                {"label": "Новости", "url": "https://cm2news.xyz/news"},
            ],
        }
