import json
import threading

import ping3
from PyQt6.QtCore import QObject
from mcstatus import JavaServer

from .utilties import *


class Fetcher(QObject):
    newsFetched = pyqtSignal(list)
    onlineFetched = pyqtSignal(int, str)

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

    def fetch_news_now(self):
        threading.Thread(target=self._fetch_news_once, daemon=True).start()

    def fetch_online_now(self):
        threading.Thread(target=self._fetch_online_once, daemon=True).start()

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

    def _safe_request(self, method, url, **kwargs):
        if not self._session:
            self._session = requests.Session()
            self._session.headers.update({'Connection': 'close'})
        try:
            resp = self._session.request(method, url, **kwargs)
            return resp
        except Exception as e:
            print(f"[Fetcher] Request to {url} failed: {e}. Resetting session connection pool.")
            if self._session:
                try:
                    self._session.close()
                except:
                    pass
                self._session = None
            raise e

    def _run_online(self):
        while not self._stop_event.is_set():
            if not self.in_game:
                self._fetch_online_once()

                if self._stop_event.wait(10):
                    break
            else:
                if self._stop_event.wait(2):
                    break

    def _run_news(self):
        while not self._stop_event.is_set():
            if not self.in_game:
                self._fetch_news_once()

                if self._stop_event.wait(120):
                    break
            else:
                if self._stop_event.wait(2):
                    break

    def _fetch_online_once(self):
        try:
            server = JavaServer.lookup(host, timeout=5)
            status = server.status()
            online_count = status.players.online

            try:
                ping_ms = ping3.ping(dest_addr="direct.cherry.pizza", unit="ms")
                if ping_ms is not None:
                    ping_text = f"{int(ping_ms)} {t(self.lang, 'ms_locale')}"
                else:
                    ping_text = "- мс"
            except Exception as e:
                print(f"[Fetcher] Failed to calculate ping: {e}")
                latency = getattr(status, "latency", None)
                if latency is not None:
                    ping_text = f"{int(latency)} {t(self.lang, 'ms_locale')}"
                else:
                    ping_text = "- мс"

        except Exception as e:
            print(f"[Fetcher] Fetch online error: {e}")
            online_count = -1
            ping_text = t(self.lang, "online_label_unknown")

        self.onlineFetched.emit(online_count, ping_text)

    def _fetch_news_once(self):
        cache_path = LAUNCHER_DIR / "news_cache.json"
        try:
            r = self._safe_request("GET", news_url if self.lang == "ru_ru" else news_en_url, timeout=3)
            r.raise_for_status()
            data = r.json()

            if not isinstance(data, list):
                print(f"[Fetcher] Unexpected news format: {data}")
                self.newsFetched.emit([])
                return
            self.newsFetched.emit(data)

            try:
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as ce:
                print(f"[Fetcher] Failed to save news cache: {ce}")

        except Exception as e:
            print(f"[Fetcher] Failed to fetch news: {e}")
            if cache_path.exists():
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        cached_data = json.load(f)
                    print("[Fetcher] News loaded from local cache.")
                    self.newsFetched.emit(cached_data)
                except Exception as le:
                    print(f"[Fetcher] Failed to load news cache: {le}")
                    self.newsFetched.emit([])
            else:
                self.newsFetched.emit([])