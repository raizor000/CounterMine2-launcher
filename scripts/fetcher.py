# fetcher.py
import threading
import time

import requests
from PyQt6.QtCore import QObject, pyqtSignal, QThreadPool
from mcstatus import JavaServer


class Fetcher(QObject):
    newsFetched = pyqtSignal(str, str)
    onlineFetched = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.url = "https://raw.githubusercontent.com/theAndrew2808/CounterMine2-Launcher-Config/refs/heads/main/news.json"
        self.host = "play.cherry.pizza"
        self.thread_pool = QThreadPool.globalInstance()

    def fetch_news_async(self):
        threading.Thread(target=self._run_news, daemon=True).start()

    def fetch_online_async(self, ):
        threading.Thread(target=self._run_online, daemon=True).start()

    def _run_online(self):
        while True:
            try:
                server = JavaServer.lookup(self.host, timeout=5)
                status = server.status()
                text = f"ИГРАЮТ {status.players.online} ЧЕЛ."
            except Exception as e:
                print("Fetch online error:", e)
                text = "Ошибка :("
            # noinspection PyUnresolvedReferences
            self.onlineFetched.emit(text)
            time.sleep(60)

    def _run_news(self):
        try:
            r = requests.get(self.url, timeout=6)
            r.raise_for_status()
            try:
                data = r.json()
                title = data.get("title", "")
                text_data = data.get("text", "")
                if isinstance(text_data, list):
                    text = "\n".join(text_data)
                else:
                    text = str(text_data)
                # noinspection PyUnresolvedReferences
                self.newsFetched.emit(title, text)

            except Exception as e:
                print(e)
        except Exception as e:
            # noinspection PyUnresolvedReferences
            self.newsFetched.emit("Новости недоступны", "- Не удалось загрузить новости.")
            print(e)
