import threading
import time

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

    def fetch_queue_async(self):
        threading.Thread(target=self._run_queue, daemon=True).start()

    def fetch_ban_async(self):
        threading.Thread(target=self._run_ban, daemon=True).start()

    def fetch_practice_queue_async(self):
        threading.Thread(target=self._run_practice_queue, daemon=True).start()


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
                response = requests.get(f'{get_server1_url()}/banned_ips')
                response.raise_for_status()
                banned_ips = response.json()
                response2 = requests.get(f'{get_server1_url()}/banned_hwids', timeout=5)
                response2.raise_for_status()
                banned_hwids = response2.json()
                os_info = platform.platform()
                processor_info = platform.processor()
                more = platform.node()
                unique_string = os_info + processor_info + more
                software_machine_id = hashlib.sha256(unique_string.encode()).hexdigest()
            except Exception as e:
                print(e)

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
                except Exception as e:
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
                    resp = requests.get(QUEUE_URL1, timeout=2)
                    if resp.status_code == 200:
                        data = resp.json()
                        players = data.get("queue", [])
                        names = [(p["nickname"], p.get("elo", "—")) for p in players]
                    else:
                        names = ["Фураникс не оплатил хост. А нам лень убирать данный блок. Так что мы разместим здесь бананчика вованчика"]
                except Exception as e:
                    print(e)

                    try:
                        resp = requests.get(QUEUE_URL, timeout=2)
                        if resp.status_code == 200:
                            data = resp.json()
                            players = data.get("queue", [])
                            names = [(p["nickname"], p.get("elo", "—")) for p in players]
                        else:
                            names = ["Фураникс не оплатил хост. А нам лень убирать данный блок. Так что мы разместим здесь бананчика вованчика"]
                    except Exception as e:
                        names = ["Ошибка запроса", "-"]
                        print(e)

                self.queueFetched.emit(names)
                time.sleep(15)
            else:
                time.sleep(2)

    def _run_practice_queue(self):
        while True:
            if not self.in_game:
                try:
                    resp1 = requests.get(PRACTICE_QUEUE_URL, timeout=5)
                    resp2 = requests.get(ACTIVE_PRACTICE_QUEUE_URL, timeout=5)

                    searching_clans = []
                    active_practices = {}

                    if resp1.status_code == 200:
                        try:
                            data1 = resp1.json()
                            if isinstance(data1, list):
                                searching_clans = [item for item in data1 if isinstance(item, str)]
                            elif isinstance(data1, dict) and "queue" in data1:
                                searching_clans = [item for item in data1["queue"] if isinstance(item, str)]
                        except:
                            searching_clans = []
                    if resp2.status_code == 200:
                        try:
                            data2 = resp2.json()
                            if isinstance(data2, dict):
                                for match_id, teams in data2.items():
                                    if isinstance(teams, list) and len(teams) == 2:
                                        t1, t2 = teams
                                        if isinstance(t1, str) and isinstance(t2, str):
                                            active_practices[match_id] = [t1.strip(), t2.strip()]
                        except:
                            pass
                    if not searching_clans:
                        searching_clans = []
                    if not active_practices:
                        active_practices = {}
                    self.practiceQueueFetched.emit(searching_clans, active_practices)

                except requests.RequestException as e:
                    print(f"[Practice Fetcher] Network error: {e}")
                    self.practiceQueueFetched.emit([], {})
                except Exception as e:
                    print(f"[Practice Fetcher] Unexpected error: {e}")
                    self.practiceQueueFetched.emit([], {})
            else:
                time.sleep(2)
            time.sleep(15)

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
                    r = requests.get(news_url1, timeout=2)
                    r.raise_for_status()
                    data = r.json()
                    if not isinstance(data, list):
                        raise ValueError("Ожидался список новостей")
                    self.newsFetched.emit(data)
                except Exception as e:
                    print(e)
                    try:
                        r = requests.get(news_url, timeout=2)
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
