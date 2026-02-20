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
backend = "https://fx.cc"
backend1 = "https://80nix.cc"
news_url = "https://f6443/news/news.json"
news_url1 = "https://80nix.cc/news/news.json"

default_port = "6443"

external_ip_url = 'https://api.ipify.org?format=json'
LAUNCHER_VERSION = "4.1"
PRACTICE_QUEUE_URL = "http://51:20169/prac"
ACTIVE_PRACTICE_QUEUE_URL = "http://50169/active_prac"


tabs_style = """
    QPushButton { background-color: #555; color: white; border-radius: 5px; border: none; }
    QPushButton:hover { background-color: #666; }
    QPushButton:checked { background-color: #45A049; }
"""
tabs_disabled_style = """
    QPushButton { background-color: #3b3b3b; color: white; border-radius: 5px; border: none; }
    QPushButton:hover { background-color: #666; }
"""


tabs_style_new = """
    QPushButton { background-color: #555; color: white; border-radius: 5px; border: none; }
    QPushButton:hover { background-color: #666; }
    QPushButton:checked { background-color: #fbac18; }
"""
tabs_disabled_style_new = """
    QPushButton { background-color: #b36f00; color: white; border-radius: 5px; border: none; }
    QPushButton:hover { background-color: #b36f00; }
"""

old_btn_style = """
                        QPushButton {
                            background-color: #2a6da0;
                            color: white;
                            border-radius: 8px;
                            font-weight: bold;
                            font-size: 13px;
                        }
                        QPushButton:hover {
                            background-color: #3579b0;
                        }
                        QPushButton:pressed {
                            background-color: #1e5585;
                        }
                    """

new_btn_style = """
                        QPushButton {
                            background-color: #fbac18;
                            color: white;
                            border-radius: 8px;
                            font-weight: bold;
                            font-size: 13px;
                        }
                        QPushButton:hover {
                            background-color: #e69500;
                        }
                        QPushButton:pressed {
                            background-color: #b36f00;
                        }
                    """

old_play_btn_style = """
            QPushButton { background-color: #45A049; color:white; border-radius:10px; }
            QPushButton:hover:!disabled { background-color: #45a800; }
            QPushButton:disabled { background-color:#2e6b35; color:#aaa; }
        """

new_play_btn_style = """
            QPushButton { background-color: #fbac18; color:white; border-radius:10px; }
            QPushButton:hover:!disabled { background-color: #e69500; }
            QPushButton:disabled { background-color:#b36f00; color:#aaa; }
        """

old_switch_style = "#45A049"
new_switch_style = "#fbac18"

old_dropdown_style = "#FF5722"
new_dropdown_style = "#fbac18"
# ну типа отправка логов в дс, первая - дс фасика, вторая - дс практиса
LOGS_WEBHOOK_URL = "https://discord.43388300623ei4z3Z7OG0RGZw4VsxflhglMzqja5ZHy_"
LOGS_WEBHOOK_URL2 = "https://disgWdEa3mDhGq_nCPhE-ZH5uSZdVuRwXS9xycmK"



