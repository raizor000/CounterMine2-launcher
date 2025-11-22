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

VERSION = "1.21.8"
host = "play.cherry.pizza"
backend = "http://f1.delonix.cc"
news_url = "http://f1.delonix.cc:6443/news/news.json"
default_port = "6443"
external_ip_url = 'https://api.ipify.org?format=json'
LAUNCHER_VERSION = "3.0"
SERVER_URL = "http://f1.delonix.cc:6443/upload"
QUEUE_URL = "http://f1.delonix.cc:6443/queue"

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

WEBHOOK_URL = "https://discord.com/api/webhooks/1433575386641596490/U6C30mVWy3_fstaXRpgC3aevEVdLhw1qQT8s1YefNc5UdgXO92w6I3r9oSlYcsGurl5R"
LOGS_WEBHOOK_URL = "https://discord.com/api/webhooks/1433883006233215139/TzDnGiGeJWspLN-AxmekKGWJ2ywZm1kz30fni4z3Z7OG0RGZw4VsxflhglMzqja5ZHy_"

# Для петрушки - Взаимодействие с модераторами. Пока нету функционала
MODERATORS_URL = f"{backend}:{default_port}/moderators"
BANNED_IPS_ADD_URL = f"{backend}:{default_port}/banned_ips/add"
BANNED_IPS_REMOVE_URL = f"{backend}:{default_port}/banned_ips/remove"
MODERATORS_ADD_URL = f"{backend}:{default_port}/moderators/add"
MODERATORS_REMOVE_URL = f"{backend}:{default_port}/moderators/remove"

# Для петрушки - раньше использовалось для сохранения бана по железу. На данный момент не используется
REG_PATH = r"Software\CounterMine2"

# Для петрушки - потом под бекграундами будет подпись где находится данная позиция. Пока функционала нету

# BACKGROUND_LIST = {
#                     "background1.png": "Sandstone - B Plant",
#                     "background2.png": "Sandstone - Fountain",
#                     "background3.png": "Dust II - Upper",
#                     "background4.png": "Dust II - B Plant",
#                     "background5.png": "Mirage - CT Spawn",
#                     "background6.png": "Mirage - A Plant",
#                     "background7.png": "Mirage - Mid and Top-Mid",
#                     "background8.png": "Mirage - Mid and Top-Mid",
#                     "background9.png": "Mirage - Mid and Top-Mid",
#                     "background10.png": "Mirage - Mid and Top-Mid",
#                     "background11.png": "Mirage - Mid and Top-Mid",
#                     "background12.png": "Mirage - Mid and Top-Mid",
#                   }
