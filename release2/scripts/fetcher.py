import threading
import time

import requests
from mcstatus import JavaServer

from PyQt6.QtCore import QObject, pyqtSignal

from .constants import news_url, host


class Fetcher(QObject):
    newsFetched = pyqtSignal(list)
    onlineFetched = pyqtSignal(str)

    def __init__(self):
        super().__init__()

    def fetch_news_async(self):
        threading.Thread(target=self._run_news, daemon=True).start()

    def fetch_online_async(self):
        threading.Thread(target=self._run_online, daemon=True).start()

    def _run_online(self):
        while True:
            try:
                server = JavaServer.lookup(host, timeout=5)
                status = server.status()
                text = f"ИГРАЮТ {status.players.online} ЧЕЛ."
            except Exception as e:
                print(f"Fetch online error: {e}")
                text = "Ошибка :("
            self.onlineFetched.emit(text)
            time.sleep(60)

    def _run_news(self):
        try:
            r = requests.get(news_url, timeout=6)
            r.raise_for_status()
            data = r.json()  # Ожидаем список: [{"title": "", "text": "", "date": ""}, ...]
            if not isinstance(data, list):
                raise ValueError("Ожидался список новостей")
            self.newsFetched.emit(data)  # Эммитим список
        except Exception as e:
            self.newsFetched.emit([])  # Пустой список при ошибке
            print(f"Fetch news error: {e}")