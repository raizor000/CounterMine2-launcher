import json
import os
import urllib.parse
import requests
import threading
import hashlib
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QScrollArea, QGridLayout, QFrame, QLabel, QPushButton
from PyQt6.QtGui import QCursor, QPixmap, QMovie

from scripts.plugin_manager import BasePlugin
from scripts.constants import MC_DIR, VERSION, tabs_style_new, tabs_style, MODRINTH_TAB_INDEX, MODS_CACHE
from scripts.utilties import is_mod_installed, SmoothScrollArea

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

class CurseSearchWorker(QObject):
    finished = pyqtSignal(list, bool, bool)

    def __init__(self, query, index, offset=0, append=False):
        super().__init__()
        self.query, self.index, self.offset, self.append = query, index, offset, append
        self._stop = False

    def stop(self): self._stop = True

    def run(self):
        try:
            limit = 33  
            sort_field = 6 if self.query else 2
            url = f"https://mod.mcimirror.top/curseforge/v1/mods/search?gameId=432&classId=6&modLoaderType=4&gameVersion={VERSION}&searchFilter={urllib.parse.quote(self.query)}&index={self.offset}&pageSize={limit}&sortField={sort_field}"
            
            headers = {'Accept': 'application/json'}
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            data = response.json().get('data', [])
            mods = []  
            for item in data:
                if self._stop: return

                mods.append({
                    "name": item['name'], 
                    "slug": item['slug'],
                    "id": item['id'],
                    "icon_url": item.get('logo', {}).get('url') if item.get('logo') else None,
                    "desc": item.get('summary', '')[:150] + '...' if len(item.get('summary', '')) > 150 else item.get('summary', '')
                })
            if not self._stop: self.finished.emit(mods, self.append, True)
        except Exception as e:
            print(f"CurseSearchWorker error: {e}")
            self.finished.emit([], self.append, False)

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

    def on_load(self):
        self.name = t(self.app.lang, "curseforge_plugin_name")
        self.description = t(self.app.lang, "curseforge_plugin_description")
        self.mods_data = []
        self.worker = None
        self.thread = None
        self.mod_icon_labels = {}
        self._active_threads = []
        self.current_offset = 0
        self.has_more = True
        self.limit = 33
        self.retry_timer_obj = None
        self.retry_seconds = 10
        
        self.refresh_signal.connect(lambda: self.refresh_grid(None))

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
        self.search_edit.textChanged.connect(lambda: self.search_timer.start(250))
        self.search_timer.start(50)  
        
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

    def start_search(self, append=False):
        if not append:
            self.current_offset = 0
            self.has_more = True
            self.error_widget.hide()
        else: self.current_offset += self.limit
  
        if self.thread and self.thread.isRunning():
            if not append: self.worker.stop()
            else: return

        self.loading_overlay.show(); self.spinner_movie.start()
        query = self.search_edit.text()
        self.worker = CurseSearchWorker(query, 0, self.current_offset, append)
        self.thread = QThread()
        self._active_threads.append((self.thread, self.worker))
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_search_done)
        self.worker.finished.connect(self.thread.quit)
        self.thread.start()

    def on_search_done(self, data, append, success):
        self.spinner_movie.stop(); self.loading_overlay.hide()
        if not success:  
            if not append: self.error_widget.show()
            return
        if not data: self.has_more = False
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
            is_inst = is_mod_installed(str(MC_DIR), mod["slug"])
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
        threading.Thread(target=self._run_action, args=(slug, mod_id, action), daemon=True).start()

    def _run_action(self, slug, mod_id, action):
        try:
            mods_dir = MC_DIR / "mods"
            if action == "install":  
                url = f"https://mod.mcimirror.top/curseforge/v1/mods/{mod_id}/files?gameVersion={VERSION}&modLoaderType=4"
                resp = requests.get(url, timeout=10).json()
                
                if 'data' not in resp or not resp['data']:
                    print(f"Action error: 'data' key missing in mirror response: {resp}")
                    return

                target_file = resp['data'][0]
                d_url = target_file.get('downloadUrl')
                f_name = target_file.get('fileName')
                f_id = target_file.get('id')  
                
                if not d_url and f_id and f_name:
                    folder1 = f_id // 1000
                    folder2 = f_id % 1000
                    d_url = f"https://edge.forgecdn.net/files/{folder1}/{folder2}/{urllib.parse.quote(f_name)}"
                    print(f"Download URL missing, using fallback: {d_url}")

                if not d_url:
                    print(f"Action error: 'downloadUrl' missing or empty for mod_id {mod_id} in mirror response: {resp}")
                    return

                r = requests.get(d_url, stream=True, timeout=30)
                r.raise_for_status()
                with open(mods_dir / f_name, "wb") as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
            else:
                for f in os.listdir(mods_dir):
                    if slug in f.lower(): os.remove(mods_dir / f)
            
            self.app.ui.installed_mods_dirty = True
            self.refresh_signal.emit()
            QtCore.QMetaObject.invokeMethod(self.app.ui, "refresh_installed_mods_display", Qt.ConnectionType.QueuedConnection)
        except Exception as e: print(f"Action error: {e}")