import os
from pathlib import Path

APPDATA = os.getenv("APPDATA") or os.path.expanduser("~")
MC_DIR = Path(APPDATA) / ".countermine"
LAUNCHER_DIR = Path(APPDATA) / ".countermine-launcher"
MODS_DIR = MC_DIR / "mods"
RP_DIR = MC_DIR / "resourcepacks"
MODS_CACHE = MC_DIR / "mods_cache"
LOGS_DIR = MC_DIR / "logs"

MC_DIR.mkdir(parents=True, exist_ok=True)
LAUNCHER_DIR.mkdir(parents=True, exist_ok=True)
MODS_DIR.mkdir(parents=True, exist_ok=True)
MODS_CACHE.mkdir(parents=True, exist_ok=True)
RP_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

VERSION = "1.21.11"
host = "play.cherry.pizza"
backend = ""
backend1 = ""
news_url = "n"
news_url1 = ""

default_port = "6443"
default_port1 = "4017"

external_ip_url = 'https://api.ipify.org?format=json'
LAUNCHER_VERSION = "4.0"
QUEUE_URL = ""
QUEUE_URL1 = ""
PRACTICE_QUEUE_URL = ""
ACTIVE_PRACTICE_QUEUE_URL = ""



tabs_style = """
    QPushButton { background-color: #555; color: white; border-radius: 5px; border: none; }
    QPushButton:hover { background-color: #666; }
    QPushButton:checked { background-color: #45A049; }
"""
tabs_disabled_style = """
    QPushButton { background-color: #3b3b3b; color: white; border-radius: 5px; border: none; }
    QPushButton:hover { background-color: #666; }
"""

# Для петрушки - потом будет авторизация через дс для проверки на доступ к модераторским фичам. Функционала пока нету
DISCORD_CLIENT_ID = "1418604142422917330"
DISCORD_CLIENT_SECRET = "2rF1Tcf6CRr9pBwB5pwZ4SEJIPd8KvOc"
DISCORD_REDIRECT_URI = "https://example.com/callback"
DISCORD_AUTH_URL = f"https://discord.com/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&response_type=code&redirect_uri={DISCORD_REDIRECT_URI}&scope=identify"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"
discord_test = "https://discord.com/oauth2/authorize?client_id=1418604142422917330&response_type=code&redirect_uri=https%3A%2F%2Fexample.com%2Fcallback&scope=identify"


# ну типа отправка логов в дс, первая - дс фасика, вторая - дс практиса
WEBHOOK_URL = ""
LOGS_WEBHOOK_URL = ""

WEBHOOK_URL2 = ""
LOGS_WEBHOOK_URL2 = ""



# Для петрушки - Взаимодействие с модераторами. Пока нету функционала | Высокий приоритет!!!
MODERATORS_URL = f"{backend}:{default_port}/moderators"
BANNED_IPS_ADD_URL = f"{backend}:{default_port}/banned_ips/add"
BANNED_IPS_REMOVE_URL = f"{backend}:{default_port}/banned_ips/remove"
MODERATORS_ADD_URL = f"{backend}:{default_port}/moderators/add"
MODERATORS_REMOVE_URL = f"{backend}:{default_port}/moderators/remove"


