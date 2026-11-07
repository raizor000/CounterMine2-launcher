# fetcher.py
import threading
import json
import time

import requests
from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool
from mcstatus import JavaServer



class Fetcher(QObject):
    newsFetched = pyqtSignal(str, str)
    onlineFetched = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__()

        self.url = "https://raw.githubusercontent.com/theAndrew2808/CounterMine2-Launcher-Config/refs/heads/main/news.json"
        self.thread_pool = QThreadPool.globalInstance()

    def fetch_news_async(self):
        threading.Thread(target=self._run_news, daemon=True).start()

    def fetch_online_async(self, host="play.cherry.pizza"):
        threading.Thread(target=self._run_online, args=(host,), daemon=True).start()

    def _run_online(self, host):
        while True:
            try:
                server = JavaServer.lookup(host, timeout=5)
                status = server.status()
                text = f"ИГРАЮТ {status.players.online} ЧЕЛ."
            except Exception as e:
                print("Fetch online error:", e)
                text = "Ошибка :("
            self.onlineFetched.emit(text)
            time.sleep(1)  # обновляем раз в 1 секунду

    def _run_news(self):
        try:
            r = requests.get(self.url, timeout=6)
            r.raise_for_status()
            try:
                data = r.json()
                title = data.get("title", "")
                text_data = data.get("text", "")

                # Если текст список — склеиваем с переносами
                if isinstance(text_data, list):
                    text = "\n".join(text_data)
                else:
                    text = str(text_data)


            except Exception:
                # если не JSON — парсим как текст (первая строка — заголовок)
                txt = r.text.strip().splitlines()
                title = txt[0] if txt else "Новости"
                text = "\n".join(txt[1:]) if len(txt) > 1 else ""

            self.newsFetched.emit(title, text)

        except Exception as e:
            self.newsFetched.emit("Новости недоступны", "- Не удалось загрузить новости.")
            print(e)
