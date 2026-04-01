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

    def fetch_news_async(self):
        threading.Thread(target=self._run_news, daemon=True).start()

    def fetch_online_async(self):
        threading.Thread(target=self._run_online, daemon=True).start()

    def fetch_practice_queue_async(self):
        threading.Thread(target=self._run_practice_queue, daemon=True).start()

    def fetch_queue_async(self):
        threading.Thread(target=self._run_queue, daemon=True).start()

    def set_lang(self, lang):
        self.lang = lang

    def set_game(self, game):
        self.in_game = bool(game)

    def _run_queue(self):
        while True:
            if not self.in_game:
                try:
                    # for url in (QUEUE_URL, QUEUE_URL2):
                        resp = requests.get(QUEUE_URL2, timeout=5)
                        if resp.status_code == 200:
                            data = resp.json()
                            players = data.get("ru", [])
                            # Валидируем и преобразуем данные в строки
                            names = []
                            for p in players:
                                nick = p.get("minecraft_nick")
                                rating = p.get("rating", "—")
                                # Пропускаем невалидные ники
                                if nick:
                                    names.append((str(nick).strip(), str(rating).strip()))
                        else:
                            names = []
                            # continue
                except Exception as e:
                    names = []
                    print(f"[Queue Fetcher] Error: {e}")

                self.queueFetched.emit(names)
                time.sleep(5)
            else:
                time.sleep(2)

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
        while True:
            if not self.in_game:
                try:
                    server = JavaServer.lookup(host, timeout=5)
                    status = server.status()
                    # ping_ms = status.latency #Костыль, показывает не настоящий пинг после добавления мульти-серверов
                    ping_ms = ping3.ping(dest_addr="play.cherry.pizza", unit="ms")
                    text = t(self.lang, "online_label").format(count=status.players.online)
                    ping_text = f"{int(ping_ms)} {t(self.lang, 'ms_locale')}"
                except Exception as e:
                    print(f"Fetch online error: {e}")
                    text = "Ошибка :("
                    ping_text = "Ошибка"

                self.onlineFetched.emit(text, ping_text)
                time.sleep(20)
            else:
                time.sleep(2)

    def _run_news(self):
        session = requests.Session()
        while True:
            if self.in_game:
                time.sleep(2)
                continue
            try:
                for url in (news_url1, news_url):
                    try:
                        r = session.get(url, timeout=5)
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
            time.sleep(120)
