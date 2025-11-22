from PyQt5.QtCore import QObject
from mcstatus import JavaServer

from .utilties import *


class Fetcher(QObject):
    newsFetched = pyqtSignal(list)
    onlineFetched = pyqtSignal(str, str)
    queueFetched = pyqtSignal(list)
    banFetched = pyqtSignal(bool, list, str)

    def __init__(self):
        super().__init__()
        self.lang = "en_us"
        self.in_game = False

    def fetch_news_async(self):
        threading.Thread(target=self._run_news, daemon=True).start()

    def fetch_online_async(self):
        threading.Thread(target=self._run_online, daemon=True).start()

    def fetch_queue_async(self):
        threading.Thread(target=self._run_queue, daemon=True).start()

    def fetch_ban_async(self):
        threading.Thread(target=self._run_ban, daemon=True).start()

    def set_lang(self, lang):
        self.lang = lang

    def set_game(self, game):
        self.in_game = bool(game)

    def _run_ban(self):
        while True:
            try:
                response = requests.get(external_ip_url)
                response.raise_for_status()
                ip_data = response.json()
                ip = ip_data['ip']
                response = requests.get(f'{get_server_url()}/banned_ips')
                response.raise_for_status()
                banned_ips = response.json()
                response2 = requests.get(f'{get_server_url()}/banned_hwids', timeout=5)
                response2.raise_for_status()
                banned_hwids = response2.json()
                os_info = platform.platform()
                processor_info = platform.processor()
                more = platform.node()
                unique_string = os_info + processor_info + more
                software_machine_id = hashlib.sha256(unique_string.encode()).hexdigest()
            except requests.RequestException as e:
                ip = "0.0.0.0"
                banned_ips = []
                banned_hwids = []
                software_machine_id = ""
                print(e)

            is_banned_ip = str(ip).strip() in list(banned_ips)
            is_banned_hwid = str(software_machine_id) in list(banned_hwids)
            is_banned = is_banned_ip or is_banned_hwid
            self.banFetched.emit(is_banned, list(banned_hwids), str(software_machine_id))
            time.sleep(120)

    def _run_queue(self):
        while True:
            if not self.in_game:
                try:
                    resp = requests.get(QUEUE_URL, timeout=3)
                    if resp.status_code == 200:
                        data = resp.json()
                        players = data.get("queue", [])
                        names = [(p["nickname"], p.get("elo", "—")) for p in players]
                    else:
                        names = ["Не удалось получить очередь"]
                except Exception as e:
                    names = ["Ошибка запроса", "-"]
                    print(e)

                self.queueFetched.emit(names)
                time.sleep(15)
            else:
                time.sleep(2)

    def _run_online(self):
        while True:
            if not self.in_game:
                try:
                    server = JavaServer.lookup(host, timeout=3)
                    status = server.status()
                    ping_ms = status.latency
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
        while True:
            if not self.in_game:
                try:
                    r = requests.get(news_url, timeout=6)
                    r.raise_for_status()
                    data = r.json()
                    if not isinstance(data, list):
                        raise ValueError("Ожидался список новостей")
                    self.newsFetched.emit(data)
                except Exception as e:
                    self.newsFetched.emit([])
                    print(f"Fetch news error: {e}")
                time.sleep(120)
            else:
                time.sleep(2)
