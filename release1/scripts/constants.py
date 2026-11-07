import os

APPDATA = os.getenv("APPDATA") or os.path.expanduser("~")
MC_DIR = os.path.join(APPDATA, ".countermine")
LAUNCHER_DIR = os.path.join(APPDATA, ".countermine-launcher")
MODS_DIR = os.path.join(MC_DIR, "mods")
MODS_CACHE = os.path.join(MC_DIR, "mods_cache")
os.makedirs(MODS_DIR, exist_ok=True)
os.makedirs(MODS_CACHE, exist_ok=True)
os.makedirs(MC_DIR, exist_ok=True)
os.makedirs(LAUNCHER_DIR, exist_ok=True)
VERSION = "1.21.8"

news_url = "https://raw.githubusercontent.com/theAndrew2808/CounterMine2-Launcher-Config/refs/heads/main/news.json"
host = "play.cherry.pizza"
backend = "https://cm2news.xyz"
external_ip_url = 'https://api.ipify.org?format=json'
LAUNCHER_VERSION = "1.3"