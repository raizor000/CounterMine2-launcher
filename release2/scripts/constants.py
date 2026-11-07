import os
from pathlib import Path

APPDATA = os.getenv("APPDATA") or os.path.expanduser("~")
MC_DIR = Path(APPDATA) / ".countermine"
LAUNCHER_DIR = Path(APPDATA) / ".countermine-launcher"
MODS_DIR = MC_DIR / "mods"
MODS_CACHE = MC_DIR / "mods_cache"

MC_DIR.mkdir(parents=True, exist_ok=True)
LAUNCHER_DIR.mkdir(parents=True, exist_ok=True)
MODS_DIR.mkdir(parents=True, exist_ok=True)
MODS_CACHE.mkdir(parents=True, exist_ok=True)

VERSION = "1.21.8"
host = "play.cherry.pizza"
backend = "https://cm2news.xyz"
news_url = "https://cm2news.xyz/news/news.json"
external_ip_url = 'https://api.ipify.org?format=json'
LAUNCHER_VERSION = "2.0"

tabs_style = """
    QPushButton { background-color: #555; color: white; border-radius: 5px; border: none; }
    QPushButton:hover { background-color: #666; }
    QPushButton:checked { background-color: #45A049; }
"""

tabs_disabled_style = """
    QPushButton { background-color: #3b3b3b; color: white; border-radius: 5px; border: none; }
    QPushButton:hover { background-color: #666; }
"""

DISCORD_CLIENT_ID = "1418604142422917330"
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = "https://example.com/callback"
DISCORD_AUTH_URL = f"https://discord.com/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&response_type=code&redirect_uri={DISCORD_REDIRECT_URI}&scope=identify"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"
discord_test = "https://discord.com/oauth2/authorize?client_id=1418604142422917330&response_type=code&redirect_uri=https%3A%2F%2Fexample.com%2Fcallback&scope=identify"

MODERATORS_URL = f"{backend}/moderators"
BANNED_IPS_ADD_URL = f"{backend}/banned_ips/add"
BANNED_IPS_REMOVE_URL = f"{backend}/banned_ips/remove"
MODERATORS_ADD_URL = f"{backend}/moderators/add"
MODERATORS_REMOVE_URL = f"{backend}/moderators/remove"