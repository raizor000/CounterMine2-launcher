import json
import os
import urllib.parse
import requests
import threading
import hashlib
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QScrollArea, QGridLayout, QFrame, QLabel, QPushButton
from PyQt6.QtGui import QCursor, QPixmap, QMovie

from scripts.plugin_manager import BasePlugin
from scripts.constants import MC_DIR, VERSION, tabs_style_new, tabs_style, MODRINTH_TAB_INDEX, MODS_CACHE
from scripts.game_files import catalog_mod_path, install_catalog_mod, remove_catalog_mod
from scripts.utilties import SmoothScrollArea

translations = {
    "ru_ru": {
        "curseforge_plugin_name": "CurseForge Integration (Зеркало)",
        "curseforge_plugin_description": "Поиск и установка модов с ЗЕРКАЛА CurseForge\nНЕ может работать одновременно с Modrinth",
        "curseforge_readonly_placeholder": "ОТОБРАЖЕНИЕ СТАТУСА МОДА ДОСТУПНО ТОЛЬКО ВО ВКЛАДКЕ УСТАНОВЛЕННЫХ МОДОВ",
        "curseforge_error_message": "Ошибка CurseForge API",
        "curseforge_retry_button": "Повторить"
    },
    "en_us": {
        "curseforge_plugin_name": "CurseForge Integration (Mirror)",
        "curseforge_plugin_description": "Search and install mods from the CurseForge MIRROR\nCANNOT work simultaneously with Modrinth",
        "curseforge_readonly_placeholder": "MOD STATUS DISPLAY IS ONLY AVAILABLE IN THE INSTALLED MODS TAB",
        "curseforge_error_message": "CurseForge API Error",
        "curseforge_retry_button": "Retry"
    }
}

def t(lang, key):
    if key not in translations[lang]:
        return "???"
    return translations[lang].get(key, key)

class CurseSearchWorker:

    def __init__(self, query, index, version, offset=0, append=False):
        self.query, self.index, self.version, self.offset, self.append = query, index, version, offset, append

    def run(self):
        try:
            limit = 33  
            sort_field = 6 if self.query else 2
            url = f"https://mod.mcimirror.top/curseforge/v1/mods/search?gameId=432&classId=6&modLoaderType=4&gameVersion={self.version}&searchFilter={urllib.parse.quote(self.query)}&index={self.offset}&pageSize={limit}&sortField={sort_field}"
            
            headers = {'Accept': 'application/json'}
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            data = response.json().get('data', [])
            mods = []  
            for item in data:

                mods.append({
                    "name": item['name'], 
                    "slug": item['slug'],
                    "id": item['id'],
                    "icon_url": item.get('logo', {}).get('url') if item.get('logo') else None,
                    "desc": item.get('summary', '')[:150] + '...' if len(item.get('summary', '')) > 150 else item.get('summary', '')
                })
            return mods, True
        except Exception as e:
            print(f"CurseSearchWorker error: {e}")
            return [], False

class CurseIconSignals(QObject):
    icon_loaded = pyqtSignal(str, bytes)

class CurseIconLoader(QtCore.QRunnable):
    def __init__(self, mod_slug, icon_url):
        super().__init__()
        self.mod_slug = mod_slug
        self.icon_url = icon_url
        self.signals = CurseIconSignals()

    def run(self):
        if not self.icon_url:
            self.signals.icon_loaded.emit(self.mod_slug, b"")
            return
        try:
            icon_hash = hashlib.md5(self.icon_url.encode()).hexdigest()
            cache_dir = MODS_CACHE / "icons"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = cache_dir / f"{icon_hash}.png"

            if cache_path.exists():
                with open(cache_path, "rb") as f:
                    self.signals.icon_loaded.emit(self.mod_slug, f.read())
                return

            response = requests.get(self.icon_url, timeout=5)
            response.raise_for_status()
            data = response.content
            with open(cache_path, "wb") as f: f.write(data)
            self.signals.icon_loaded.emit(self.mod_slug, data)
        except Exception:
            self.signals.icon_loaded.emit(self.mod_slug, b"")

class CurseForgePlugin(BasePlugin):
    name = "CurseForge Integration (Зеркало)"
    description = "Поиск и установка модов с ЗЕРКАЛА CurseForge. НЕ может работать одновременно с Modrinth"
    author = "raizor"
    icon = "assets/pixmaps/curseforge.png"
    version = "1.0.0"

    refresh_signal = pyqtSignal()
    search_result = pyqtSignal(int, list, bool, bool)

    def on_load(self):
        self.name = t(self.app.lang, "curseforge_plugin_name")
        self.description = t(self.app.lang, "curseforge_plugin_description")
        self.mods_data = []
        self._search_id = 0
        self._searching = False
        self._searched_version = None
        self.mod_icon_labels = {}
        self.current_offset = 0
        self.has_more = True
        self.limit = 33
        self.retry_timer_obj = None
        self.retry_seconds = 10
        
        self.refresh_signal.connect(self.refresh_grid)
        self.search_result.connect(self.on_search_done, Qt.ConnectionType.QueuedConnection)

    def on_language_change(self, lang):
        self.name = t(lang, "curseforge_plugin_name")
        self.description = t(lang, "curseforge_plugin_description")
        self.update_ui_texts(lang)

    def update_ui_texts(self, lang):
        if hasattr(self, 'tab_btn'):
            self.tab_btn.setText(t(lang, "tabs_mods"))
        if hasattr(self, 'search'):
            self.search.setPlaceholderText(t(lang, "curseforge_readonly_placeholder"))
        if hasattr(self, 'search_edit'):
            self.search_edit.setPlaceholderText(t(lang, "curse_search"))
        if hasattr(self, 'error_msg'):
            self.error_msg.setText(t(lang, "curseforge_error_message"))
        if hasattr(self, 'retry_btn'):
            self.retry_btn.setText(t(lang, "curseforge_retry_button"))

    def on_ui_ready(self):
        ui = self.app.ui
        self.tab_btn = QPushButton()
        self.tab_btn.setFixedSize(100, 30)
        self.tab_btn.setStyleSheet(tabs_style_new)
        self.tab_btn.setCheckable(True)
        self.tab_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.tab_btn.clicked.connect(lambda: ui._switch_tab(MODRINTH_TAB_INDEX))

        ui.tabs_layout.insertWidget(1, self.tab_btn)
        self.app.ui.modrinth_plugin_tab_btn = self.tab_btn
        self.app.ui.settings_changed.connect(self.on_settings_changed)

        self.container = QFrame(ui)
        self.container.setGeometry(0, 40, ui.width(), ui.height() - 40)
        self.container.setStyleSheet("background: transparent; border: none;")
        self.container.setVisible(False)
        self.app.ui.modrinth_container = self.container

        layout = QVBoxLayout(self.container)

        self.search = QLineEdit()
        self.search.setStyleSheet("QLineEdit { background-color: #555; color: white; border-radius: 5px; padding: 8px; border: none; font-size: 14px;text-align: center; }")
        self.search.setReadOnly(True)
        self.search.setCursor(QCursor(Qt.CursorShape.ForbiddenCursor))
        layout.addWidget(self.search)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(t(ui.lang, "curse_search"))
        self.search_edit.setStyleSheet("QLineEdit { background-color: #555; color: white; border-radius: 5px; padding: 8px; border: none; }")
        layout.addWidget(self.search_edit)

        self.loading_overlay = QFrame(self.container)
        self.loading_overlay.setStyleSheet("background-color: rgba(0, 0, 0, 170); border-radius: 5px;")
        self.loading_overlay.hide()
        overlay_layout = QVBoxLayout(self.loading_overlay)  
        self.spinner_label = QLabel(self.loading_overlay)
        self.spinner_movie = QMovie(ui.resource_path("assets/pixmaps/online_animation.gif"))
        self.spinner_label.setMovie(self.spinner_movie)
        self.spinner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overlay_layout.addWidget(self.spinner_label)

        self.error_widget = QFrame(self.container)
        self.error_widget.setObjectName("error_widget")
        self.error_widget.setStyleSheet("QFrame#error_widget { background-color: rgba(60, 20, 20, 230); border-radius: 10px; border: 2px solid #ff4444; }")
        self.error_widget.hide()  
        error_inner_layout = QVBoxLayout(self.error_widget)
        self.error_msg = QLabel()
        self.error_msg.setStyleSheet("color: white; font-weight: bold; background: transparent;")
        error_inner_layout.addWidget(self.error_msg)
        self.retry_btn = QPushButton()
        self.retry_btn.clicked.connect(self.manual_retry)
        error_inner_layout.addWidget(self.retry_btn)

        self.scroll = SmoothScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QWidget#qt_scrollarea_viewport { background: transparent; }
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 35);
                min-height: 40px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255, 255, 255, 60);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(self.content_widget)
        self.scroll.setWidget(self.content_widget)
        layout.addWidget(self.scroll)
        self.scroll.verticalScrollBar().valueChanged.connect(self._on_scroll_bottom)

        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.start_search)
        self.tab_btn.clicked.connect(self._load_catalog_if_needed)
        self.app.catalog_version_changed.connect(self._on_version_changed)
        self.search_edit.textChanged.connect(lambda: self.search_timer.start(250))
        
        self.fade_top = QFrame(self.container)
        self.fade_top.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.fade_top.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                stop:0 rgba(40, 40, 40, 255), 
                stop:1 rgba(40, 40, 40, 0));
            border: none;
        """)

        self.fade_bottom = QFrame(self.container)
        self.fade_bottom.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.fade_bottom.setStyleSheet("""
            background: qlineargradient(x1:0, y1:1, x2:0, y2:0, 
                stop:0 rgba(40, 40, 40, 255), 
                stop:1 rgba(40, 40, 40, 0));
            border: none;
        """)

        self.fade_sync_timer = QTimer()
        self.fade_sync_timer.timeout.connect(self._reposition_fade_effects)
        self.fade_sync_timer.start(50)

        self.update_ui_texts(self.app.lang)
  
    def _reposition_fade_effects(self):
        if not self.container.isVisible(): return
        
        search_bottom = self.search_edit.height() + self.search_edit.y()
        self.fade_top.setGeometry(0, search_bottom, self.container.width(), 40)
        self.fade_bottom.setGeometry(0, self.container.height() - 40, self.container.width(), 40)
        
        self.loading_overlay.setGeometry(0, 0, self.container.width(), self.container.height())

        self.loading_overlay.raise_()
        self.search_edit.raise_()
        self.fade_top.raise_()
        self.fade_bottom.raise_()

    def _on_scroll_bottom(self, value):
        if not self.container.isVisible() or self.loading_overlay.isVisible(): return  
        if value > self.scroll.verticalScrollBar().maximum() - 100 and self.has_more:
            self.start_search(append=True)

    def on_settings_changed(self, key, value):
        if key == "new_style": self.tab_btn.setStyleSheet(tabs_style_new if value else tabs_style)
        # Language change is handled by on_language_change

    def _load_catalog_if_needed(self):
        if self._searched_version != self.app.selected_version:
            self.start_search()

    def _on_version_changed(self):
        self._searched_version = None
        self._search_id += 1
        self._searching = False
        self.mods_data = []
        self.spinner_movie.stop()
        self.loading_overlay.hide()
        self.error_widget.hide()
        self.refresh_grid()
        if self.container.isVisible():
            self.start_search()

    def start_search(self, append=False):
        if append and (self._searching or not self.has_more):
            return
        if not append:
            self.current_offset = 0
            self.has_more = True
            self.error_widget.hide()
        self._search_id += 1
        search_id = self._search_id
        self._searching = True
        self._searched_version = self.app.selected_version
        self.loading_overlay.show()
        self.spinner_movie.start()
        query = self.search_edit.text()
        offset = self.current_offset + self.limit if append else 0
        worker = CurseSearchWorker(query, 0, self._searched_version, offset, append)

        def run():
            data, success = worker.run()
            self.search_result.emit(search_id, data, append, success)

        threading.Thread(target=run, daemon=True).start()

    def on_search_done(self, search_id, data, append, success):
        if search_id != self._search_id:
            return
        self._searching = False
        self.spinner_movie.stop(); self.loading_overlay.hide()
        if not success:  
            if not append: self.error_widget.show()
            return
        self.has_more = len(data) == self.limit
        if append:
            self.current_offset += self.limit
            if not data:
                return
        if not append: self.mods_data = data
        else: self.mods_data.extend(data)
        self.refresh_grid(data if append else self.mods_data, append=append)

    def manual_retry(self):  
        self.error_widget.hide(); self.start_search()

    @QtCore.pyqtSlot()
    @QtCore.pyqtSlot(list)
    @QtCore.pyqtSlot(list, bool)
    def refresh_grid(self, mods_to_add=None, append=False):
        if not append:
            if mods_to_add is None or len(mods_to_add) == 0:
                mods_to_add = self.mods_data

            while self.grid.count():
                w = self.grid.takeAt(0).widget()
                if w: w.deleteLater()
            self.mod_icon_labels.clear()
            start_idx = 0  
        else: start_idx = len(self.mods_data) - len(mods_to_add)

        card_w, card_h = (self.container.width() - 60) // 3, 170
        pool = QtCore.QThreadPool.globalInstance()

        for i, mod in enumerate(mods_to_add):
            idx = start_idx + i
            is_inst = catalog_mod_path(
                MC_DIR / "mods" / self.app.selected_version, f"curseforge:{mod['id']}", mod["slug"]
            ) is not None
            card = QFrame()  
            card.setFixedSize(card_w, card_h)
            card.setStyleSheet("background-color: #555; border-radius: 10px;")
            lay = QVBoxLayout(card)
            
            header = QWidget()
            h_lay = QHBoxLayout(header)
            icon_label = QLabel()
            icon_label.setFixedSize(48, 48)
            h_lay.addWidget(icon_label)
            self.mod_icon_labels[mod["slug"]] = icon_label
  
            if mod.get("icon_url"):
                loader = CurseIconLoader(mod["slug"], mod["icon_url"])
                loader.signals.icon_loaded.connect(self._on_icon_loaded)
                pool.start(loader)

            title = QLabel(mod["name"])
            title.setStyleSheet("color: white; font-weight: bold;")
            title.setWordWrap(True)  
            h_lay.addWidget(title, 1)
            lay.addWidget(header)

            desc = QLabel(mod["desc"])
            desc.setStyleSheet("color: #ddd; font-size: 14px;")
            desc.setWordWrap(True)
            lay.addWidget(desc)
            lay.addStretch()  

            btn = QPushButton(t(self.app.lang, "btn_del") if is_inst else t(self.app.lang, "btn_local"))
            btn.setStyleSheet(f"background-color: {'#d32f2f' if is_inst else '#45A049'}; color: white; border-radius: 5px;")
            btn.setFixedHeight(30)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda _, s=mod["slug"], inst=is_inst, mid=mod["id"]: self.perform_action(s, mid, "remove" if inst else "install"))
            lay.addWidget(btn)
            self.grid.addWidget(card, idx // 3, idx % 3)
  
    def _on_icon_loaded(self, slug, data):
        if slug in self.mod_icon_labels and data:
            pix = QPixmap()
            pix.loadFromData(data)
            if not pix.isNull():
                self.mod_icon_labels[slug].setPixmap(pix.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def perform_action(self, slug, mod_id, action):
        self.app.start_mod_task(self._run_action, slug, mod_id, action)

    def _run_action(self, slug, mod_id, action, version):
        directory = MC_DIR / "mods" / version
        key = f"curseforge:{mod_id}"
        if action == "remove":
            remove_catalog_mod(directory, key, slug)
            return
        response = requests.get(
            f"https://mod.mcimirror.top/curseforge/v1/mods/{int(mod_id)}/files",
            params={"gameVersion": version, "modLoaderType": 4},
            timeout=10,
        )
        response.raise_for_status()
        files = response.json().get("data")
        if not files:
            raise ValueError(f"No compatible Fabric file for {slug} ({version})")
        file = files[0]
        filename = file["fileName"]
        url = file.get("downloadUrl")
        if not url:
            folder, number = divmod(int(file["id"]), 1000)
            url = f"https://edge.forgecdn.net/files/{folder}/{number}/{urllib.parse.quote(filename, safe='')}"
        checksum = next(
            (("sha1", item["value"]) for item in file.get("hashes", []) if item["algo"] == 1),
            None,
        )
        install_catalog_mod(directory, key, filename, url, checksum)
