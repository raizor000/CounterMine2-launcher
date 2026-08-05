import hashlib
import json
import sys
import threading
import time
import urllib.parse
import urllib.request
import zipfile


from PyQt6 import QtWidgets, QtCore
from PyQt6.QtCore import QSize, QUrl, QPoint, QObject, QThread, pyqtSlot, QSizeF
from PyQt6.QtGui import QDesktopServices, QPixmap, QFont, QIcon, QMovie, QFontDatabase, QPalette
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import QPushButton, QStackedLayout, QGridLayout, QLabel, \
    QTextBrowser, QSizePolicy, QGraphicsView, QHBoxLayout, \
    QGraphicsScene, QApplication
from .constants import MODRINTH_TAB_INDEX
from .constants import MODRINTH_TAB_INDEX, PLUGINS_ICON_CACHE
from .utilties import *

class MarketIconSignals(QObject):
    loaded = pyqtSignal(str, bytes)

class MarketIconLoader(QtCore.QRunnable):
    def __init__(self, plugin_id, url):
        super().__init__()
        self.plugin_id = plugin_id
        self.url = url
        self.signals = MarketIconSignals()

    def run(self):
        if not self.url: return  
        try:
            url_hash = hashlib.md5(self.url.encode()).hexdigest()
            ext = "png"
            if ".webp" in self.url.lower(): ext = "webp"
            cache_path = PLUGINS_ICON_CACHE / f"{url_hash}.{ext}"

            if cache_path.exists():
                with open(cache_path, "rb") as f:
                    self.signals.loaded.emit(self.plugin_id, f.read())
                return

            headers = {'User-Agent': 'CounterMine2-Launcher/5.0'}
            response = requests.get(self.url, headers=headers, timeout=5)
            if response.status_code == 200:
                self.signals.loaded.emit(self.plugin_id, response.content)  
                data = response.content
                with open(cache_path, "wb") as f:
                    f.write(data)
                self.signals.loaded.emit(self.plugin_id, data)
            else:
                print(f"Failed to load icon for {self.plugin_id}: {response.status_code}")
        except Exception as e:
            print(f"Error loading icon for {self.plugin_id}: {e}")


class LauncherUI(QWidget):
    play_clicked = pyqtSignal()
    reinstall_client = pyqtSignal()
    mod_action = pyqtSignal(str, str)
    reset_settings = pyqtSignal()
    shader_action = pyqtSignal(str, str)
    resourcepack_action = pyqtSignal(str, str)
    settings_changed = pyqtSignal(str, object)
    auth_login_clicked = pyqtSignal()
    auth_logout_clicked = pyqtSignal()
    open_directory_clicked = pyqtSignal()
    quitSignal = pyqtSignal()

    def __init__(self, version, ip, lang, parent=None):
        super().__init__(parent)

        self.status = None
        QFontDatabase.addApplicationFont(str(self.resource_path("assets/fonts/PressStart2P-Regular.ttf")))
        QFontDatabase.addApplicationFont(str(self.resource_path("assets/fonts/PIXY.ttf")))

        self.balance_frame = None
        self.top = None
        self.prac_expanded = None
        self.faceit_expanded = None
        self.pix = None
        self.news_data = []
        self.launcher = parent
        self.version = version
        self.ip = ip
        self.lang = lang
        self.shaders_data = []
        self.resourcepacks_data = []
        self.shader_buttons = {}
        self.resourcepack_buttons = {}
        self.installed_mods_initialized = False
        self.installed_mods_dirty = True
        self.information_container = None
        self.mods_data = []
        self.moresettings_container = None
        self.plugins_manager_container = None
        self.modrinth_container = None 
        self.plugin_market_view = False
        self.modrinth_plugin_tab_btn = None 
        self.market_icon_labels = {}
        self.waitlist = None
        self.bg3d = None
        self._current_tab_index = 0
        self._settings_blur_effect = None
        self._current_animation = None
        self._build_ui()

        self.installEventFilter(self)


    def resource_path(self, relative_path):
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)


    def _set_static_background(self, ww, wh):
        self.background_label = QLabel(self)
        self.background_label.setGeometry(0, 0, ww, wh)
        self.background_label.setScaledContents(True)

        pixmap = QPixmap(self.resource_path("assets/background/background.jpg"))
        if not pixmap.isNull():
            self.background_label.setPixmap(
                pixmap.scaled(
                    ww,
                    wh,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self.background_label.lower()

    def _build_ui(self):
        ww = 1024
        wh = 580
        self.setFixedSize(ww, wh)

        self.scene = None
        self.view = None
        self.video_item = None
        self.first_intro_played = True
        self._set_static_background(ww, wh)


        self.dim_layer = QFrame(self)
        self.dim_layer.setGeometry(0, 0, ww, wh)  
        self.dim_layer.setVisible(
            False)  
        self.dim_layer.setStyleSheet("background-color: rgba(0, 0, 0, 150);")
        self.dim_layer.setVisible(False)

        self.header_frame = QFrame(self)
        self.header_frame.setGeometry(0, 0, ww, 40)
        self.header_frame.setStyleSheet("background-color: rgba(40, 40, 40, 190)")

        self.logo = QLabel(self.header_frame)
        self.logo_pix = QPixmap(self.resource_path("assets/pixmaps/logo.png"))
        if not self.logo_pix.isNull():
            self.logo.setPixmap(self.logo_pix)
            self.logo.setScaledContents(True)
        self.logo.setGeometry(10, 8, 168, 24)

        self.logo_separator = QFrame(self.header_frame)  
        self.logo_separator.setFrameShape(QFrame.Shape.VLine)
        self.logo_separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.logo_separator.setStyleSheet("background-color: #777;")
        self.logo_separator.setFixedWidth(3)
        self.logo_separator.setFixedHeight(self.logo.height())
        self.logo_separator.move(self.logo.x() + self.logo.width() + 10, self.logo.y())

        self.tabs_container = QWidget(self.header_frame)
        self.tabs_container.setGeometry(200, 0, 800, 40)
        self.tabs_container.setStyleSheet("background-color: transparent")
        self.tabs_layout = QHBoxLayout(self.tabs_container)
        self.tabs_layout.setContentsMargins(0, 5, 0, 5)
        self.tabs_layout.setSpacing(10)
        self.tabs_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)


        self.tab_news_btn = QPushButton("Главная")
        self.tab_news_btn.setFixedSize(100, 30)
        self.tab_news_btn.setStyleSheet(tabs_style_new)
        self.tab_news_btn.setCheckable(True)
        self.tab_news_btn.setChecked(True)
        self.tab_news_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                            ))
        self.tabs_layout.addWidget(self.tab_news_btn)

        self.tab_installed_mods_btn = QPushButton("Установки")
        self.tab_installed_mods_btn.setFixedSize(100, 30)
        self.tab_installed_mods_btn.setStyleSheet(tabs_style_new)
        self.tab_installed_mods_btn.setCheckable(True)
        self.tab_installed_mods_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                                      ))
        self.tabs_layout.addWidget(self.tab_installed_mods_btn)


        self.tab_settings_btn = QPushButton("Настройки")
        self.tab_settings_btn.setFixedSize(100, 30)
        self.tab_settings_btn.setStyleSheet(tabs_style_new)
        self.tab_settings_btn.setCheckable(True)
        self.tab_settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                                ))
        self.tabs_layout.addWidget(self.tab_settings_btn)

        self.separator_ending = QFrame()  
        self.separator_ending.setFrameShape(QFrame.Shape.VLine)
        self.separator_ending.setFrameShadow(QFrame.Shadow.Sunken)
        self.separator_ending.setStyleSheet("background-color: #777;")
        self.separator_ending.setFixedWidth(3)
        self.separator_ending.setFixedHeight(self.logo.height())
        self.separator_ending.setGeometry(self.tab_settings_btn.x() + self.tab_settings_btn.width() + 10, 8, 2, 24)
        self.separator_ending.setFixedSize(2, 24)
        self.tabs_layout.addWidget(self.separator_ending)


        self.close_btn = QPushButton("✕", self.header_frame)
        self.close_btn.setGeometry(ww - 40, 5, 30, 30)
        self.close_btn.setFont(QFont("sans-serif", 11, QFont.Weight.Bold))

        self.close_btn.setStyleSheet("""
                    QPushButton { background-color: transparent; color: red; border: none; }
                    QPushButton:hover { color: darkred; }
                """)
        self.close_btn.clicked.connect(self.quitSignal.emit)
        self.close_btn.raise_()
        self.close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                         ))

        self.min_btn = QPushButton("—", self.header_frame)
        self.min_btn.setGeometry(ww - 80, 5, 30, 30)
        self.min_btn.setFont(QFont("sans-serif", 11, QFont.Weight.Bold))

        self.min_btn.setStyleSheet("""
                    QPushButton { background-color: transparent; color: #fbac18; border: none; }
                    QPushButton:hover { color: gray; }
                """)
        self.min_btn.clicked.connect(self.launcher.showMinimized)
        self.min_btn.raise_()
        self.min_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                       ))

        self.separator_min = QFrame(self.header_frame)  
        self.separator_min.setFrameShape(QFrame.Shape.VLine)
        self.separator_min.setFrameShadow(QFrame.Shadow.Sunken)
        self.separator_min.setStyleSheet("background-color: #777;")
        self.separator_min.setFixedWidth(3)
        self.separator_min.setFixedHeight(self.logo.height())
        self.separator_min.setGeometry(self.min_btn.x() - 12, 8, 2, 24)

        self.container_frame = QFrame(self)
        self.container_frame.setGeometry(20, 60, 420, 300)
        self.container_layout = QStackedLayout(self.container_frame)

        self.news_page = SmoothScrollArea(self.container_frame)  
        self.news_page.setWidgetResizable(True)
        self.news_page.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.news_page.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.news_page.setStyleSheet("background-color: transparent; border: none;")

        self.fade_overlay = QFrame(self.container_frame)  
        self.fade_overlay.setStyleSheet("""
            background: qlineargradient(
                x1:0, y1:1, x2:0, y2:0,        
                stop:0 rgba(50,50,50,180),     
                stop:1 rgba(50,50,50,0)       
            );
            border: none;
            border-bottom-left-radius: 10px; 
            border-bottom-right-radius: 10px;
        """)
        self.fade_overlay.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        self.fade_overlay.raise_()
        self.fade_overlay.setGeometry(
            self.news_page.x(),
            self.news_page.y() + self.news_page.height() - 50,
            self.news_page.width() - 10,
            50
        )

        self.fade_overlay2 = QFrame(self.container_frame)  
        self.fade_overlay2.setStyleSheet("""
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(50,50,50,180),
                stop:1 rgba(50,50,50,0)
            );
            border: none;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
        """)
        self.fade_overlay2.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.fade_overlay2.raise_()

        self.news_content = QWidget()
        self.news_content.setStyleSheet("background-color: transparent;")
        self.news_content.setAutoFillBackground(True)
        palette = self.news_content.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(40, 40, 40, 1))
        self.news_content.setPalette(palette)
        self.news_layout = QVBoxLayout(self.news_content)
        self.news_layout.setContentsMargins(10, 10, 12, 10)
        self.news_layout.setSpacing(10)

        self.news_page.setWidget(self.news_content)
        self.container_layout.addWidget(self.news_page)  
        self.fade_overlay2.setGeometry(
            0,
            self.news_page.y(),
            self.container_frame.width(),
            50
        )
        self.fade_overlay2.raise_()
  
        self.update_news([{'date': 'Загрузка... | Прокрутите ниже чтобы узнать больше', 'id': 1,
                           'text': 'Подождите, идет загрузка новостей с сервера.....\n' * 4,
                           'title': '    ----- Загрузка новостей... -----'}])
        self.fade_overlay2.raise_()

        mods_content_height = wh - 40

        self.installed_mods_container = QFrame(self)
        self.installed_mods_container.setGeometry(20, 40, self.width() - 40, mods_content_height)
        self.installed_mods_container.setVisible(False)
        self.installed_mods_container.setStyleSheet("background-color: transparent;")

        installed_mods_container_layout = QVBoxLayout(self.installed_mods_container)  
        installed_mods_container_layout.setContentsMargins(0, 0, 0, 0)
        self.installed_mods_page = SmoothScrollArea(self.installed_mods_container)
        self.installed_mods_page.setWidgetResizable(True)
        self.installed_mods_page.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.installed_mods_page.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.installed_mods_page.setStyleSheet("background-color: transparent; border: none;")
        self.installed_mods_content = QWidget(self.installed_mods_page)
        self.installed_mods_content.setStyleSheet("background-color: transparent;")
        self.installed_mods_layout = QGridLayout(self.installed_mods_content)
        self.installed_mods_layout.setContentsMargins(10, 10, 10, 10)
        self.installed_mods_layout.setSpacing(10)
        self.installed_mods_page.setWidget(self.installed_mods_content)
        installed_mods_container_layout.addWidget(self.installed_mods_page)

        self.settings_container = QFrame(self)  
        self.settings_container.setGeometry(20, 40, ww - 40, mods_content_height)
        self.settings_container.setVisible(False)
        self.settings_container.setStyleSheet("background-color: transparent;")

        try:
            self._settings_blur_effect = QtWidgets.QGraphicsBlurEffect()
            self._settings_blur_effect.setBlurRadius(5)
        except Exception:
            self._settings_blur_effect = None

        main_settings_layout = QHBoxLayout(self.settings_container)
        main_settings_layout.setContentsMargins(20, 20, 20, 20)
        main_settings_layout.setSpacing(30)

        try:
            settings_card = self._create_settings_card()
            about_card = self._create_about_card()
            main_settings_layout.addStretch()
            main_settings_layout.addWidget(settings_card)
            main_settings_layout.addStretch()
            main_settings_layout.addWidget(about_card)
            main_settings_layout.addStretch()
        except Exception as e:
            print(e)

        self.information_container = QFrame(self)  
        self.information_container.setGeometry(20, 40, ww - 40, mods_content_height)
        self.information_container.setVisible(False)
        self.information_container.setStyleSheet("background-color: transparent;")

        form_layout = QVBoxLayout(self.information_container)
        form_layout.setContentsMargins(40, 40, 40, 40)
        form_layout.setSpacing(20)

        form_card = QFrame()  
        form_card.setStyleSheet("background-color: rgba(50,50,50,200); border-radius:12px;")
        form_card.setMinimumHeight(400)

        card_lay = QVBoxLayout(form_card)
        card_lay.setContentsMargins(30, 30, 30, 30)
        card_lay.setSpacing(18)

        self.information_title = QLabel(t(self.lang, "about_title"))
        self.information_title.setFixedHeight(42)
        self.information_title.setStyleSheet("color: #ffffff; font-weight: bold; background: transparent;")
        self.information_title.setFont(QFont("sans-serif", 20))
        self.information_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(self.information_title)

        self.info_label = QLabel()
        self.info_label.setFont(QFont("sans-serif", 13))
        self.info_label.setTextFormat(Qt.TextFormat.RichText)
        self.info_label.setWordWrap(True)
        self.info_label.setOpenExternalLinks(True)
        self.info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.info_label.setStyleSheet("color: #e0e0e0; background: transparent;")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        with open(get_resource_path("scripts/html/about.html" if self.lang == "ru" else "scripts/html/about_en.html"), mode="r", encoding="UTF-8") as f:
            self.info_label.setText(f.read())
        

        info_scroll = SmoothScrollArea()
        info_scroll.setWidgetResizable(True)
        info_scroll.setFixedHeight(260)
        info_scroll.setStyleSheet("""
                                    QScrollArea { background: transparent; border: none; }
                                    QWidget#qt_scrollarea_viewport { background: transparent; }
                                    QScrollBar:vertical {
                                            border: none;
                                            background: transparent; 
                                            width: 8px;
                                            border-radius: 4px;
                                            margin: 0px;
                                        }
                                        QScrollBar::handle:vertical {
                                            background: #fbac18;
                                            min-height: 20px;
                                            border-radius: 4px;
                                        }
                                        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
                                        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
                    """)
        info_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        info_container = QWidget()
        info_container.setStyleSheet("background: transparent;")
        info_layout = QVBoxLayout(info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.addWidget(self.info_label)
        info_scroll.setWidget(info_container)
        card_lay.addWidget(info_scroll)

        self.scroll_hint = QLabel(t(self.lang, "about_scroll_hint"))
        self.scroll_hint.setStyleSheet("color: #bbbbbb; font-size: 10px; font-style: italic; background: transparent;")
        self.scroll_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(self.scroll_hint)

        self.back_btn = QPushButton(t(self.lang, "back_btn"))
        self.back_btn.setFixedHeight(44)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: white;
                border-radius: 8px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #555; }
        """)
        self.back_btn.clicked.connect(self._return_to_main_settings)
        card_lay.addWidget(self.back_btn)

        form_layout.addWidget(form_card)
        form_layout.addStretch()

        self.moresettings_container = QFrame(self)  
        self.moresettings_container.setGeometry(20, 40, ww - 40, mods_content_height)
        self.moresettings_container.setVisible(False)
        self.moresettings_container.setStyleSheet("background-color: transparent;")

        form_layout2 = QVBoxLayout(self.moresettings_container)
        form_layout2.setContentsMargins(40, 40, 40, 40)
        form_layout2.setSpacing(20)

        form_card2 = QFrame()  
        form_card2.setStyleSheet("background-color: rgba(50,50,50,200); border-radius:12px;")
        form_card2.setMinimumHeight(400)

        card_lay2 = QVBoxLayout(form_card2)
        card_lay2.setContentsMargins(30, 30, 30, 30)
        card_lay2.setSpacing(18)

        self.more_settings_title = QLabel(t(self.lang, "more_settings_title"))
        self.more_settings_title.setFixedHeight(42)
        self.more_settings_title.setStyleSheet("color: #ffffff; font-weight: bold; background: transparent;")
        self.more_settings_title.setFont(QFont("sans-serif", 20))
        self.more_settings_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay2.addWidget(self.more_settings_title)

        snow_layout = QHBoxLayout()  
        self.snow_label = QLabel(t(self.lang, "snow_label"))
        self.snow_label.setStyleSheet("color: #dddddd; font-size: 11pt; background: transparent;")
        self.snow_switch = SwitchButton()
        self.snow_switch.setFixedSize(52, 28)
        snow_layout.addWidget(self.snow_label)
        snow_layout.addStretch()
        snow_layout.addWidget(self.snow_switch)
        card_lay2.addLayout(snow_layout)

  
        rpc_layout = QHBoxLayout()
        self.rpc_label = QLabel(t(self.lang, "rpc_label"))
        self.rpc_label.setStyleSheet("color: #dddddd; font-size: 11pt; background: transparent;")
        self.rpc_switch = SwitchButton()
        self.rpc_switch.setFixedSize(52, 28)
        rpc_layout.addWidget(self.rpc_label)
        rpc_layout.addStretch()
        rpc_layout.addWidget(self.rpc_switch)
        card_lay2.addLayout(rpc_layout)
  

        lang_layout = QHBoxLayout()
        self.lang_label = QLabel(t(self.lang, "lang_label"))
        self.lang_label.setStyleSheet("color: #dddddd; font-size: 11pt; background: transparent;")
        self.lang_dropdown = DropDown(["Русский", "English"])
        lang_layout.setContentsMargins(0, 8, 0, 8)
        lang_layout.setSpacing(10)
        lang_layout.addWidget(self.lang_label)
        lang_layout.addStretch()
        lang_layout.addWidget(self.lang_dropdown)
        card_lay2.addLayout(lang_layout)

        debug_console_layout = QHBoxLayout()
        self.debug_console_label = QLabel("Включить консоль отладки")
        self.debug_console_label.setStyleSheet("color: #dddddd; font-size: 11pt; background: transparent;")
        self.debug_console_switch = SwitchButton()
        self.debug_console_switch.setFixedSize(52, 28)
        debug_console_layout.addWidget(self.debug_console_label)
        debug_console_layout.addStretch()
        debug_console_layout.addWidget(self.debug_console_switch)
        card_lay2.addLayout(debug_console_layout)
        

        self.plugin_settings_separator = QFrame()
        self.plugin_settings_separator.setFrameShape(QFrame.Shape.HLine)
        self.plugin_settings_separator.setStyleSheet("background-color: #555;")
        self.plugin_settings_separator.setFixedHeight(1)
        self.plugin_settings_separator.setVisible(False)
        card_lay2.addWidget(self.plugin_settings_separator)
        self.plugin_settings_layout = QVBoxLayout()
        card_lay2.addLayout(self.plugin_settings_layout)

        self.lang_dropdown.valueChanged.connect(
            lambda checked: self.settings_changed.emit("lang", checked)
        )

        self.snow_switch.stateChanged.connect(
            lambda checked: self.settings_changed.emit("snow", checked)
        )

        self.rpc_switch.stateChanged.connect(
            lambda checked: self.settings_changed.emit("rpc", checked)
        )

        self.debug_console_switch.stateChanged.connect(
            lambda checked: self.settings_changed.emit("debug_console", checked)
        )


        card_lay2.addStretch()

        self.more_settings_back_btn = QPushButton(t(self.lang, "back_btn"))
        self.more_settings_back_btn.setFixedHeight(44)
        self.more_settings_back_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #444;
                        color: white;
                        border-radius: 8px;
                        font-size: 13px;
                    }
                    QPushButton:hover { background-color: #555; }
                """)
        self.more_settings_back_btn.clicked.connect(self._return_to_main_settings)
        card_lay2.addWidget(self.more_settings_back_btn)

        form_layout2.addWidget(form_card2)  
        form_layout2.addStretch()

        self.plugins_manager_container = QFrame(self)
        self.plugins_manager_container.setGeometry(20, 40, ww - 40, mods_content_height)
        self.plugins_manager_container.setVisible(False)
        self.plugins_manager_container.setStyleSheet("background-color: transparent;")

        plugins_main_layout = QVBoxLayout(self.plugins_manager_container)
        plugins_main_layout.setContentsMargins(40, 40, 40, 40)
        plugins_main_layout.setSpacing(20)

        plugins_card = QFrame()
        plugins_card.setStyleSheet("background-color: rgba(50,50,50,160); border-radius:12px;")
        plugins_card.setMinimumHeight(450)

        plugins_card_lay = QVBoxLayout(plugins_card)
        plugins_card_lay.setContentsMargins(30, 30, 30, 30)
        plugins_card_lay.setSpacing(18)

        self.plugins_title_label = QLabel("Менеджер плагинов")
        self.plugins_title_label.setFixedHeight(42)
        self.plugins_title_label.setStyleSheet("color: #ffffff; font-weight: bold; background: transparent;")
        self.plugins_title_label.setFont(QFont("sans-serif", 20))
        self.plugins_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plugins_card_lay.addWidget(self.plugins_title_label)

        self.plugins_tabs_layout = QHBoxLayout()
        self.plugins_local_tab = QPushButton("Установленные")
        self.plugins_market_tab = QPushButton("Маркетплейс")
        
        tab_style = "QPushButton { background: #444; color: white; border-radius: 5px; padding: 5px; } QPushButton:checked { background: #fbac18; color: black; }"
        self.plugins_local_tab.setStyleSheet(tab_style)
        self.plugins_market_tab.setStyleSheet(tab_style)
        self.plugins_local_tab.setCheckable(True)
        self.plugins_market_tab.setCheckable(True)
        self.plugins_local_tab.setChecked(True)

        self.plugins_local_tab.clicked.connect(lambda: self._switch_plugin_view(False))
        self.plugins_market_tab.clicked.connect(lambda: self._switch_plugin_view(True))

        self.plugins_tabs_layout.addWidget(self.plugins_local_tab)
        self.plugins_tabs_layout.addWidget(self.plugins_market_tab)
        plugins_card_lay.addLayout(self.plugins_tabs_layout)

        self.plugins_scroll = SmoothScrollArea()
        self.plugins_scroll.setWidgetResizable(True)
        self.plugins_scroll.setStyleSheet("""
            SmoothScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                border: none;
                background: transparent; 
                width: 8px;
                border-radius: 4px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #fbac18;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)        
        self.plugins_scroll_content = QWidget()
        self.plugins_scroll_content.setStyleSheet("background: transparent;")
        self.plugins_list_layout = QGridLayout(self.plugins_scroll_content)
        self.plugins_list_layout.setSpacing(15)
        self.plugins_list_layout.setContentsMargins(10, 10, 10, 10)
        self.plugins_list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.plugins_scroll.setWidget(self.plugins_scroll_content)
        plugins_card_lay.addWidget(self.plugins_scroll)

        self.plugins_back_btn = QPushButton(t(self.lang, "back_btn"))
        self.plugins_back_btn.setFixedHeight(44)
        self.plugins_back_btn.setStyleSheet("""
            QPushButton { background-color: #444; color: white; border-radius: 8px; font-size: 13px; }
            QPushButton:hover { background-color: #555; }
        """)
        self.plugins_back_btn.clicked.connect(self._return_to_main_settings)
        plugins_card_lay.addWidget(self.plugins_back_btn)

        plugins_main_layout.addWidget(plugins_card)
        plugins_main_layout.addStretch()

        self.tab_news_btn.clicked.connect(lambda: self._switch_tab(0))
        self.tab_settings_btn.clicked.connect(lambda: self._switch_tab(2))
        self.tab_installed_mods_btn.clicked.connect(lambda: self._switch_tab(3))

        button_size = 48
        spacing = 10
        top_offset = 60
        right_offset = 20
        block_top = top_offset
        block_bottom = self.height() - 30 - button_size
        block_height = block_bottom - block_top + button_size
        self.buttons_block = QFrame(self)
        self.buttons_block.setGeometry(self.width() - right_offset - (button_size + 24), block_top, button_size + 24,  
                                       block_height + 20)
        self.buttons_block.setStyleSheet(
            "background-color: rgba(40, 40, 40, 100); border-radius:10px; padding:2px; border: 1px solid rgba(255, 255, 255, 40);")

        icons = [("telegram.png", "https://t.me/countermine2"),
                 ("youtube.png", "https://www.youtube.com/@CounterMine2"),
                 ("discord.png", "https://discord.com/invite/counter-mine-2-935258545170047006"),
                 ("vkontakte.png", "https://vk.com/countermine"), ("cherrypizza.png", "https://cherry.pizza/")]
        for i, (icon, link) in enumerate(icons):
            btn = QPushButton(self.buttons_block)  
            y = 10 + i * (button_size + spacing)
            btn.setGeometry(12, y, button_size, button_size)
            ico = QIcon(self.resource_path("assets/buttons/" + icon))
            btn.setIcon(ico)
            btn.setIconSize(QSize(button_size, button_size))
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                  ))
            btn.clicked.connect(lambda checked=False, url=link: QDesktopServices.openUrl(QUrl(url)))
            btn.setStyleSheet("border:none; background-color: rgba(50,50,50,140); border-radius: 2px;")
            btn.setToolTip(str(icon.replace(".png", "")))

        self.open_game_directory_btn = QPushButton(self.buttons_block)  
        self.open_game_directory_btn.setGeometry(12, block_height - 2 * button_size - spacing + 9, button_size,
                                                 button_size)
        self.open_game_directory_btn.setIcon(QIcon(self.resource_path("assets/buttons/directory.png")))
        self.open_game_directory_btn.setIconSize(QSize(button_size, button_size))
        self.open_game_directory_btn.clicked.connect(lambda: self.open_directory_clicked.emit())
        self.open_game_directory_btn.setStyleSheet("border:none; background:#323232;")
        self.open_game_directory_btn.setToolTip("Открыть папку игры")
        self.open_game_directory_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
  
        self.reinstall_btn = QPushButton(self.buttons_block)
        self.reinstall_btn.setGeometry(12, block_height - button_size + 9, button_size, button_size)
        self.reinstall_btn.setIcon(QIcon(self.resource_path("assets/buttons/reinstall.png")))
        self.reinstall_btn.setIconSize(QSize(button_size, button_size))
        self.reinstall_btn.clicked.connect(lambda: self.reinstall_client.emit())
        self.reinstall_btn.setStyleSheet("border:none; background:#323232;")
        self.reinstall_btn.setToolTip(t(self.lang, "reinstall_tooltip"))
        self.reinstall_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                             ))
  
        ofw, ofh = 231, 64
        self.online_frame = QFrame(self)
        self.online_frame.setGeometry(28, self.height() - ofh - 10, ofw, ofh)
        self.online_frame.setStyleSheet(
            "background-color: rgba(50,50,50,190); border-radius:8px;border: 1px solid rgba(255, 255, 255, 40);")
        online_layout = QHBoxLayout(self.online_frame)
        online_layout.setContentsMargins(10, 5, 10, 5)
        online_layout.setSpacing(15)

        self.online_gif_label = QLabel(self.online_frame)
        self.static_pixmap = QPixmap(self.resource_path("assets/pixmaps/online_static.png")).scaled(55, 50)
        self.movie = QMovie(self.resource_path("assets/pixmaps/online_animation.gif"))  
        self.movie.setScaledSize(QSize(55, 50))

        self.online_gif_label.setStyleSheet("background: transparent; border: 0px;")

        self.online_gif_label.setPixmap(self.static_pixmap)
        online_layout.addWidget(self.online_gif_label)

        def on_enter(event):  
            if self.movie.isValid():
                self.online_gif_label.setMovie(self.movie)
                self.movie.start()
            return super(self.online_frame.__class__, self.online_frame).enterEvent(event)

        def on_leave(event):  
            self.movie.stop()

            self.online_gif_label.setPixmap(self.static_pixmap)
            return super(self.online_frame.__class__, self.online_frame).leaveEvent(event)

        self.online_frame.enterEvent = on_enter
        self.online_frame.leaveEvent = on_leave

        self.online_label = AnimatedCountLabel(self.lang, self.online_frame)
        self.online_label.setStyleSheet("color:white; font-weight:bold; background: transparent; border: 0px;")
        self.online_label.setFont(QFont("sans-serif", 11))
        online_layout.addWidget(self.online_label, 1)

        pifw, pifh = 80, 64
        self.ping_frame = QFrame(self)
        self.ping_frame.setGeometry(268, self.height() - pifh - 10, pifw, pifh)
        self.ping_frame.setStyleSheet("background-color: rgba(50,50,50,190); border-radius:8px; border: 1px solid rgba(255, 255, 255, 40); ")
        ping_layout = QHBoxLayout(self.ping_frame)
        ping_layout.setContentsMargins(10, 5, 10, 5)
        ping_layout.setSpacing(15)

        self.ping_label = QLabel(f"- {t(self.lang, 'ms_locale')}", self.ping_frame)  
        self.ping_label.setStyleSheet("color:white; font-weight:bold; background: transparent; border: 0px;")
        self.ping_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ping_label.setFont(QFont("sans-serif", 10))
        ping_layout.addWidget(self.ping_label)

        pfw, pfh = 240, ofh

        self.play_btn = QPushButton("Играть", self)
        self.play_btn.setGeometry(self.width() - pfw - 113, self.height() - pfh - 10, pfw, pfh)
        self.play_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                        ))
        self.play_btn.setFont(QFont("sans-serif", 13, QFont.Weight.Bold))
        self.play_btn.setStyleSheet("""
            QPushButton { background-color: #45A049; color:white; border-radius:10px; }
            QPushButton:hover:!disabled { background-color: #45a800; }
            QPushButton:disabled { background-color:#2e6b35; color:#aaa; }
        """)
        self.play_btn.clicked.connect(self.play_clicked.emit)
        self.play_btn.raise_()



    def _create_about_card(self):
        card = QFrame()
        card.setFixedSize(400, 380) 
        card.setStyleSheet("""
            QFrame {
                background-color: rgba(50,50,50,200);
                border-radius: 10px;
                border: none;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 150))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        self.about_title = QLabel(t(self.lang, "about_title"))
        self.about_title.setStyleSheet("color: white; font-weight: bold; background: transparent;")
        self.about_title.setFont(QFont("sans-serif", 16))
        self.about_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.about_title)

        about_main_text = (
            "Лаунчер CounterMine2 - это неофициальный лаунчер проекта CounterMine2. "
            "Проект является полностью бесплатным"
        )
        self.main_label = QLabel(about_main_text)
        self.main_label.setStyleSheet("color: #dddddd; font-size: 12pt; background: transparent;")
        self.main_label.setFont(QFont("sans-serif", 10))
        self.main_label.setWordWrap(True)  
        self.main_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.main_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.main_label)
       
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.HLine)
        separator1.setFrameShadow(QFrame.Shadow.Sunken)
        separator1.setStyleSheet("background-color: #777; height: 1px;")  
        layout.addWidget(separator1)

        self.more_btn = QPushButton(t(self.lang, "more_btn_text"))
        self.more_btn.setFixedHeight(40) 
        self.more_btn.setStyleSheet(new_btn_style) 
        self.more_btn.clicked.connect(lambda: self._switch_to_moresettings_page())
        layout.addWidget(self.more_btn)

        self.plugins_btn = QPushButton(t(self.lang, "plugins_btn"))
        self.plugins_btn.setFixedHeight(40)
        self.plugins_btn.setStyleSheet(new_btn_style) 
        self.plugins_btn.clicked.connect(lambda: self._switch_to_plugins_page())
        layout.addWidget(self.plugins_btn)

        self.formalities_btn = QPushButton(t(self.lang, "more_btn_text2"))
        self.formalities_btn.setFixedHeight(40) 
        self.formalities_btn.setStyleSheet(new_btn_style) 
        self.formalities_btn.clicked.connect(lambda: self._switch_to_formalities_page())
        layout.addWidget(self.formalities_btn)

        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)  
        separator2.setStyleSheet("background-color: #777; height: 1px;")
        layout.addWidget(separator2)

        self.tech_info_label = QLabel(f"version: {self.version} by raizor ") 
        self.tech_info_label.setStyleSheet("color: #999999; font-size: 10pt; background: transparent;")
        self.tech_info_label.setFont(QFont("sans-serif", 9))
        self.tech_info_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.tech_info_label)
        layout.addStretch()
        return card

    def _switch_to_formalities_page(self):
        self.settings_container.setVisible(False)
        self.dim_layer.setVisible(True)
        self.dim_layer.raise_()
        self._apply_blur_to_settings_background(False)

        self.information_container.setVisible(True)
        self._animate_container(self.information_container)
        self.information_container.raise_()
        self.header_frame.raise_()
        self.tab_settings_btn.setChecked(True)

    def _switch_to_moresettings_page(self):
        self.settings_container.setVisible(False)
        self.dim_layer.setVisible(True)
        self.dim_layer.raise_()
        self._apply_blur_to_settings_background(False)

        self.moresettings_container.setVisible(True)  
        self._animate_container(self.moresettings_container)
        self.moresettings_container.raise_()
        self.header_frame.raise_()
        self.tab_settings_btn.setChecked(True)

    def _switch_to_plugins_page(self):
        self.settings_container.setVisible(False)
        self.dim_layer.setVisible(True)
        self.dim_layer.raise_()
        self._apply_blur_to_settings_background(False)

        self.plugins_manager_container.setVisible(True)
        self._animate_container(self.plugins_manager_container)
        self.plugins_manager_container.raise_()
        self.header_frame.raise_()
        self.tab_settings_btn.setChecked(True)  
        self._populate_plugins()

    def _switch_plugin_view(self, market: bool):
        self.plugin_market_view = market
        self.plugins_local_tab.setChecked(not market)
        self.plugins_market_tab.setChecked(market)

        if market:
            self._show_market_loading()

            threading.Thread(target=self._load_market_data, daemon=True).start()
        else:
            self.launcher.plugin_manager.check_for_updates() 
            self._populate_plugins()

    def _show_market_loading(self):
        while self.plugins_list_layout.count():
            item = self.plugins_list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        loading_container = QWidget()
        loading_lay = QVBoxLayout(loading_container)

        spinner_lbl = QLabel()
        spinner_movie = QMovie(self.resource_path("assets/pixmaps/online_animation.gif"))
        spinner_lbl.setMovie(spinner_movie)
        spinner_movie.start()

        loading_text = QLabel(t(self.lang, "plugins_loading"))
        loading_text.setStyleSheet("color: #fbac18; font-size: 14px; font-weight: bold; background: transparent;")

        loading_lay.addStretch()
        loading_lay.addWidget(spinner_lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        loading_lay.addWidget(loading_text, alignment=Qt.AlignmentFlag.AlignCenter)
        loading_lay.addStretch()

        self.plugins_list_layout.addWidget(loading_container, 0, 0, 1, 3)

    def _show_market_error(self):
        while self.plugins_list_layout.count():
            item = self.plugins_list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        error_container = QWidget()
        error_lay = QVBoxLayout(error_container)
        error_lay.setSpacing(20)

        err_icon = QLabel("⚠️")
        err_icon.setStyleSheet("font-size: 48px; background: transparent; border: none;")

        err_text = QLabel(t(self.lang, "plugins_error"))
        err_text.setStyleSheet("color: #d32f2f; font-size: 16px; font-weight: bold; background: transparent; border: none;")

        retry_btn = QPushButton(t(self.lang, "btn_retry"))
        retry_btn.setFixedSize(160, 40)
        retry_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        retry_btn.setStyleSheet(new_btn_style)
        retry_btn.clicked.connect(lambda: self._switch_plugin_view(True))

        error_lay.addStretch()
        error_lay.addWidget(err_icon, alignment=Qt.AlignmentFlag.AlignCenter)
        error_lay.addWidget(err_text, alignment=Qt.AlignmentFlag.AlignCenter)
        error_lay.addWidget(retry_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        error_lay.addStretch()

        self.plugins_list_layout.addWidget(error_container, 0, 0, 1, 3)

    def _load_market_data(self):
        try:
            if self.launcher.fetch_remote_plugins():
                self.launcher.plugin_manager.check_for_updates()
                QtCore.QMetaObject.invokeMethod(self, "_populate_plugins", Qt.ConnectionType.QueuedConnection)
            else:
                QtCore.QMetaObject.invokeMethod(self, "_show_market_error", Qt.ConnectionType.QueuedConnection)
        except Exception as e:
            print(e)

    @pyqtSlot()
    def _populate_plugins(self):
        try:
            while self.plugins_list_layout.count():
                item = self.plugins_list_layout.takeAt(0)
                if item.widget(): item.widget().deleteLater()
            self.market_icon_labels.clear()

            if not hasattr(self.launcher, 'plugin_manager'): return

            if self.plugin_market_view:
                raw_plugins = self.launcher.remote_plugins
                
                maintenance_data = getattr(self.launcher, 'maintenance_data', [])
                for m_idx, info in enumerate(maintenance_data):  
                    m_card = self._create_maintenance_card(info)
                    self.plugins_list_layout.addWidget(m_card, m_idx, 0, 1, 3)
                if len(maintenance_data) > 0:
                    return
                row_offset = len(maintenance_data)
                
                if isinstance(raw_plugins, dict):
                    current_row = row_offset  
                    for category, plugins in raw_plugins.items():
                        cat_lbl = QLabel(category.upper())
                        cat_lbl.setStyleSheet("color: #777; font-size: 12px; font-weight: bold; margin-top: 10px; margin-bottom: 5px; background: transparent;")
                        self.plugins_list_layout.addWidget(cat_lbl, current_row, 0, 1, 3)
                        current_row += 1
                        
                        for i, plugin in enumerate(plugins):
                            card = self._create_plugin_card(plugin)
                            self.plugins_list_layout.addWidget(card, current_row + (i // 3), i % 3)
                        
                        current_row += (len(plugins) + 2) // 3
                    return 
                else:
                    plugins_to_show = raw_plugins
            else:
                plugins_to_show = self.launcher.plugin_manager.discovered_plugins if hasattr(self.launcher, 'plugin_manager') else []  
                row_offset = 0

            for i, plugin in enumerate(plugins_to_show):
                card = self._create_plugin_card(plugin)
                self.plugins_list_layout.addWidget(card, row_offset + (i // 3), i % 3)
        except Exception as e:
            print(f"[UI] Error populating plugins: {e}")
            import traceback
            traceback.print_exc()
            self._show_market_error()

    def _create_plugin_card(self, plugin):
        plugin_id = plugin.get('id')
        plugin_name = plugin.get('name')
        is_internal = plugin.get('class') and plugin['class'].__module__.startswith('scripts.internal')
        is_enabled = self.launcher.plugin_states.get(plugin_id, True)
        already_installed = any(p['id'] == plugin_id or p['name'] == plugin_name for p in self.launcher.plugin_manager.discovered_plugins)
        
        card_width = (self.plugins_manager_container.width() - 460) // 2  
        card = QFrame()
        card.setFixedSize(card_width, 180)
        card.setStyleSheet("background-color: rgba(60,60,60,200); border-radius: 12px;")

        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 12, 12, 12)
        
        header = QHBoxLayout()
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(64, 64)
        icon_path = plugin.get('icon')
        icon_url = plugin.get('icon_url')  
        if not self.plugin_market_view and icon_path:
            path = self.resource_path(icon_path) if not os.path.isabs(icon_path) else icon_path
            pix = QPixmap(path)
            if not pix.isNull():
                icon_lbl.setPixmap(pix.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                icon_lbl.setStyleSheet("background-color: #444; border-radius: 10px;")
        elif self.plugin_market_view and icon_url:
            icon_lbl.setStyleSheet("background-color: #333; border-radius: 10px;")
            self.market_icon_labels[plugin_id] = icon_lbl
            loader = MarketIconLoader(plugin_id, icon_url)
            loader.signals.loaded.connect(self._on_market_icon_loaded)
            QtCore.QThreadPool.globalInstance().start(loader)
        else:  
            icon_lbl.setStyleSheet("background-color: #444; border-radius: 20px;")
        header.addWidget(icon_lbl)
        
        name_lbl = QLabel(f"<b>{plugin['name']}</b>")
        name_lbl.setStyleSheet("color: white; font-size: 17px; background: transparent;")
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignBottom)
        name_lbl.setWordWrap(True)
        header.addWidget(name_lbl, 1)  
        
        if self.plugin_market_view:
            toggle = QPushButton(t(self.lang, "btn_install"))
            toggle.setFixedSize(80, 30)
            toggle.setStyleSheet("background: #45A049; color: white; border-radius: 5px;")
            if already_installed:
                toggle.setText(t(self.lang, "btn_installed"))
                toggle.setEnabled(False)
                toggle.setStyleSheet("background: #555; color: #888; border-radius: 5px;")
            else:
                toggle.clicked.connect(lambda _, p=plugin, b=toggle: self._install_plugin(p, b))
            header.addWidget(toggle)
        else:
            update_available = plugin.get('update_available', False)
            if update_available:
                update_btn = QPushButton(t(self.lang, "btn_update").format(v=plugin['latest_version']))
                update_btn.setFixedHeight(30)
                update_btn.setStyleSheet("background: #0288d1; color: white; border-radius: 5px; font-weight: bold;")
                update_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                update_btn.clicked.connect(lambda _, p=plugin, b=update_btn: self._update_plugin(p, b))
                header.addWidget(update_btn)
            else:
                toggle = SwitchButton()
                toggle.setChecked(is_enabled)
                toggle.stateChanged.connect(lambda checked, pid=plugin_id: self.settings_changed.emit("plugin_state", (pid, checked)))
                header.addWidget(toggle)
        lay.addLayout(header)
        
        desc_lbl = QLabel(plugin['description'])
        desc_lbl.setStyleSheet("color: #bbb; font-size: 13px; background: transparent;")
        desc_lbl.setWordWrap(True)
        lay.addWidget(desc_lbl)
        lay.addStretch() 
        
        footer = QHBoxLayout()
        meta_lbl = QLabel(f"v{plugin['version']} | {plugin['author']}")
        meta_lbl.setStyleSheet("color: #777; font-size: 10px; background: transparent;")
        is_essential = getattr(plugin.get('class'), 'is_essential', False)
        footer.addWidget(meta_lbl)
        if not self.plugin_market_view and not is_internal and not is_essential:
            footer.addStretch()
            del_btn = QPushButton(t(self.lang, "btn_delete_plugin"))
            del_btn.setFixedSize(70, 22)
            del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            del_btn.setStyleSheet("background: #d32f2f; color: white; border-radius: 4px; font-size: 10px; font-weight: bold;")
            del_btn.clicked.connect(lambda _, pid=plugin_id: self._delete_plugin(pid))
            footer.addWidget(del_btn)
        lay.addLayout(footer)
        return card

    def _create_maintenance_card(self, info):
        card = QFrame()
        card.setFixedHeight(95)
        card.setObjectName("maintenanceCard")
        
        if isinstance(info, dict):
            title = info.get('title', 'Внимание')
            desc = info.get('description', '')
            m_type = info.get('type', 'warning') 
            status_text = info.get('status_text', 'LIVE')
        else:
            title = 'Внимание'
            desc = str(info)
            m_type = 'warning'
            status_text = 'LIVE'

        styles = {
            'warning': {
                'bg': 'qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(251, 172, 24, 40), stop:1 rgba(211, 47, 47, 40))',
                'border': 'rgba(251, 172, 24, 100)',
                'shadow': 'rgba(251, 172, 24, 40)',
                'accent': '#fbac18',
                'icon': '⚠️'
            },
            'error': {
                'bg': 'qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(211, 47, 47, 50), stop:1 rgba(183, 28, 28, 50))',
                'border': 'rgba(211, 47, 47, 120)',
                'shadow': 'rgba(211, 47, 47, 50)',
                'accent': '#ff5252',
                'icon': '🚫'
            },
            'info': {
                'bg': 'qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(33, 150, 243, 40), stop:1 rgba(25, 118, 210, 40))',
                'border': 'rgba(33, 150, 243, 100)',
                'shadow': 'rgba(33, 150, 243, 40)',
                'accent': '#4fc3f7',
                'icon': 'ℹ️'
            }
        }
        
        style = styles.get(m_type, styles['warning'])
        
        card.setStyleSheet(f"""
            QFrame#maintenanceCard {{
                background: {style['bg']};
                border: 1px solid {style['border']};
                border-radius: 15px;
            }}
        """)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(25)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(style['shadow']))
        card.setGraphicsEffect(shadow)
        
        lay = QHBoxLayout(card)
        lay.setContentsMargins(20, 10, 20, 10)
        lay.setSpacing(15)
        
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(40, 40)
        icon_path = self.resource_path(f"assets/icons/{m_type}.png")
        pix = QPixmap(icon_path)
        if not pix.isNull():
            icon_lbl.setPixmap(pix.scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            icon_lbl.setText(style['icon'])
            icon_lbl.setStyleSheet(f"font-size: 26px; color: {style['accent']}; background: transparent; border: none;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(icon_lbl)
        
        text_lay = QVBoxLayout()
        text_lay.setSpacing(2)
        
        title_lbl = QLabel(f"<b>{title}</b>")
        title_lbl.setStyleSheet(f"color: {style['accent']}; font-size: 16px; background: transparent; border: none;")
        
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet("color: #ffffff; font-size: 13px; background: transparent; border: none;")
        desc_lbl.setWordWrap(True)
        
        text_lay.addWidget(title_lbl)
        text_lay.addWidget(desc_lbl)
        lay.addLayout(text_lay, 1)

        status_lbl = QLabel(status_text)
        status_lbl.setFixedSize(55, 22)
        status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_lbl.setStyleSheet(f"""
            background: {style['accent']};
            color: black;
            font-size: 10px;
            font-weight: bold;
            border-radius: 11px;
            border: none;
        """)
        lay.addWidget(status_lbl)
        
        return card

    def _on_market_icon_loaded(self, plugin_id, data):
        if plugin_id in self.market_icon_labels:
            label = self.market_icon_labels[plugin_id]
            try:
                pix = QPixmap()
                pix.loadFromData(data)
                if not pix.isNull():
                    label.setPixmap(pix.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))  
                    label.setStyleSheet("background: transparent;")
            except Exception as e:
                self.launcher.write_log(f"Error displaying marketplace icon for {plugin_id}: {e}")

    def _delete_plugin(self, plugin_id):
        if self.launcher.delete_external_plugin(plugin_id):
            self._populate_plugins()

    def _install_plugin(self, plugin, button):
        button.setEnabled(False)
        button.setText(t(self.lang, "btn_installing"))
        button.setStyleSheet("background: #555; color: #888; border-radius: 5px;")

        def run_install():
            if self.launcher.install_plugin_from_url(plugin):
                QtCore.QMetaObject.invokeMethod(self, "_on_install_success", Qt.ConnectionType.QueuedConnection)
            else:
                QtCore.QMetaObject.invokeMethod(self, "_populate_plugins", Qt.ConnectionType.QueuedConnection)
        
        threading.Thread(target=run_install, daemon=True).start()

    @pyqtSlot()
    def _on_install_success(self):  
        self._switch_plugin_view(False)

    def _update_plugin(self, plugin_data, button):
        plugin_id = plugin_data.get('id')
        plugin_name = plugin_data.get('name')
        latest_version = plugin_data.get('latest_version')

        reply = QtWidgets.QMessageBox.question(
            self,
            t(self.lang, "plugin_update_confirm_title"),
            t(self.lang, "plugin_update_confirm_text").format(name=plugin_name, version=latest_version),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.Yes
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        button.setEnabled(False)
        button.setText(t(self.lang, "btn_installing"))

        def run_update():
            success = self.launcher.plugin_manager.update_plugin(plugin_id)
            QtCore.QMetaObject.invokeMethod(self, "_on_update_finished", Qt.ConnectionType.QueuedConnection,
                                            QtCore.Q_ARG(bool, success))

        threading.Thread(target=run_update, daemon=True).start()

    @pyqtSlot(bool)
    def _on_update_finished(self, success):
        if success:
            QtWidgets.QMessageBox.information(self, t(self.lang, "plugin_update_success_title"), t(self.lang, "plugin_update_success_text"))
        else:
            QtWidgets.QMessageBox.warning(self, t(self.lang, "plugin_update_error_title"), t(self.lang, "plugin_update_error_text"))
        self.launcher.plugin_manager.load_plugins()
        self._populate_plugins()

    def _update_nick_scroll(self):
        status_width = self.status.geometry().width()
        balance_width = self.balance_frame.geometry().width()
        top_width = self.top.geometry().width()

        available_width = top_width - balance_width - status_width - 16
        self.nick_scroll.setFixedWidth(abs(available_width))
        self.nick_scroll.scroll_step()

    def _toggle_logout_menu(self):
        if hasattr(self, 'logout_menu'):  
            if self.logout_menu.isVisible():
                self.logout_menu.hide()
            else:
                nick_global_pos = self.nick_scroll.mapTo(self.logout_menu.parent(), QPoint(0, 0))
                menu_x = nick_global_pos.x()
                menu_y = nick_global_pos.y() + self.nick_scroll.height() + 5
                self.logout_menu.move(menu_x, menu_y)
                self.logout_menu.show()
                self.logout_menu.raise_()

    def _on_logout_clicked(self):
        self.logout_menu.hide()
        self.auth_logout_clicked.emit()

    def eventFilter(self, obj, event):  
        if event.type() == event.Type.MouseButtonPress:
            if hasattr(self, 'logout_menu') and self.logout_menu.isVisible():
                if not self.logout_menu.geometry().contains(event.pos()) and \
                        not self.nick_scroll.geometry().contains(event.pos()):
                    self.logout_menu.hide()

        return super().eventFilter(obj, event)

    def _create_settings_card(self):
        card = QFrame()  
        card.setFixedSize(400, 380)
        card.setStyleSheet("""
            QFrame {
                background-color: rgba(50,50,50,200);
                border-radius: 10px;
                border: none;
            }
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 150))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        self.settings_title = QLabel("Аккаунт")
        self.settings_title.setStyleSheet("color: white; font-weight: bold; background: transparent;")
        self.settings_title.setFont(QFont("sans-serif", 16))
        self.settings_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.settings_title)

        def cherry():  
            lbl = QLabel()
            pix = QPixmap(self.resource_path("assets/pixmaps/cherry.png")).scaled(22, 22, Qt.AspectRatioMode.KeepAspectRatio,
                                                                          Qt.TransformationMode.SmoothTransformation)
            lbl.setPixmap(pix)
            return lbl

        top = QFrame()
        top.setFixedHeight(60)  
        top.setStyleSheet("""
               QFrame {
                   background-color: rgba(50,50,50,200);
                   border-radius: 6px;
               }
           """)
        t = QHBoxLayout(top)
        t.setContentsMargins(10, 6, 10, 6)
        t.setSpacing(8)
        self.bal = QLabel("0")
        self.bal.setStyleSheet("color: white; font-size: 13px;")
        balance_frame = QFrame()
        balance_frame.setFixedHeight(34)
        balance_frame.setStyleSheet("""
            QFrame {
                background-color: #24282b;
                border-radius: 6px;
                border: 1px solid #e2a400;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)

        bf = QHBoxLayout(balance_frame)
        bf.setContentsMargins(6, 2, 6, 2)
        bf.setSpacing(4)

        bf.addWidget(cherry())
        bf.addWidget(self.bal)
        t.addWidget(balance_frame)

        font = QFont("Press Start 2P")
        font.setWeight(QFont.Weight.DemiBold)
        font.setPixelSize(18)
        font2 = QFont("PIXY")
        font2.setWeight(QFont.Weight.DemiBold)
        font2.setPixelSize(20)
  
        self.top = top
        self.balance_frame = balance_frame

        self.nick_scroll = ScrollingNick("", 0)
        self.nick_scroll.label1.setFont(font)
        self.nick_scroll.label2.setFont(font)
        self.nick_scroll.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                           ))
        self.nick_scroll.mousePressEvent = lambda e: self._toggle_logout_menu()

        text_width = self.nick_scroll.label1.sizeHint().width()
        self.nick_scroll.container.setMinimumWidth(text_width * 2)  

        QTimer.singleShot(50, self._update_nick_scroll)
        t.addWidget(self.nick_scroll, stretch=1)
        t.addStretch()

        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setFixedSize(140, 45)
        self.status.setStyleSheet("""
        QLabel {
            padding-left: 2px;
            color: white;
            font-weight: bold;
            background-color: #fbac18; 
            border-top: 4px solid #ffcd45;
            border-bottom: 4px solid #6f5909;
            border-radius: 0px;
            letter-spacing: 1px;
        }
        """)
        self.status.setFont(font2)

        t.addWidget(self.status)

        layout.addWidget(top)

        self.auth_logged_in_frame = top
  
        bottom = QFrame()
        bottom.setFixedHeight(60)
        bottom.setStyleSheet("""
               QFrame {
                   background-color: rgba(50,50,50,200);
                   border-radius: 6px;
               }
           """)
        b = QHBoxLayout(bottom)
        b.setContentsMargins(10, 6, 10, 6)
        b.setSpacing(8)
        cherry_frame = QFrame()  
        cherry_frame.setFixedHeight(34)
        cherry_frame.setStyleSheet("""
            QFrame {
                background-color: #24282b;
                border-radius: 6px;
                border: 1px solid #e2a400;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        cf_layout = QHBoxLayout(cherry_frame)
        cf_layout.setContentsMargins(6, 2, 6, 2)
        cf_layout.setSpacing(4)  
        cf_layout.addWidget(cherry())
        b.addWidget(cherry_frame)
        b.addSpacing(8)
        self.auth_login_btn = QPushButton()
        self.auth_login_btn.setFixedHeight(36)
        self.auth_login_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.auth_login_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                              ))
        self.auth_login_btn.setStyleSheet("""
            QPushButton {
                background-color: #2f46a3;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #3956c7;
            }
        """)
        btn_layout = QHBoxLayout(self.auth_login_btn)
        btn_layout.setContentsMargins(10, 0, 10, 0)
        btn_layout.setSpacing(6)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        svg_data = b'''<svg width="24" height="24" viewBox="0 0 24 24" fill="#fbac18">
        <path d="M9 0H15V1.5H16.5V3H18V9H16.5V10.5H15V12H9V10.5H7.5V9H6V3H7.5V1.5H9V0ZM10.5 7.5V9H13.5V7.5H15V4.5H13.5V3H10.5V4.5H9V7.5H10.5ZM6 13.5H18V15H21V16.5H22.5V18H24V24H0V18H1.5V16.5H3V15H6V13.5ZM4.5 19.5H3V21H21V19.5H19.5V18H16.5V16.5H7.5V18H4.5V19.5Z" fill="currentColor"/>
        </svg>''' 
        svg_data = svg_data.replace(b'currentColor', b'#fbac18')
        human = QSvgWidget()
        human.load(svg_data)
        human.setStyleSheet("color: white;")
        human.setFixedSize(16, 16)

        self.auth_login_label = QLabel("ВХОД")
        self.auth_login_label.setStyleSheet(
            "color: white; font-weight: bold; font-size: 14px; text-transform: uppercase;background:transparent;")
        btn_layout.addStretch()
        btn_layout.addWidget(human)
        btn_layout.addWidget(self.auth_login_label)
        btn_layout.addStretch()
        self.auth_login_btn.clicked.connect(self.auth_login_clicked.emit)

        b.addWidget(self.auth_login_btn)
        layout.addWidget(bottom)  

        self.auth_logged_out_frame = bottom

        self.stats_container = QFrame()
        self.stats_container.setStyleSheet("background-color: transparent;")
        stats_layout = QVBoxLayout(self.stats_container)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(10)

        self.stats_grid = QGridLayout()
        self.stats_grid.setSpacing(8)
        stats_layout.addLayout(self.stats_grid)

        layout.addWidget(self.stats_container)

        layout.addStretch()

        self.auth_logged_in_frame.hide()
        self.auth_logged_out_frame.show()
        self.stats_container.hide()

        self.logout_menu = QFrame(card)  
        self.logout_menu.setFixedSize(150, 40)
        self.logout_menu.setStyleSheet("""
            QFrame {
                background-color: #3a3a3c;
                border-radius: 6px;
                border: 1px solid #555;
            }
        """)
        self.logout_menu.hide()
        self.logout_menu.raise_()

        logout_shadow = QGraphicsDropShadowEffect()
        logout_shadow.setBlurRadius(15)
        logout_shadow.setOffset(0, 3)
        logout_shadow.setColor(QColor(0, 0, 0, 180))
        self.logout_menu.setGraphicsEffect(logout_shadow)

        logout_menu_layout = QVBoxLayout(self.logout_menu)  
        logout_menu_layout.setContentsMargins(5, 5, 5, 5)
        logout_menu_layout.setSpacing(0)

        self.logout_menu_btn = QPushButton("Выйти")
        self.logout_menu_btn.setFixedHeight(30)
        self.logout_menu_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                               ))
        self.logout_menu_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ff5555;
                border: none;
                font-weight: bold;
                font-size: 12px;
                text-align: left;
                padding-left: 10px;
            }
            QPushButton:hover {
                background-color: #505055;
                border-radius: 4px;
            }
        """)
        self.logout_menu_btn.clicked.connect(self._on_logout_clicked)  
        logout_menu_layout.addWidget(self.logout_menu_btn)

        return card

    def set_profile_status(self, role, balance):
        if role:
            self.status.show()
            self.status.setText(str(role))
            self.status.setStyleSheet("""
            QLabel {
                padding-left: 2px;
                color: white;
                font-weight: bold;
                background-color: #fbac18;
                border-top: 4px solid #ffcd45;
                border-bottom: 4px solid #6f5909;
                border-radius: 0px;
                letter-spacing: 1px;
            }
            """)
        else:
            self.status.hide()
        self.bal.setText(str(balance) if balance is not None else "0")

    @pyqtSlot(dict)
    def update_auth_ui(self, user_data):
        try:
            if user_data:
                self.auth_logged_in_frame.show()
                self.stats_container.show()
                self.auth_logged_out_frame.hide()

                nick = user_data.get("nickname", "-")
                balance = user_data.get("balance", 0)

                user_type = user_data.get("type", "DEFAULT")
                is_prime = user_data.get("prime", False)

                role = str(user_type)
                if role == "DEFAULT":
                    if is_prime:
                        role = "PRIME"
                    else:
                        role = " "

                self.nick_scroll.setText(nick)
                self.set_profile_status(role, balance)

                for i in reversed(range(self.stats_grid.count())):
                    self.stats_grid.itemAt(i).widget().setParent(None)

                game_stats = user_data.get("gameStats", {})
                stats_list = []
                if game_stats and "edges" in game_stats:
                    stats_list = game_stats["edges"]

                stats_map = {}
                for edge in stats_list:
                    node = edge.get("node", {})
                    t_type = node.get("type", "").upper()
                    stats_map[t_type] = node.get("total", 0)

                desired_stats = [
                    "KILL", "DEATH", "PLAYTIME",
                    "SHOOT", "BOMB_PLANT", "BOMB_DEFUSE",
                ]

                row, col = 0, 0
                for stat_key in desired_stats:
                    val = stats_map.get(stat_key, "-")
                    if val != "-":
                        val = str(val)

                    display_key = stat_key.lower()

                    self._create_stat_card(row, col, f"{display_key}: {val}")
                    col += 1
                    if col >= 2:
                        col = 0
                        row += 1

                kills = stats_map.get("KILL", 0)
                deaths = stats_map.get("DEATH", 0)
                kd = kills / deaths if deaths > 0 else kills

                playtime_min = stats_map.get("PLAYTIME", 0)
                playtime_hours = playtime_min / 60

                summary_text = f"KD: {kd:.2f} | {playtime_hours:.1f} HOURS"
                self._create_stat_card(row, 0, summary_text, colspan=2)

            else:
                self.auth_logged_in_frame.hide()
                self.auth_logged_out_frame.show()
                self.stats_container.show()

                for i in reversed(range(self.stats_grid.count())):
                    self.stats_grid.itemAt(i).widget().setParent(None)

                desired_stats = [
                    "KILL", "DEATH", "PLAYTIME",
                    "SHOOT", "BOMB_PLANT", "BOMB_DEFUSE",
                ]
                row, col = 0, 0
                for stat_key in desired_stats:
                    self._create_stat_card(row, col, f"{stat_key.lower()}: -")
                    col += 1
                    if col >= 2:
                        col = 0
                        row += 1

                self._create_stat_card(row, 0, "KD: - | - HOURS", colspan=2)

        except: pass

    def _create_stat_card(self, row, col, text, colspan=1):
        stat_card = QFrame()
        stat_card.setStyleSheet("""
            QFrame {
                background-color: #3d3938;
                border-top: 4px solid #6b6b6b;
                border-bottom: 4px solid #202020;
                border-left: none;
                border-right: none;
                border-radius: 0px;
            }
        """)
        stat_card.setFixedHeight(56)
        stat_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(stat_card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(2)

        lbl = QLabel(text.upper())
        lbl.setStyleSheet("""
            color: #d6d3d1; 
            font-weight: 600; 
            font-size: 13px;  
            background: transparent;
            border: none;
        """)
        layout.addWidget(lbl)

        self.stats_grid.addWidget(stat_card, row, col, 1, colspan)

    def _apply_blur_to_settings_background(self, enable: bool):
        if not self.settings_container:
            return

        if enable:
            if self._settings_blur_effect:
                try:
                    self._settings_blur_effect.setEnabled(True)
                    return
                except RuntimeError:
                    self._settings_blur_effect = None

            self._settings_blur_effect = QtWidgets.QGraphicsBlurEffect(self.settings_container)
            self._settings_blur_effect.setBlurRadius(10)
            self.settings_container.setGraphicsEffect(self._settings_blur_effect)
        else:
            if self._settings_blur_effect:
                try:
                    self._settings_blur_effect.setEnabled(False)
                    self.settings_container.setGraphicsEffect(None)
                except RuntimeError:
                    pass


    def _return_to_main_settings(self):
        active_container = None
        if self.information_container.isVisible():
            active_container = self.information_container
        elif self.moresettings_container.isVisible():
            active_container = self.moresettings_container
        elif self.plugins_manager_container.isVisible():
            active_container = self.plugins_manager_container

        if active_container:
            def on_animation_finished():
                self.dim_layer.setVisible(True)
                self.settings_container.setVisible(True)
                self.settings_container.raise_()
                self.header_frame.raise_()
                self._animate_container(self.settings_container)
                self.tab_settings_btn.setChecked(True)
            
            self._animate_out_container(active_container, on_animation_finished)
        else:
            self.dim_layer.setVisible(True)
            self.settings_container.setVisible(True)
            self.settings_container.raise_()
            self.header_frame.raise_()

    def _animate_out_container(self, container, callback=None):
        if not container: return
        if hasattr(container, '_active_group'):
            container._active_group.stop()

        current_effect = container.graphicsEffect()
        if current_effect and isinstance(current_effect, QtWidgets.QGraphicsOpacityEffect):
            effect = current_effect
            container._effect_owned = False
        else:
            effect = QtWidgets.QGraphicsOpacityEffect(container)
            container.setGraphicsEffect(effect)
            container._effect_owned = True

        group = QtCore.QParallelAnimationGroup()
        
        opacity_anim = QtCore.QPropertyAnimation(effect, b"opacity")
        opacity_anim.setDuration(250)
        opacity_anim.setStartValue(1.0)
        opacity_anim.setEndValue(0.0)
        opacity_anim.setEasingCurve(QtCore.QEasingCurve.Type.InCubic)

        pos_anim = QtCore.QPropertyAnimation(container, b"pos")
        pos_anim.setDuration(250)
        target_pos = getattr(container, '_target_pos', container.pos())
        pos_anim.setStartValue(target_pos)
        pos_anim.setEndValue(QtCore.QPoint(target_pos.x() + 20, target_pos.y()))
        pos_anim.setEasingCurve(QtCore.QEasingCurve.Type.InCubic)
        pos_anim.valueChanged.connect(lambda: self.update())

        group.addAnimation(opacity_anim)
        group.addAnimation(pos_anim)

        def internal_cleanup():
            container.setVisible(False)
            try:
                if getattr(container, '_effect_owned', False):
                    container.setGraphicsEffect(None)
                    delattr(container, '_effect_owned')
            except Exception:
                pass
            container.move(target_pos)
            if callback: callback()

        group.finished.connect(internal_cleanup)
        container._active_group = group
        group.start()

    def _animate_container(self, container: QFrame | QPushButton |QLabel |QScrollArea):
        if not container:
            return

        if hasattr(container, '_active_group'):
            container._active_group.stop()

        effect = container.graphicsEffect()
        if effect and isinstance(effect, QtWidgets.QGraphicsOpacityEffect):
            container._effect_owned = False
        else:
            effect = QtWidgets.QGraphicsOpacityEffect(container)
            container.setGraphicsEffect(effect)
            container._effect_owned = True

        opacity_animation = QtCore.QPropertyAnimation(effect, b"opacity")
        opacity_animation.setDuration(500)
        opacity_animation.setStartValue(0.0)
        opacity_animation.setEndValue(1.0)
        opacity_animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)

        target_pos = container.pos()
        if hasattr(container, '_target_pos'):
            target_pos = container._target_pos
        else:
            container._target_pos = target_pos

        slide_offset_x = 20

        position_animation = QtCore.QPropertyAnimation(container, b"pos")
        position_animation.setDuration(500)
        position_animation.setStartValue(QtCore.QPoint(target_pos.x() + slide_offset_x, target_pos.y()))
        position_animation.setEndValue(target_pos)
        position_animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        position_animation.valueChanged.connect(lambda: self.update())

        container.move(target_pos.x() + slide_offset_x, target_pos.y())

        animation_group = QtCore.QParallelAnimationGroup()
        animation_group.addAnimation(opacity_animation)
        animation_group.addAnimation(position_animation)

        def cleanup():
            try:
                if getattr(container, '_effect_owned', False) and container.graphicsEffect() is effect:
                    container.setGraphicsEffect(None)
                    delattr(container, '_effect_owned')
            except Exception:
                pass
            container.move(target_pos)
            if hasattr(container, '_active_group'):
                delattr(container, '_active_group')
            if hasattr(container, '_target_pos'):
                delattr(container, '_target_pos')

        animation_group.finished.connect(cleanup)
        container._active_group = animation_group
        animation_group.start()

    def _switch_tab(self, index):
        try:
            if hasattr(self, '_current_tab_index') and self._current_tab_index == index:
                return
            self._current_tab_index = index

            self.container_frame.setVisible(False) 
            self.installed_mods_container.setVisible(False) 
            self.settings_container.setVisible(False)
            if self.modrinth_container: 
                self.modrinth_container.setVisible(False) 

            self.information_container.setVisible(False)
            self.moresettings_container.setVisible(False)
            self.plugins_manager_container.setVisible(False)

            self.tab_news_btn.setChecked(index == 0)
            if self.modrinth_plugin_tab_btn:
                self.modrinth_plugin_tab_btn.setChecked(index == MODRINTH_TAB_INDEX)  
            self.tab_installed_mods_btn.setChecked(index == 3)
            self.tab_settings_btn.setChecked(index == 2)

            is_cs2_theme = self.launcher.is_cs2_theme_active

            self.ping_frame.setVisible(index == 0 or is_cs2_theme)
            self.play_btn.setVisible(index == 0 or is_cs2_theme)
            self.online_frame.setVisible(index == 0 or is_cs2_theme)
            self.buttons_block.setVisible(index == 0)

            if is_cs2_theme and index != 0:
                self.bg3d.pause_render()
            elif is_cs2_theme and index == 0:
                self.bg3d.resume_render()


            if self.waitlist:
                self.waitlist.setVisible(index == 0)

            if index == 0: 
                self.container_frame.setVisible(True)
                self._animate_container(self.container_frame)
                
                if not is_cs2_theme:
                    self._animate_container(self.online_frame)
                    self._animate_container(self.ping_frame)
                    self._animate_container(self.play_btn)
                    self._animate_container(self.buttons_block)

                if self.waitlist:
                    self._animate_container(self.waitlist)
                
            elif index == MODRINTH_TAB_INDEX: 
                if self.modrinth_container:
                    self.modrinth_container.setVisible(True)
                    self._animate_container(self.modrinth_container)
                self.modrinth_container.raise_()
            elif index == 3: 
                self.installed_mods_container.setVisible(True)
                self._animate_container(self.installed_mods_container)
                self._populate_installed_mods()
                self.installed_mods_initialized = True
                self.installed_mods_dirty = False
                self.installed_mods_container.raise_()
                self.installed_mods_content.raise_()
            elif index == 2: 
                self.settings_container.setVisible(True)
                self._animate_container(self.settings_container)
                self.settings_container.raise_()
            self.dim_layer.setVisible(index in (1, 2, 3))

            self.container_frame.raise_()                
            
            
            
            self.header_frame.raise_()
        except Exception as e:
            print(e)

    def _get_installed_mods(self):
        installed_items = []

        mods_dir = os.path.join(MC_DIR, "mods")
        if os.path.exists(mods_dir):
            for file in os.listdir(mods_dir):
                if file.endswith('.jar'):
                    full_path = os.path.join(mods_dir, file)
                    mod_info = {
                        "name": file.replace('.jar', ''),
                        "slug": file.replace('.jar', '').split('-')[0].lower().replace('_', '-'),
                        "desc": "Неизвестный мод",
                        "installed": True,
                        "type": "mod",
                        "filename": file
                    }

                    try:
                        with zipfile.ZipFile(full_path, 'r') as z:
                            if 'fabric.mod.json' in z.namelist():
                                with z.open('fabric.mod.json') as f:
                                    data = json.loads(f.read().decode('utf-8'))
                                    mod_info["name"] = data.get("name", mod_info["name"])
                                    mod_info["desc"] = data.get("description", mod_info["desc"])
                                    json_id = data.get("id")
                                    if json_id:  
                                        mod_info["mod_id"] = json_id
                    except Exception as e:
                        print(f"Error reading mod {file}: {e}")

                    mod_data = next((m for m in self.mods_data if m["slug"] == mod_info["slug"]), None)
                    if mod_data:
                        mod_info["desc"] = mod_data.get("desc", mod_info["desc"])

                    mod_info["display_name"] = f"[Mod] {mod_info['name']}"
                    installed_items.append(mod_info)

        shaders_dir = os.path.join(MC_DIR, "shaderpacks")
        if os.path.exists(shaders_dir):
            for file in os.listdir(shaders_dir):
                if file.endswith(('.zip', '.rar')) or os.path.isdir(os.path.join(shaders_dir, file)):
                    slug_guess = file.lower().split('.')[0].replace(' ', '-')
                    shader_info = {
                        "name": file,
                        "slug": slug_guess,
                        "desc": "Шейдер из папки",
                        "installed": True,
                        "type": "shader",
                        "filename": file,
                        "display_name": f"[Shader] {file}"
                    }

                    shader_data = next(
                        (s for s in self.shaders_data if s["slug"] in slug_guess or slug_guess in s["slug"]), None)
                    if shader_data:
                        shader_info["name"] = shader_data["name"]
                        shader_info["display_name"] = f"[Shader] {shader_data['name']}"

                    installed_items.append(shader_info)

        rp_dir = os.path.join(MC_DIR, "resourcepacks")
        if os.path.exists(rp_dir):
            for file in os.listdir(rp_dir):
                if file.endswith('.zip') or os.path.isdir(os.path.join(rp_dir, file)):
                    name_base = file.rsplit('.', 1)[0] if '.' in file else file
                    slug_guess = name_base.lower().replace(' ', '-')
                    rp_info = {
                        "name": name_base,
                        "slug": slug_guess,
                        "desc": "Локальный ресурспак",
                        "installed": True,
                        "type": "resourcepack",
                        "filename": file,
                        "display_name": f"[Resourcepack] {name_base}"
                    }

                    rp_data = next(
                        (r for r in self.resourcepacks_data if r["slug"] in slug_guess or slug_guess in r["slug"]),
                        None)
                    if rp_data:
                        rp_info["name"] = rp_data["name"]
                        rp_info["display_name"] = f"[Resourcepack] {rp_data['name']}"

                    installed_items.append(rp_info)

        installed_items.sort(key=lambda x: x.get("display_name", x["name"]).lower())
        return installed_items

    def _populate_installed_mods(self):
        while self.installed_mods_layout.count():
            item = self.installed_mods_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        installed_items = self._get_installed_mods()

        card_width = (self.installed_mods_container.width() - 40) // 3
        card_height = 180

        for i, item in enumerate(installed_items):
            display_name = item.get("display_name", f"[{item['type'].capitalize()}] {item['name']}")
            slug = item["slug"]
            desc = item.get("desc", "Нет описания")
            item_type = item["type"]

            card = QFrame(self.installed_mods_content)  
            card.setFixedSize(card_width, card_height)
            card.setStyleSheet("QFrame { background-color: #555555; border-radius: 10px; border: none; }")

            layout = QVBoxLayout(card)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(5)

            title = QLabel(display_name)
            title.setStyleSheet("color: white; font-weight: bold;")
            title.setFont(QFont("sans-serif", 12))
            title.setWordWrap(True)  
            title.setFixedHeight(40)
            layout.addWidget(title)

            desc_label = QLabel(desc)
            desc_label.setStyleSheet("color: #dddddd;")
            desc_label.setFont(QFont("sans-serif", 10))
            desc_label.setWordWrap(True)
            desc_label.setFixedHeight(60)  
            layout.addWidget(desc_label)

            btn = QPushButton("Удалить")
            btn.setFixedHeight(30)
            btn.setStyleSheet("""
                QPushButton { background-color: #d32f2f; color: white; border-radius: 5px; border: none; }
                QPushButton:hover { background-color: #b71c1c; }
            """)

            btn.clicked.connect(
                lambda _, s=slug, t=item_type, f=item.get("filename"): self._remove_installed_item(s, t, f))

            layout.addWidget(btn)

            row = i // 3
            col = i % 3  
            self.installed_mods_layout.addWidget(card, row, col)

        self.installed_mods_content.adjustSize()

    def _primary_screen(self):
        from PyQt6.QtWidgets import QApplication
        return QApplication.primaryScreen()

    def _remove_installed_item(self, slug: str, item_type: str, filename: str = None):
        self.installed_mods_dirty = True
        target = filename if filename else slug
        if item_type == "mod":
            self.mod_action.emit(target, "remove")
        elif item_type == "shader":
            self.shader_action.emit(target, "remove")
        elif item_type == "resourcepack":
            self.resourcepack_action.emit(target, "remove")

    @pyqtSlot()
    def refresh_installed_mods_display(self):
        if self.installed_mods_container.isVisible():
            self._populate_installed_mods()
        QtWidgets.QApplication.processEvents()

    def update_ui(self, lang):
        self.lang = lang
        self.tab_news_btn.setText(t(lang, "tabs_home"))
        self.tab_installed_mods_btn.setText(t(lang, "tabs_installed_mods"))
        self.tab_settings_btn.setText(t(lang, "tabs_information"))
  
        self.about_title.setText(t(lang, "about_title"))
        self.reinstall_btn.setToolTip(t(lang, "reinstall_btn_tooltip"))
        self.open_game_directory_btn.setToolTip(t(lang, "directory_title"))
        self.main_label.setText(t(lang, "about_text"))
        self.tech_info_label.setText(f"version: {self.version} by raizor")
        self.scroll_hint.setText(t(lang, "scroll_hint"))
        with open(get_resource_path("scripts/html/about.html" if self.lang == "ru_ru" else "scripts/html/about_en.html"), mode="r", encoding="UTF-8") as f:
            self.info_label.setText(f.read())
        self.back_btn.setText(t(lang, "back_btn"))
        self.information_title.setText(t(lang, "about_title"))


        try:
            self.settings_title.setText(t(lang, "settings_title"))
            self.rpc_label.setText(t(lang, "rpc"))
            self.snow_label.setText(t(lang, "snow_label"))
            self.debug_console_label.setText(t(lang, "debug_console"))
            self.lang_label.setText(t(lang, "lang_label"))
            self.more_settings_title.setText(t(lang, "tabs_information"))
            self.more_settings_back_btn.setText(t(lang, "back_btn"))
            self.plugins_btn.setText(t(lang, "plugins_btn"))
            self.plugins_title_label.setText(t(lang, "plugins_title"))
            self.plugins_back_btn.setText(t(lang, "back_btn"))
        except:  
            pass
        
        self.more_btn.setText(t(lang, "more_btn_text"))
        self.formalities_btn.setText(t(lang, "more_btn_text2"))

        self.more_btn.setText(t(lang, "more_btn_text"))
        self.formalities_btn.setText(t(lang, "more_btn_text2"))
        try:
            self.auth_login_label.setText(t(lang, "login_btn"))
            self.logout_menu_btn.setText(t(lang, "logout_btn"))
        except: pass

        self.reinstall_btn.setToolTip(t(lang, "reinstall_btn_tooltip"))

        self.play_btn.setText(t(lang, "play_button"))

        self.launcher.fetcher.fetch_news_now()
        self.launcher.fetcher.fetch_online_now()

    def set_play_status(self, text):
        self.play_btn.setText(text)

    def set_play_enabled(self, yes: bool):
        self.play_btn.setEnabled(yes)

    def update_online_label(self, text):
        self.online_label.setText(text)

    def update_ping_label(self, text):
        self.ping_label.setText(text)

    def update_online_and_ping_labels(self, online_count: int, ping_text: str):
        if online_count >= 0:
            self.online_label.update_language(self.lang)
            self.online_label.animate_to(online_count)
        else:
            self.online_label.setText(t(self.lang, "online_label_unknown"))

        self.ping_label.setText(ping_text)
        current_stylesheet = self.ping_frame.styleSheet()
        try:
            ping_value = int(float(ping_text.replace(t(self.lang, "ms_locale",), "").strip()))
        except ValueError:
            self.ping_frame.setStyleSheet(current_stylesheet+"background-color: rgba(50,50,50,190);")
            return
        if ping_value < 70:
            color = "rgba(69,168,0,190)"
        elif ping_value < 110:
            color = "rgba(255,204,0,190)"
        else:
            color = "rgba(211,47,47,190)"

        self.ping_frame.setStyleSheet(current_stylesheet+f"background-color:{color};")

    def update_news(self, news_list: list):
        self.news_content.setUpdatesEnabled(False)

        while self.news_layout.count():
            item = self.news_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


        self.news_data = news_list[:50] if len(news_list) > 50 else news_list

        if not news_list:
            news_list = [{
                "title": "Банан съел новости",
                "text": "Не удалось загрузить новости с сервера. Возможно, их съел BananVovan.",
                "date": ":banana: :banana: :черепок:"
            }]

        for news in news_list:
            news_block = QFrame(self.news_content)
            news_block.setStyleSheet("background-color: rgba(50,50,50,160); border-radius:10px;")

            block_layout = QVBoxLayout(news_block)
            block_layout.setContentsMargins(10, 10, 10, 10)

            title = QLabel(news.get("title", "Без заголовка"), news_block)
            title.setStyleSheet("color: white; background: transparent;")
            title.setFont(QFont("sans-serif", 18))
            title.setWordWrap(True)
            title.setFixedWidth(380)
            block_layout.addWidget(title)

            text = QLabel(news.get("text", "Не удалось загрузить новости"), news_block)
            text.setStyleSheet("color: white; background: transparent;")
            text.setFont(QFont("sans-serif", 14))
            text.setWordWrap(True)
            text.setFixedWidth(380)
            block_layout.addWidget(text)
            self.fade_overlay2.raise_()

            if "date" in news:
                date_label = QLabel(news["date"], news_block)
                date_label.setStyleSheet("color:gray; font-style: italic; background: transparent;")
                date_label.setFont(QFont("sans-serif", 10))
                block_layout.addWidget(date_label)

            self.news_layout.addWidget(news_block)

        self.fade_overlay.raise_()
        self.fade_overlay.setGeometry(
            self.news_page.x(),
            self.news_page.y() + self.news_page.height() - 50,
            self.news_page.width(),
            50
        )
        self.fade_overlay.raise_()

        self.fade_overlay2.setGeometry(
            0,
            self.news_page.y(),
            self.container_frame.width(),
            50
        )
        self.fade_overlay2.raise_()


        self.news_content.setUpdatesEnabled(True)

        self.news_content.update()
        self.news_page.viewport().update()
        self.container_frame.update()
        self.repaint()




    def update_shader_status(self, slug, action):
        if slug not in self.shader_buttons: return
        btn = self.shader_buttons[slug]
        installed = action == "install"
        btn.setText(t(self.lang, "btn_del") if installed else t(self.lang, "btn_local"))  
        btn.setStyleSheet(f"""
            QPushButton {{ background-color: {'#d32f2f' if installed else '#45A049'}; color: white; border-radius: 5px; border: none; }}
            QPushButton:hover {{ background-color: {'#b71c1c' if installed else '#3d8b40'}; }}
        """)
        btn.clicked.disconnect()
        btn.clicked.connect(lambda: self.shader_action.emit(slug, "remove" if installed else "install"))
        for item in self.shaders_data:
            if item["slug"] == slug:
                item["installed"] = installed

    def update_resourcepack_status(self, slug, action):
        if slug not in self.resourcepack_buttons: return
        btn = self.resourcepack_buttons[slug]
        installed = action == "install"
        btn.setText(t(self.lang, "btn_del") if installed else t(self.lang, "btn_local"))  
        btn.setStyleSheet(f"""
            QPushButton {{ background-color: {'#d32f2f' if installed else '#45A049'}; color: white; border-radius: 5px; border: none; }}
            QPushButton:hover {{ background-color: {'#b71c1c' if installed else '#3d8b40'}; }}
        """)
        btn.clicked.disconnect()
        btn.clicked.connect(lambda: self.resourcepack_action.emit(slug, "remove" if installed else "install"))
        for item in self.resourcepacks_data:
            if item["slug"] == slug:
                item["installed"] = installed
