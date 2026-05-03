import threading
import time

import ping3
from PyQt6.QtCore import QObject
from mcstatus import JavaServer

from .utilties import *


class Fetcher(QObject):
    newsFetched = pyqtSignal(list)
    onlineFetched = pyqtSignal(str, str)
    queueFetched = pyqtSignal(list)
    banFetched = pyqtSignal(bool, list, str)
    practiceQueueFetched = pyqtSignal(list, dict)

    def __init__(self):
        super().__init__()
        self.lang = "en_us"
        self.in_game = False
        self._stop_event = threading.Event()
        self._session = None
        self._threads = []

    def fetch_news_async(self):
        thread = threading.Thread(target=self._run_news, daemon=True)
        thread.start()
        self._threads.append(thread)

    def fetch_online_async(self):
        thread = threading.Thread(target=self._run_online, daemon=True)
        thread.start()
        self._threads.append(thread)

    def fetch_practice_queue_async(self):
        thread = threading.Thread(target=self._run_practice_queue, daemon=True)
        thread.start()
        self._threads.append(thread)

    def fetch_queue_async(self):
        thread = threading.Thread(target=self._run_queue, daemon=True)
        thread.start()
        self._threads.append(thread)

    def set_lang(self, lang):
        self.lang = lang

    def set_game(self, game):
        self.in_game = bool(game)
    
    def stop(self):
        self._stop_event.set()
        for thread in self._threads:
            thread.join(timeout=2)
        self._threads.clear()
        if self._session:
            self._session.close()
            self._session = None

    def _run_queue(self):
        while not self._stop_event.is_set():
            if not self.in_game:
                try:
                    resp = requests.post(
                        QUEUE_URL2,
                        json={"action": "queue5vs5"},
                        timeout=5
                    )

                    if resp.status_code == 200:
                        data = resp.json()
                        players = data.get("ru", [])
                        names = []
                        for p in players:
                            nick = p.get("minecraft_nick")
                            rating = p.get("rating", "—")
                            if nick:
                                names.append((str(nick).strip(), str(rating).strip()))
                    else:
                        names = []

                except Exception as e:
                    names = []
                    print(f"[Queue Fetcher] Error: {e}")

                self.queueFetched.emit(names)

                if self._stop_event.wait(5):
                    break
            else:
                if self._stop_event.wait(2):
                    break

    def _run_practice_queue(self):
        # session = requests.Session()
        # while True:
        #     if self.in_game:
        #         time.sleep(2)
        #         continue
        #
        #     try:
        #         r_queue = session.get(PRACTICE_QUEUE_URL, timeout=5)
        #         r_active = session.get(ACTIVE_PRACTICE_QUEUE_URL, timeout=5)
        #
        #         searching_clans = []
        #         active_practices = {}
        #
        #         if r_queue.ok:
        #             data = r_queue.json()
        #             if isinstance(data, dict):
        #                 data = data.get("queue", [])
        #             if isinstance(data, list):
        #                 searching_clans = [x for x in data if isinstance(x, str)]
        #
        #         if r_active.ok:
        #             data = r_active.json()
        #             if isinstance(data, dict):
        #                 active_practices = {
        #                     k: [a.strip(), b.strip()]
        #                     for k, v in data.items()
        #                     if isinstance(v, list)
        #                        and len(v) == 2
        #                        and all(isinstance(x, str) for x in v)
        #                     for a, b in [v]
        #                 }
        #
        #         self.practiceQueueFetched.emit(searching_clans, active_practices)
        #
        #     except requests.RequestException as e:
        #         print(f"[Practice Fetcher] Network error: {e}")
        #         self.practiceQueueFetched.emit([], {})
        #     except Exception as e:
        #         print(f"[Practice Fetcher] Unexpected error: {e}")
        #         self.practiceQueueFetched.emit([], {})
        #     time.sleep(15)
        pass

    def _run_online(self):
        while not self._stop_event.is_set():
            if not self.in_game:
                try:
                    server = JavaServer.lookup(host, timeout=5)
                    status = server.status()
                    ping_ms = ping3.ping(dest_addr="play.cherry.pizza", unit="ms")
                    text = t(self.lang, "online_label").format(count=status.players.online)
                    ping_text = f"{int(ping_ms)} {t(self.lang, 'ms_locale')}"
                except Exception as e:
                    print(f"Fetch online error: {e}")
                    text = "Ошибка :("
                    ping_text = "Ошибка"

                self.onlineFetched.emit(text, ping_text)
                if self._stop_event.wait(20):
                    break
            else:
                if self._stop_event.wait(2):
                    break

    def _run_news(self):
        if not self._session:
            self._session = requests.Session()
        
        while not self._stop_event.is_set():
            if self.in_game:
                if self._stop_event.wait(2):
                    break
                continue
            try:
                for url in (news_url1, news_url):
                    try:
                        r = self._session.get(url, timeout=5)
                        r.raise_for_status()
                        data = r.json()

                        if not isinstance(data, list):
                            raise ValueError("Ожидался список новостей")
                        self.newsFetched.emit(data)
                        break
                    except Exception:
                        continue
                else:
                    self.newsFetched.emit([])
            except Exception as e:
                print(f"Fetch news error: {e}")
                self.newsFetched.emit([])
            if self._stop_event.wait(120):
                break
