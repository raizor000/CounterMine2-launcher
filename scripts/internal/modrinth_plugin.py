import json
import os
import urllib.parse
import urllib.request
import requests
import threading
import hashlib
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QScrollArea, QGridLayout, QFrame, QLabel, QPushButton
from PyQt6.QtGui import QCursor, QPixmap, QMovie

from scripts.plugin_manager import BasePlugin
from scripts.constants import MC_DIR, VERSION, tabs_style_new, tabs_style, MODRINTH_TAB_INDEX, MODS_CACHE
from scripts.utilties import t, is_mod_installed, SmoothScrollArea

class ModSearchWorker(QObject):
    finished = pyqtSignal(list, bool, bool) 

    def __init__(self, query, index, version, offset=0, append=False):
        super().__init__()
        self.query, self.index, self.version, self.offset, self.append = query, index, version, offset, append
        self._stop = False

    def stop(self): self._stop = True

    def run(self):
        try:
            limit = 51
            facets = f'[["project_type:mod"],["categories:fabric"],["versions:{self.version}"]]'
            url = f"https://api.modrinth.com/v2/search?query={urllib.parse.quote(self.query)}&facets={urllib.parse.quote(facets)}&limit={limit}&offset={self.offset}&index={self.index}"
            
            headers = {'User-Agent': 'CounterMine2-Launcher/5.0'}
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            
            hits = response.json().get('hits', [])
            mods = []  
            for hit in hits:
                if self._stop:
                    return

                mods.append({
                    "name": hit['title'], "slug": hit['slug'], 
                    "icon_url": hit.get('icon_url'),
                    "desc": hit.get('description', '')[:150] + '...' if len(hit.get('description', '')) > 150 else hit.get('description', '')
                })
            if not self._stop: self.finished.emit(mods, self.append, True)
        except Exception as e:
            print(f"ModSearchWorker error: {e}")
            self.finished.emit([], self.append, False)

class ModIconSignals(QObject):
    icon_loaded = pyqtSignal(str, bytes)

class ModIconLoader(QtCore.QRunnable):
    def __init__(self, mod_slug, icon_url):
        super().__init__()
        self.mod_slug = mod_slug
        self.icon_url = icon_url
        self.signals = ModIconSignals()

    def run(self):
        if not self.icon_url:
            self.signals.icon_loaded.emit(self.mod_slug, b"")
            return
        try:
            icon_hash = hashlib.md5(self.icon_url.encode()).hexdigest()
            ext = "png"
            if ".webp" in self.icon_url.lower(): ext = "webp"
            
            cache_dir = MODS_CACHE / "icons"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = cache_dir / f"{icon_hash}.{ext}"

            if cache_path.exists():
                with open(cache_path, "rb") as f:
                    self.signals.icon_loaded.emit(self.mod_slug, f.read())
                return

            headers = {'User-Agent': 'CounterMine2-Launcher/1.0'}
            response = requests.get(self.icon_url, headers=headers, timeout=5)
            response.raise_for_status()
            
            data = response.content
            with open(cache_path, "wb") as f:
                f.write(data)

            self.signals.icon_loaded.emit(self.mod_slug, data)
        except Exception as e:
            print(f"Error loading icon for {self.mod_slug}: {e}")
            self.signals.icon_loaded.emit(self.mod_slug, b"")

class ModrinthPlugin(BasePlugin):
    name = "Modrinth Integration"
    description = "Встроенный поиск и установка модов\nНЕ может работать одновременно с CurseForge зеркалом"
    author = "raizor"
    icon = "assets/pixmaps/modrinth.png"

    refresh_signal = pyqtSignal()

    def on_load(self):
        self.mods_data = []
        self.worker = None
        self.thread = None
        self.mod_icon_labels = {}
        self._active_threads = []
        self.current_offset = 0
        self.has_more = True
        self.limit = 51
        self.retry_timer_obj = None
        self.retry_seconds = 10

        self.refresh_signal.connect(lambda: self.refresh_grid(None))

    def on_ui_ready(self):
        ui = self.app.ui
        self.tab_btn = QPushButton(t(ui.lang, "tabs_mods"))
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
        self.search_edit = QLineEdit()  
        self.search_edit.setPlaceholderText(t(ui.lang, "mod_search"))
        self.search_edit.setStyleSheet("QLineEdit { background-color: #555; color: white; border-radius: 5px; padding: 8px; border: none; }")
        layout.addWidget(self.search_edit)

        self.loading_overlay = QFrame(self.container)
        self.loading_overlay.hide()

        overlay_layout = QVBoxLayout(self.loading_overlay)
        self.spinner_label = QLabel(self.loading_overlay)
        self.spinner_movie = QMovie(ui.resource_path("assets/pixmaps/online_animation.gif"))
        self.spinner_label.setMovie(self.spinner_movie)
        self.spinner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinner_label.setStyleSheet("background: transparent; border: none;")
        overlay_layout.addWidget(self.spinner_label)

        self.error_widget = QFrame(self.container)
        self.error_widget.setObjectName("error_widget")  
        self.error_widget.setStyleSheet("""
            QFrame#error_widget {
                background-color: rgba(60, 20, 20, 230);
                border-radius: 10px;
                border: 2px solid #ff4444;
            }
        """)
        self.error_widget.hide()  

        error_inner_layout = QVBoxLayout(self.error_widget)
        error_inner_layout.setContentsMargins(15, 15, 15, 15)
        error_inner_layout.setSpacing(10)

        self.error_msg = QLabel("Ошибка загрузки Modrinth :(")
        self.error_msg.setStyleSheet("color: white; font-weight: bold; font-size: 14px; background: transparent; border: none;")
        self.error_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_inner_layout.addWidget(self.error_msg)

        self.retry_label = QLabel("Повтор через 10 сек...")
        self.retry_label.setStyleSheet("color: #cccccc; font-size: 12px; background: transparent; border: none;")
        self.retry_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_inner_layout.addWidget(self.retry_label)

        self.retry_btn = QPushButton("Повторить сейчас")
        self.retry_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.retry_btn.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: white;
                border-radius: 5px;
                padding: 6px;
                font-weight: bold;
                border: 1px solid #666;
            }
            QPushButton:hover { background-color: #555; }
        """)
        self.retry_btn.clicked.connect(self.manual_retry)
        error_inner_layout.addWidget(self.retry_btn)

        self.retry_timer_obj = QTimer()
        self.retry_timer_obj.timeout.connect(self.on_retry_tick)

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
                background: #fbac18;
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
        
        self.app.ui.mod_action.connect(self.on_external_action)

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

    def _reposition_fade_effects(self):
        if not self.container.isVisible(): return
        
        search_bottom = self.search_edit.height() + 15
        self.fade_top.setGeometry(0, search_bottom, self.container.width(), 40)
        self.fade_bottom.setGeometry(0, self.container.height() - 40, self.container.width(), 40)
        
        self.loading_overlay.setGeometry(0, 0, self.container.width(), self.container.height())

        ew, eh = 300, 130
        self.error_widget.setGeometry(
            (self.container.width() - ew) // 2,
            search_bottom + (self.container.height() - search_bottom - eh) // 2,
            ew, eh
        )

        self.loading_overlay.raise_()
        self.search_edit.raise_()
        self.fade_top.raise_()
        self.fade_bottom.raise_()
        self.error_widget.raise_()

    def _on_scroll_bottom(self, value):
        if not self.container.isVisible() or self.loading_overlay.isVisible():
            return
        
        vbar = self.scroll.verticalScrollBar()
        if value > vbar.maximum() - 100: 
            if self.has_more:
                self.start_search(append=True)

    def on_settings_changed(self, key, value):
        if key == "new_style":
            if value:
                self.tab_btn.setStyleSheet(tabs_style_new)
            else:
                self.tab_btn.setStyleSheet(tabs_style)
        elif key == "lang":
            self.tab_btn.setText(t(self.app.ui.lang, "tabs_mods"))

    def start_search(self, append=False):
        if not append:
            self.current_offset = 0
            self.has_more = True
            self.error_widget.hide()
            self.retry_timer_obj.stop()
        else:
            self.current_offset += self.limit
        if not self.has_more: return

        try: 
            if self.thread and self.thread.isRunning():
                if not append: 
                    self.worker.stop()
                else:
                    return 
                try:
                    self.worker.finished.disconnect()
                except (TypeError, RuntimeError):
                    pass
                self.thread.quit()
        except RuntimeError:
            self.thread = None
            self.worker = None

        self.loading_overlay.show()
        self.spinner_movie.start()

        query = self.search_edit.text()
        self.worker = ModSearchWorker(query, "relevance" if query else "downloads", self.app.selected_version, self.current_offset, append)
        self.thread = QThread() 
        thread_pair = (self.thread, self.worker)
        self._active_threads.append(thread_pair)

        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_search_done)

        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)

        def _finalize_cleanup(t=self.thread):
            if thread_pair in self._active_threads:
                self._active_threads.remove(thread_pair)
            if self.thread == t:
                self.thread = None

        self.thread.finished.connect(_finalize_cleanup)

        self.thread.start()

    def on_search_done(self, data, append, success):
        self.spinner_movie.stop()
        self.loading_overlay.hide()
        
        if not success:
            if not append:
                self.retry_seconds = 10
                self.retry_label.setText(f"Повтор через {self.retry_seconds} сек...")
                self.error_widget.show()
                self.error_widget.raise_()
                self.retry_timer_obj.start(1000)
            return

        if not data:
            self.has_more = False
            if append: return

        if append:
            self.mods_data.extend(data)
            self.refresh_grid(data, append=True)
        else:
            self.mods_data = data
            self.refresh_grid(self.mods_data, append=False)

    def on_retry_tick(self):
        self.retry_seconds -= 1
        if self.retry_seconds <= 0:
            self.manual_retry()
        else:
            self.retry_label.setText(f"Повтор через {self.retry_seconds} сек...")

    def manual_retry(self):
        self.retry_timer_obj.stop()
        self.error_widget.hide()
        self.start_search(append=False)

    @QtCore.pyqtSlot() 
    @QtCore.pyqtSlot(list)
    @QtCore.pyqtSlot(list, bool)
    def refresh_grid(self, mods_to_add=None, append=False):
        if not append:
            if mods_to_add is None:
                mods_to_add = self.mods_data

            while self.grid.count():
                w = self.grid.takeAt(0).widget()
                if w: w.deleteLater()
            self.mod_icon_labels.clear()
            start_idx = 0 
        else:
            start_idx = len(self.mods_data) - len(mods_to_add)

        card_w = (self.container.width() - 60) // 3
        card_h = 170

        pool = QtCore.QThreadPool.globalInstance()

        for i, mod in enumerate(mods_to_add):
            real_idx = start_idx + i
            is_inst = is_mod_installed(str(MC_DIR), mod["slug"], self.app.selected_version)
            card = QFrame() 
            card.setFixedSize(card_w, card_h)
            card.setStyleSheet("background-color: #555; border-radius: 10px;")
            
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 10, 10, 10)
            card_layout.setSpacing(5)

            header_widget = QWidget()
            header_layout = QHBoxLayout(header_widget)
            header_layout.setContentsMargins(0, 0, 0, 0)
            header_layout.setSpacing(10)

            icon_label = QLabel()
            icon_label.setFixedSize(48, 48)
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setStyleSheet("background: transparent;") 
            header_layout.addWidget(icon_label)
            self.mod_icon_labels[mod["slug"]] = icon_label

            if mod.get("icon_url"):
                icon_worker = ModIconLoader(mod["slug"], mod.get("icon_url"))
                icon_worker.signals.icon_loaded.connect(self._on_icon_loaded)
                pool.start(icon_worker)

            title = QLabel(mod["name"])
            title.setStyleSheet("color: white; font-weight: bold; background: transparent;")
            title.setFont(self.app.ui.font())
            title.setWordWrap(True) 
            title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            header_layout.addWidget(title, 1)

            card_layout.addWidget(header_widget)

            desc = QLabel(mod["desc"])
            desc.setStyleSheet("color: #ddd; font-size: 14px; background: transparent;")
            desc.setWordWrap(True) 
            desc.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            card_layout.addWidget(desc)
            
            card_layout.addStretch()

            btn = QPushButton(t(self.app.lang, "btn_del") if is_inst else t(self.app.lang, "btn_local"))
            btn.setStyleSheet(f"background-color: {'#d32f2f' if is_inst else '#45A049'}; color: white; border-radius: 5px;")
            btn.setFixedHeight(30)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda _, s=mod["slug"], inst=is_inst: self.perform_action(s, "remove" if inst else "install"))
            card_layout.addWidget(btn)

            self.grid.addWidget(card, real_idx // 3, real_idx % 3)
            if real_idx % 5 == 0:
                QtWidgets.QApplication.processEvents()

    def _on_icon_loaded(self, slug, data):
        if slug in self.mod_icon_labels:
            icon_label = self.mod_icon_labels[slug]
            try:
                if not data or icon_label is None:
                    return
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                if not pixmap.isNull():
                    icon_label.setPixmap(pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            except RuntimeError:
                pass

    def on_external_action(self, slug, action):
        if action == "remove":
            self.perform_action(slug, "remove")

    def perform_action(self, slug, action):
        threading.Thread(target=self._run_action, args=(slug, action), daemon=True).start()

    def _run_action(self, slug, action):
        try:
            versioned_mods_dir = MC_DIR / "mods" / self.app.selected_version
            versioned_mods_dir.mkdir(parents=True, exist_ok=True)

            if action == "install": 
                url = f"https://api.modrinth.com/v2/project/{slug}/version?loaders=[\"fabric\"]&game_versions=[\"{self.app.selected_version}\"]"
                
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                v = response.json()[0]
                file_info = v['files'][0]
                
                with requests.get(file_info['url'], stream=True, timeout=10) as r:
                    r.raise_for_status()
                    with open(versioned_mods_dir / file_info['filename'], "wb") as mod_file:
                        for chunk in r.iter_content(chunk_size=8192):
                            mod_file.write(chunk)
            else:
                for f in os.listdir(versioned_mods_dir):
                    if slug in f.lower(): os.remove(versioned_mods_dir / f)
            self.app.ui.installed_mods_dirty = True
            self.app._swap_mods(self.app.selected_version, self.app.selected_version)
            self.refresh_signal.emit()
            QtCore.QMetaObject.invokeMethod(self.app.ui, "refresh_installed_mods_display", Qt.ConnectionType.QueuedConnection)
        except requests.exceptions.RequestException as e:
            print(f"Network error during {'installation' if action == 'install' else 'removal'} of {slug}: {e}")