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

# нода n2 - основная. Ф1 пока что запаска
VERSION = "1.21.11"
host = "play.cherry.pizza"
backend = "https://cm2news.xyz"
backend1 = "https://cm2news.xyz"
news_url = "https://cm2news.xyz/news/news.json"
news_url1 = "https://cm2news.xyz/news/news.json"


external_ip_url = 'https://api.ipify.org?format=json'
LAUNCHER_VERSION = "3.2"
SERVER_URL = "https://cm2news.xyz/upload"
QUEUE_URL = "https://cm2ranked.xyz/queue"
SERVER_URL1 = "https://cm2news.xyz/upload"
QUEUE_URL1 = "https://cm2ranked.xyz/queue"
PRACTICE_QUEUE_URL = "https://cm2ranked.xyz/prac"
ACTIVE_PRACTICE_QUEUE_URL = "https://cm2ranked.xyz/active_prac"



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
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = "https://example.com/callback"
DISCORD_AUTH_URL = f"https://discord.com/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&response_type=code&redirect_uri={DISCORD_REDIRECT_URI}&scope=identify"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"
discord_test = "https://discord.com/oauth2/authorize?client_id=1418604142422917330&response_type=code&redirect_uri=https%3A%2F%2Fexample.com%2Fcallback&scope=identify"


# ну типа отправка логов в дс, первая - дс фасика, вторая - дс практиса
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
LOGS_WEBHOOK_URL = os.environ.get("LOGS_WEBHOOK_URL", "")

WEBHOOK_URL2 = os.environ.get("WEBHOOK_URL2", "")
LOGS_WEBHOOK_URL2 = os.environ.get("LOGS_WEBHOOK_URL2", "")



# Для петрушки - Взаимодействие с модераторами. Пока нету функционала | Высокий приоритет!!!
MODERATORS_URL = f"{backend}/moderators"
BANNED_IPS_ADD_URL = f"{backend}/banned_ips/add"
BANNED_IPS_REMOVE_URL = f"{backend}/banned_ips/remove"
MODERATORS_ADD_URL = f"{backend}/moderators/add"
MODERATORS_REMOVE_URL = f"{backend}/moderators/remove"

# Для петрушки - раньше использовалось для сохранения бана по железу. На данный момент не используется
# REG_PATH = r"Software\CounterMine2"

# крч всё фигня с апи черепицы @TODO 3.3 надо
# TOKEN_URL = "https://auth.cherry.pizza/realms/cherrypizza/protocol/openid-connect/token"
# CLIENT_ID = "frontend"
# REDIRECT_URI = "http://localhost:8080"
# GRAPHQL_URL = "https://cherry.pizza/api/graphql"
# AUTH_URL = "https://auth.cherry.pizza/realms/cherrypizza/protocol/openid-connect/auth?client_id=frontend&redirect_uri=http://localhost:8080&response_type=code&scope=openid"

# Для петрушки - потом под бекграундами будет подпись где находится данная позиция. Пока функционала нету
# По поводу функционала, НЕ планируется в связи с большим количеством ассетов (больше 170 штук). Возможно позже, но не сейчас
# BACKGROUND_LIST = {
#                     "background1.png": "Sandstone - B Plant",
#                     "background2.png": "Sandstone - Fountain",
#                     "background3.png": "Dust II - Upper",
#                     "background4.png": "Dust II - B Plant",
#                     "background5.png": "Mirage - CT Spawn",
#                     "background6.png": "Mirage - A Plant",
#                     "background7.png": "Mirage - Mid and Top-Mid",
#                     "background8.png": "Mirage - Mid and Top-Mid", # Тут я забил на это дело, еще когда было всего 13 обоев в паке
#                     "background9.png": "Mirage - Mid and Top-Mid",
#                     "background10.png": "Mirage - Mid and Top-Mid",
#                     "background11.png": "Mirage - Mid and Top-Mid",
#                     "background12.png": "Mirage - Mid and Top-Mid",
#                   }


XRAY_BAD_BLOCKS = {
    "stone", "deepslate", "netherrack",
    "end_stone", "dirt", "andesite",
    "granite", "diorite"
}

XRAY_OK_WORDS = {
    "glass", "leaves", "water", "lava",
    "plant", "grass", "fern", "flower",
    "torch", "bars", "door", "pane"
}


