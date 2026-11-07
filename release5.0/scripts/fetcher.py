import json
import threading

import requests
from PyQt6.QtCore import QObject, pyqtSignal

from .constants import LAUNCHER_DIR, host, news_en_url, news_url
from .storage import write_json
from .utilties import t


class Fetcher(QObject):
    newsFetched = pyqtSignal(list)
    onlineFetched = pyqtSignal(int, str)

    def __init__(self):
        super().__init__()
        self.lang = "en_us"
        self.in_game = False
        self._stop_event = threading.Event()
        self._news_wake = threading.Event()
        self._online_wake = threading.Event()

    def fetch_news_async(self):
        threading.Thread(
            target=self._run, args=(self._fetch_news_once, self._news_wake, 120), daemon=True
        ).start()

    def fetch_online_async(self):
        threading.Thread(
            target=self._run, args=(self._fetch_online_once, self._online_wake, 10), daemon=True
        ).start()

    def fetch_news_now(self):
        self._news_wake.set()

    def fetch_online_now(self):
        self._online_wake.set()

    def set_lang(self, lang):
        self.lang = lang

    def set_game(self, game):
        was_in_game = self.in_game
        self.in_game = bool(game)
        if was_in_game and not self.in_game:
            self.fetch_news_now()
            self.fetch_online_now()

    def stop(self):
        self._stop_event.set()
        self._news_wake.set()
        self._online_wake.set()

    def _run(self, fetch, wake, interval):
        while not self._stop_event.is_set():
            wake.clear()
            if not self.in_game:
                fetch()
            wake.wait(interval)

    def _fetch_online_once(self):
        lang = self.lang
        try:
            from mcstatus import JavaServer

            status = JavaServer.lookup(host, timeout=5).status()
            players = status.players.online
            ping = f"{int(status.latency)} {t(lang, 'ms_locale')}"
        except Exception as exc:
            print(f"[Fetcher] Fetch online error: {exc}")
            players, ping = -1, t(lang, "online_label_unknown")
        if not self._stop_event.is_set():
            self.onlineFetched.emit(players, ping)

    def _fetch_news_once(self):
        lang = self.lang
        cache = LAUNCHER_DIR / f"news_cache_{lang}.json"
        data = []
        try:
            response = requests.get(news_url if lang == "ru_ru" else news_en_url, timeout=5)
            response.raise_for_status()
            articles = response.json()
            if not isinstance(articles, list):
                raise ValueError("Expected a list of news articles")
            data = [article for article in articles if isinstance(article, dict)]
            write_json(cache, data)
        except (OSError, ValueError, requests.RequestException) as exc:
            print(f"[Fetcher] Failed to fetch or cache news: {exc}")
            if not data:
                try:
                    cached = json.loads(cache.read_text(encoding="utf-8"))
                    if isinstance(cached, list):
                        data = [article for article in cached if isinstance(article, dict)]
                except (OSError, ValueError):
                    pass
        if not self._stop_event.is_set() and lang == self.lang:
            self.newsFetched.emit(data)
