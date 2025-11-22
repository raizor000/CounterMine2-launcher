import json
import sys
import urllib.parse
import urllib.request

from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QSize, pyqtSignal, QUrl, QTimer
from PyQt5.QtGui import QDesktopServices, QPixmap, QFont, QCursor, QIcon, QMovie, QColor, QPalette, QLinearGradient, \
    QBrush
from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QFrame, QStackedLayout, QHBoxLayout, \
    QGraphicsDropShadowEffect, QVBoxLayout, QGridLayout, QScrollArea, QLineEdit

from .utilties import *


class LauncherUI(QWidget):
    play_clicked = pyqtSignal()
    reinstall_client = pyqtSignal()
    mod_action = pyqtSignal(str, str)
    reset_settings = pyqtSignal()
    shader_action = pyqtSignal(str, str)
    resourcepack_action = pyqtSignal(str, str)
    settings_changed = pyqtSignal(str, object)


    def __init__(self, version, ip, lang, bg, parent=None):
        super().__init__(parent)
        self.show_faceit = False
        self.pix = None
        self.news_data = []
        self.launcher = parent
        self.version = version
        self.dynamic_bg = bg
        self.ip = ip
        self.lang = lang
        self.current_bg_index = 1
        self.mods_data = []
        self.mod_cards = {}
        self.mod_buttons = {}
        self.mod_labels = {}
        self._toast_widgets = []
        self.shaders_data = []
        self.resourcepacks_data = []
        self.shader_search_edit = QLineEdit()
        self.resourcepack_search_edit = QLineEdit()
        self.shader_cards = {}
        self.shader_buttons = {}
        self.resourcepack_cards = {}
        self.resourcepack_buttons = {}
        self._build_ui()

    def resource_path(self, relative_path):
        # Для петрушки - получаем из ексешки ассеты
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    def _build_ui(self):
        ww = 1024
        wh = 580
        self.setFixedSize(ww, wh)

        self.bg = QLabel(self)
        if self.dynamic_bg:
            self.pix = QPixmap(self.resource_path("assets/background1.png"))
        else:
            self.pix = QPixmap(self.resource_path("assets/background1.png"))
        if not self.pix.isNull():
            self.pix = self.pix.scaled(ww, wh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self.bg.setPixmap(self.pix)
        self.bg.setGeometry(0, 0, ww, wh)

        self.bg_timer = QTimer()
        self.bg_timer.timeout.connect(self.bg_loop)
        self.bg_timer.start(20000)


        self.dim_layer = QFrame(self)
        self.dim_layer.setGeometry(0, 0, ww, wh)
        self.dim_layer.setStyleSheet("background-color: rgba(0, 0, 0, 0.7);")
        self.dim_layer.setVisible(False)   # Для петрушки - по ум. скрыт. Показывается на всех страницах кроме 0 (главной)

        self.search_edit = QLineEdit()
        self.installed_edit = QLineEdit()

        self.header_frame = QFrame(self)
        self.header_frame.setGeometry(0, 0, ww, 40)
        self.header_frame.setStyleSheet("background-color: rgba(50,50,50,200);")

        self.logo = QLabel(self.header_frame)
        self.logo_pix = QPixmap(self.resource_path("assets/logo.png"))
        if not self.logo_pix.isNull():
            self.logo.setPixmap(self.logo_pix)
            self.logo.setScaledContents(True)
        self.logo.setGeometry(10, 8, 168, 24)

        self.logo_separator = QFrame(self.header_frame)
        self.logo_separator.setFrameShape(QFrame.VLine)
        self.logo_separator.setFrameShadow(QFrame.Sunken)
        self.logo_separator.setStyleSheet("background-color: #777;")
        self.logo_separator.setFixedWidth(3)
        self.logo_separator.setFixedHeight(self.logo.height())
        self.logo_separator.move(self.logo.x() + self.logo.width() + 10, self.logo.y())

        self.tab_news_btn = QPushButton("Главная", self.header_frame)
        self.tab_news_btn.setGeometry(200, 5, 100, 30)
        self.tab_news_btn.setStyleSheet(tabs_style)
        self.tab_news_btn.setCheckable(True)
        self.tab_news_btn.setChecked(True)
        self.tab_news_btn.setCursor(QCursor(Qt.PointingHandCursor))

        self.tab_mods_btn = QPushButton("Модпаки", self.header_frame)
        self.tab_mods_btn.setGeometry(310, 5, 100, 30)
        self.tab_mods_btn.setStyleSheet(tabs_style)
        self.tab_mods_btn.setCheckable(True)
        self.tab_mods_btn.setCursor(QCursor(Qt.PointingHandCursor))

        self.tab_installed_mods_btn = QPushButton("Установки", self.header_frame)
        self.tab_installed_mods_btn.setGeometry(420, 5, 100, 30)
        self.tab_installed_mods_btn.setStyleSheet(tabs_style)
        self.tab_installed_mods_btn.setCheckable(True)
        self.tab_installed_mods_btn.setCursor(QCursor(Qt.PointingHandCursor))

        self.tab_settings_btn = QPushButton("Настройки", self.header_frame)
        self.tab_settings_btn.setGeometry(530, 5, 100, 30)
        self.tab_settings_btn.setStyleSheet(tabs_style)
        self.tab_settings_btn.setCheckable(True)
        self.tab_settings_btn.setCursor(QCursor(Qt.PointingHandCursor))

        self.tab_shaders_btn = QPushButton("Шейдеры", self.header_frame)
        self.tab_shaders_btn.setGeometry(648, 5, 100, 30)
        self.tab_shaders_btn.setStyleSheet(tabs_style)
        self.tab_shaders_btn.setCheckable(True)
        self.tab_shaders_btn.setCursor(QCursor(Qt.PointingHandCursor))

        self.tab_resourcepacks_btn = QPushButton("Ресурспаки", self.header_frame)
        self.tab_resourcepacks_btn.setGeometry(755, 5, 100, 30)
        self.tab_resourcepacks_btn.setStyleSheet(tabs_style)
        self.tab_resourcepacks_btn.setCheckable(True)
        self.tab_resourcepacks_btn.setCursor(QCursor(Qt.PointingHandCursor))

        self.separator_moretabs = QFrame(self.header_frame)
        self.separator_moretabs.setFrameShape(QFrame.VLine)
        self.separator_moretabs.setFrameShadow(QFrame.Sunken)
        self.separator_moretabs.setStyleSheet("background-color: #777;")
        self.separator_moretabs.setFixedWidth(3)
        self.separator_moretabs.setFixedHeight(self.logo.height())
        self.separator_moretabs.setGeometry(self.tab_shaders_btn.x() - 12, 8, 2, 24)

        self.close_btn = QPushButton("✕", self.header_frame)
        self.close_btn.setGeometry(ww - 40, 5, 30, 30)
        self.close_btn.setFont(QFont("sans-serif", 11, QFont.Bold))
        self.close_btn.setStyleSheet("""
                    QPushButton { background-color: transparent; color: red; border: none; }
                    QPushButton:hover { color: darkred; }
                """)
        # noinspection PyUnresolvedReferences
        self.close_btn.clicked.connect(sys.exit)
        self.close_btn.raise_()
        self.close_btn.setCursor(QCursor(Qt.PointingHandCursor))

        self.min_btn = QPushButton("—", self.header_frame)
        self.min_btn.setGeometry(ww - 80, 5, 30, 30)
        self.min_btn.setFont(QFont("sans-serif", 11, QFont.Bold))
        self.min_btn.setStyleSheet("""
                    QPushButton { background-color: transparent; color: yellow; border: none; }
                    QPushButton:hover { color: gray; }
                """)
        # noinspection PyUnresolvedReferences
        self.min_btn.clicked.connect(self.launcher.showMinimized)
        self.min_btn.raise_()
        self.min_btn.setCursor(QCursor(Qt.PointingHandCursor))

        self.separator_min = QFrame(self.header_frame)
        self.separator_min.setFrameShape(QFrame.VLine)
        self.separator_min.setFrameShadow(QFrame.Sunken)
        self.separator_min.setStyleSheet("background-color: #777;")
        self.separator_min.setFixedWidth(3)
        self.separator_min.setFixedHeight(self.logo.height())
        self.separator_min.setGeometry(self.min_btn.x() - 12, 8, 2, 24)

        self.container_frame = QFrame(self)
        self.container_frame.setGeometry(20, 60, 420, 300)
        self.container_layout = QStackedLayout(self.container_frame)

        self.news_page = QScrollArea(self.container_frame)
        self.news_page.setWidgetResizable(True)
        self.news_page.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.news_page.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.news_page.setStyleSheet("background-color: transparent; border: none;")


        self.fade_overlay = QFrame(self.container_frame)
        self.fade_overlay.setStyleSheet("""
            background: qlineargradient(
                x1:0, y1:1, x2:0, y2:0,        
                stop:0 rgba(50,50,50,255),     
                stop:1 rgba(50,50,50,0)       
            );
            border: none;
            border-bottom-left-radius: 10px; 
            border-bottom-right-radius: 10px;
        """)
        self.fade_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.fade_overlay.raise_()
        self.fade_overlay.setGeometry(
            self.news_page.x()+10,
            self.news_page.y() + self.news_page.height() - 50,
            self.news_page.width()-10,
            50
        )

        self.fade_overlay2 = QFrame(self.container_frame)
        self.fade_overlay2.setStyleSheet("""
            background: qlineargradient(
                x1:0, y1:0, x2:0, y2:1,
                stop:0 rgba(50,50,50,255),
                stop:1 rgba(50,50,50,0)
            );
            border: none;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
        """)
        self.fade_overlay2.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.fade_overlay2.raise_()

        self.news_content = QWidget(self.news_page)
        self.news_content.setStyleSheet("background-color: transparent;")
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

        mods_content_height = wh - 40
        self.mods_container = QFrame(self)
        self.mods_container.setGeometry(20, 40, ww - 40, mods_content_height)
        self.mods_container.setVisible(False)

        self.installed_mods_container = QFrame(self)
        self.installed_mods_container.setGeometry(20, 40, self.width() - 40, mods_content_height)
        self.installed_mods_container.setVisible(False)
        self.installed_mods_container.setStyleSheet("background-color: transparent;")

        installed_mods_container_layout = QVBoxLayout(self.installed_mods_container)
        installed_mods_container_layout.setContentsMargins(0, 0, 0, 0)
        self.installed_mods_page = QScrollArea(self.installed_mods_container)
        self.installed_mods_page.setWidgetResizable(True)
        self.installed_mods_page.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.installed_mods_page.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.installed_mods_page.setStyleSheet("background-color: transparent; border: none;")
        self.installed_mods_content = QWidget(self.installed_mods_page)
        self.installed_mods_content.setStyleSheet("background-color: transparent;")
        self.installed_mods_layout = QGridLayout(self.installed_mods_content)
        self.installed_mods_layout.setContentsMargins(10, 10, 10, 10)
        self.installed_mods_layout.setSpacing(10)
        self.installed_mods_page.setWidget(self.installed_mods_content)
        installed_mods_container_layout.addWidget(self.installed_mods_page)


        self.shaders_container = QFrame(self)
        self.shaders_container.setGeometry(20, 40, ww - 40, mods_content_height)
        self.shaders_container.setVisible(False)
        self.shaders_container.setStyleSheet("background-color: transparent;")

        shaders_main_layout = QVBoxLayout(self.shaders_container)
        shaders_main_layout.setContentsMargins(0, 0, 0, 0)

        self.shaders_scroll = QScrollArea(self.shaders_container)
        self.shaders_scroll.setWidgetResizable(True)
        self.shaders_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.shaders_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.shaders_scroll.setStyleSheet("background-color: transparent; border: none;")

        self.shaders_content = QWidget(self.shaders_scroll)
        self.shaders_content.setStyleSheet("background-color: transparent;")
        self.shaders_grid = QGridLayout(self.shaders_content)
        self.shaders_grid.setContentsMargins(10, 10, 10, 10)
        self.shaders_grid.setSpacing(10)
        self.shaders_scroll.setWidget(self.shaders_content)
        shaders_main_layout.addWidget(self.shaders_scroll)

        self.resourcepacks_container = QFrame(self)
        self.resourcepacks_container.setGeometry(20, 40, ww - 40, mods_content_height)
        self.resourcepacks_container.setVisible(False)
        self.resourcepacks_container.setStyleSheet("background-color: transparent;")

        rp_main_layout = QVBoxLayout(self.resourcepacks_container)
        rp_main_layout.setContentsMargins(0, 0, 0, 0)

        self.resourcepacks_scroll = QScrollArea(self.resourcepacks_container)
        self.resourcepacks_scroll.setWidgetResizable(True)
        self.resourcepacks_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.resourcepacks_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.resourcepacks_scroll.setStyleSheet("background-color: transparent; border: none;")

        self.resourcepacks_content = QWidget(self.resourcepacks_scroll)
        self.resourcepacks_content.setStyleSheet("background-color: transparent;")
        self.resourcepacks_grid = QGridLayout(self.resourcepacks_content)
        self.resourcepacks_grid.setContentsMargins(10, 10, 10, 10)
        self.resourcepacks_grid.setSpacing(10)
        self.resourcepacks_scroll.setWidget(self.resourcepacks_content)
        rp_main_layout.addWidget(self.resourcepacks_scroll)

        self.settings_container = QFrame(self)
        self.settings_container.setGeometry(20, 40, ww - 40, mods_content_height)
        self.settings_container.setVisible(False)
        self.settings_container.setStyleSheet("background-color: transparent;")

        main_settings_layout = QHBoxLayout(self.settings_container)
        main_settings_layout.setContentsMargins(20, 20, 20, 20)
        main_settings_layout.setSpacing(30)

        try:
            settings_card = self._create_settings_card()
            main_settings_layout.addWidget(settings_card)
            about_card = self._create_about_card()
            main_settings_layout.addWidget(about_card)
            main_settings_layout.addStretch()
            main_settings_layout.addWidget(settings_card)
            main_settings_layout.addStretch()
            main_settings_layout.addWidget(about_card)
            main_settings_layout.addStretch()
        except Exception as e:
            print(e)


        mods_container_layout = QVBoxLayout(self.mods_container)
        mods_container_layout.setContentsMargins(0, 0, 0, 0)
        self.mods_page = QScrollArea(self.mods_container)
        self.mods_page.setWidgetResizable(True)
        self.mods_page.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.mods_page.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.mods_page.setStyleSheet("background-color: transparent; border: none;")
        self.mods_content = QWidget(self.mods_page)
        self.mods_content.setStyleSheet("background-color: transparent;")
        self.mods_layout = QGridLayout(self.mods_content)
        self.mods_layout.setContentsMargins(10, 10, 10, 10)
        self.mods_layout.setSpacing(10)
        self.mods_page.setWidget(self.mods_content)
        mods_container_layout.addWidget(self.mods_page)

        self.mod_cards = {}
        self.mod_buttons = {}
        self.mod_labels = {}

        self._populate_mods([])

        self.moderator_container = QFrame(self)
        self.moderator_container.setGeometry(20, 40, ww - 40, wh - 40)
        self.moderator_container.setVisible(False)
        self.moderator_container.setStyleSheet("background-color: transparent;")
        moderator_layout = QVBoxLayout(self.moderator_container)
        moderator_layout.setContentsMargins(10, 10, 10, 10)
        self.moderator_content = QWidget()
        self.moderator_layout = QVBoxLayout(self.moderator_content)
        moderator_layout.addWidget(self.moderator_content)
        self.container_layout.addWidget(self.moderator_container)

        # Для петрушки - подключаем кнопки переключения вкладок

        # noinspection PyUnresolvedReferences
        self.tab_news_btn.clicked.connect(lambda: self._switch_tab(0))
        # noinspection PyUnresolvedReferences
        self.tab_mods_btn.clicked.connect(lambda: self._switch_tab(1))
        # noinspection PyUnresolvedReferences
        self.tab_settings_btn.clicked.connect(lambda: self._switch_tab(2))
        # noinspection PyUnresolvedReferences
        self.tab_installed_mods_btn.clicked.connect(lambda: self._switch_tab(3))
        # noinspection PyUnresolvedReferences
        self.tab_shaders_btn.clicked.connect(lambda: self._switch_tab(4))
        # noinspection PyUnresolvedReferences
        self.tab_resourcepacks_btn.clicked.connect(lambda: self._switch_tab(5))


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
        self.buttons_block.setStyleSheet("background-color: rgba(50,50,50,200); border-radius:10px; padding:2px;")

        icons = [("telegram.png", "https://t.me/countermine2"),
                 ("youtube.png", "https://www.youtube.com/@CounterMine2"),
                 ("discord.png", "https://discord.com/invite/counter-mine-2-935258545170047006"),
                 ("vkontakte.png", "https://vk.com/countermine"), ("cherrypizza.png", "https://cherry.pizza/")]
        for i, (icon, link) in enumerate(icons):
            btn = QPushButton(self.buttons_block)
            y = 10 + i * (button_size + spacing)
            btn.setGeometry(12, y, button_size, button_size)
            ico = QIcon(self.resource_path("assets/" + icon))
            btn.setIcon(ico)
            btn.setIconSize(QSize(button_size, button_size))
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            # noinspection PyUnresolvedReferences
            btn.clicked.connect(lambda checked=False, url=link: QDesktopServices.openUrl(QUrl(url)))
            btn.setStyleSheet("border:none; background:#323232;")
            btn.setToolTip(str(icon.replace(".png", "")))

        self.reinstall_btn = QPushButton(self.buttons_block)
        self.reinstall_btn.setGeometry(12, block_height - button_size, button_size, button_size)
        self.reinstall_btn.setIcon(QIcon(self.resource_path("assets/reinstall.png")))
        self.reinstall_btn.setIconSize(QSize(button_size, button_size))
        # noinspection PyUnresolvedReferences
        self.reinstall_btn.clicked.connect(lambda: self.reinstall_client.emit())
        self.reinstall_btn.setStyleSheet("border:none; background:#323232;")
        self.reinstall_btn.setToolTip("ПЕРЕУСТАНОВИТЬ КЛИЕНТ")
        self.reinstall_btn.setCursor(QCursor(Qt.PointingHandCursor))

        self.waitlist = QWidget(self)
        self.waitlist.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.waitlist.setStyleSheet("""
            QWidget {
                background-color: rgba(40, 40, 40, 160);
                border-radius: 10px;
                border: 1px rgba(255,255,255,40);
            }
            QLabel {
                color: white;
                font-size: 11pt;
            }
        """)

        main_layout = QVBoxLayout(self.waitlist)
        main_layout.setContentsMargins(15, 10, 15, 10)
        main_layout.setSpacing(5)

        self.faceit_title_label = QLabel("Очередь Faceit")
        self.faceit_title_label.setAlignment(Qt.AlignCenter)
        self.faceit_title_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #f0f0f0;")
        main_layout.addWidget(self.faceit_title_label)

        total_slots = 10
        occupied = 0

        self.queue_label = QLabel(self.get_queue_string(occupied, total_slots))
        self.queue_label.setAlignment(Qt.AlignCenter)
        self.queue_label.setStyleSheet("font-size: 13pt; letter-spacing: -1px;")
        main_layout.addWidget(self.queue_label)

        names_layout = QHBoxLayout()
        names_layout.setSpacing(8)
        names_layout.setContentsMargins(0, 0, 0, 0)

        player_names = []

        names_layout = QHBoxLayout()
        names_layout.setSpacing(8)
        names_layout.setContentsMargins(0, 0, 0, 0)

        names_widget = QWidget()
        names_widget.setLayout(names_layout)
        main_layout.addWidget(names_widget, alignment=Qt.AlignCenter)

        self.names_label = QLabel("\n".join(f"{i + 1}. {name} \n ELO: {elo}" for i, name, elo in enumerate(player_names[:occupied])))
        self.names_label.setAlignment(Qt.AlignLeft)
        self.names_label.setStyleSheet("color: #dddddd; font-size: 10pt;")


        main_layout.addWidget(self.names_label, alignment=Qt.AlignLeft)

        remaining = total_slots - occupied
        word = (
            "игроков" if 5 <= remaining or remaining == 0
            else "игрока" if 2 <= remaining <= 4
            else "игрок"
        )
        self.counter_label = QLabel(f"Осталось {remaining} {word} для начала")
        self.counter_label.setAlignment(Qt.AlignCenter)
        self.counter_label.setStyleSheet("color: #aaaaaa; font-size: 10pt;")
        main_layout.addWidget(self.counter_label)

        self.waitlist.adjustSize()


        header = self.header_frame
        margin = 25
        x = header.width() - self.waitlist.width() - margin - self.buttons_block.width()
        y = self.buttons_block.y()
        self.waitlist.move(x, y)
        self.waitlist.raise_()

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.waitlist.setGraphicsEffect(shadow)

        player_names = get_queue_data()
        occupied = len(player_names)
        self.update_queue(occupied, total_slots)
        self.update_names(occupied, player_names)

        ofw, ofh = 231, 64
        self.online_frame = QFrame(self)
        self.online_frame.setGeometry(28, self.height() - ofh - 10, ofw, ofh)
        self.online_frame.setStyleSheet("background-color:#323232; border-radius:8px;")
        online_layout = QHBoxLayout(self.online_frame)
        online_layout.setContentsMargins(10, 5, 10, 5)
        online_layout.setSpacing(15)


        self.online_gif_label = QLabel(self.online_frame)
        self.static_pixmap = QPixmap(self.resource_path("assets/online_static.png")).scaled(55, 50)
        self.movie = QMovie(self.resource_path("assets/online_animation.gif"))
        self.movie.setScaledSize(QSize(55, 50))

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


        self.online_label = QLabel(t(self.lang, "online_label").format(count="-"), self.online_frame)
        self.online_label.setStyleSheet("color:white; font-weight:bold;")
        self.online_label.setFont(QFont("sans-serif", 11))
        online_layout.addWidget(self.online_label)

        pifw, pifh = 80, 64
        self.ping_frame = QFrame(self)
        self.ping_frame.setGeometry(268, self.height() - pifh - 10, pifw, pifh)
        self.ping_frame.setStyleSheet("background-color:#323232; border-radius:8px;")
        ping_layout = QHBoxLayout(self.ping_frame)
        ping_layout.setContentsMargins(10, 5, 10, 5)
        ping_layout.setSpacing(15)

        self.ping_label = QLabel(f"- {t(self.lang, 'ms_locale')}", self.ping_frame)
        self.ping_label.setStyleSheet("color:white; font-weight:bold;")
        self.ping_label.setAlignment(Qt.AlignCenter)
        self.ping_label.setFont(QFont("sans-serif", 10))
        ping_layout.addWidget(self.ping_label)

        pfw, pfh = 240, ofh

        self.play_frame = QFrame(self)
        self.play_frame.setGeometry(self.width() - pfw - 113, self.height() - pfh - 10, pfw, pfh)
        self.play_frame.setStyleSheet("background-color: rgba(50,50,50,200); border-radius:10px; padding:5px;")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.play_frame.setGraphicsEffect(shadow)
        self.play_btn = QPushButton("Играть", self.play_frame)
        self.play_btn.setGeometry(0, 0, pfw, pfh)
        self.play_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.play_btn.setFont(QFont("sans-serif", 13, QFont.Bold))
        self.play_btn.setStyleSheet("""
            QPushButton { background-color: #45A049; color:white; border-radius:10px; }
            QPushButton:hover:!disabled { background-color: #45a800; }
            QPushButton:disabled { background-color:#2e6b35; color:#aaa; }
        """)
        # noinspection PyUnresolvedReferences
        self.play_btn.clicked.connect(self.play_clicked.emit)
        self.play_frame.raise_()

        self.setup_shaders_search()
        self.setup_resourcepacks_search()

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
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        self.about_title = QLabel("Немного про лаунчер")
        self.about_title.setStyleSheet("color: white; font-weight: bold;")
        self.about_title.setFont(QFont("sans-serif", 16))
        self.about_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.about_title)

        about_main_text = (
            "Лаунчер CounterMine2 - это неофициальный лаунчер проекта CounterMine2. "
            "В лаунчере не было и не будет рекламы, так что проект остается полностью неоплачиваемым.\n\n"
            "Лаунчер разработан игроками raizor, __petryshka__ и furanixx\nПо вопросам вы всегда можете обратиться в:\n"
            "   - Discord: raizor000\n"
            "   - Mail: m4215284@gmail.com\n\n"
            "Примечание: Лаунчер может собирать анонимные данные, по типу характеристик процессора. "
            "Мы не передаем эти данные третьим лицам.\n"
        )
        self.main_label = QLabel(about_main_text)
        self.main_label.setStyleSheet("color: #dddddd; font-size: 12pt;")
        self.main_label.setFont(QFont("sans-serif", 10))
        self.main_label.setWordWrap(True)
        self.main_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        layout.addWidget(self.main_label)

        self.tech_info_label = QLabel(f"version: {self.version} | IP: {'*' * len(self.ip)} (Наведи курсор)")
        self.tech_info_label.setStyleSheet("color: #999999; font-size: 10pt;")
        self.tech_info_label.setFont(QFont("sans-serif", 9))
        self.tech_info_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.tech_info_label.setMouseTracking(True)
        self.tech_info_label.enterEvent = self._on_tech_hover
        self.tech_info_label.leaveEvent = self._on_tech_leave
        layout.addWidget(self.tech_info_label)

        layout.addStretch()
        return card

    def _on_tech_hover(self, event):
        self.tech_info_label.setText(f"version: {self.version} | IP: {self.ip}")
        self.tech_info_label.setStyleSheet("color: #45A049; font-size: 10pt;")

    def _on_tech_leave(self, event):
        self.tech_info_label.setText(f"version: {self.version} | IP: {'*' * len(self.ip)} ({t(self.lang, 'ip_hover_label')})")
        self.tech_info_label.setStyleSheet("color: #999999; font-size: 10pt;")

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

        self.settings_title = QLabel("Настройки")
        self.settings_title.setStyleSheet("color: white; font-weight: bold;")
        self.settings_title.setFont(QFont("sans-serif", 16))
        self.settings_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.settings_title)

        nick_layout = QHBoxLayout()
        self.nick_label = QLabel("Никнейм:")
        self.nick_label.setStyleSheet("color: #dddddd; font-size: 11pt;")
        self.nickname_input = QLineEdit()
        self.nickname_input.setPlaceholderText("Введите никнейм")
        self.nickname_input.setStyleSheet("""
            QLineEdit {
                background-color: #555;
                color: white;
                border-radius: 6px;
                padding: 6px;
                border: none;
            }
            QLineEdit:focus {
                background-color: #666;
            }
        """)
        self.nickname_input.setFixedHeight(32)
        nick_layout.addWidget(self.nick_label)
        nick_layout.addWidget(self.nickname_input, 1)
        layout.addLayout(nick_layout)

        def save_nickname():
            nick = self.nickname_input.text().strip()
            if nick:
                self.settings_changed.emit("nickname", nick)

        self.nickname_input.textChanged.connect(save_nickname)

        sound_layout = QHBoxLayout()
        self.sound_label = QLabel("Звук при входе/выходе из очереди Faceit")
        self.sound_label.setStyleSheet("color: #dddddd; font-size: 11pt;")
        self.sound_switch = SwitchButton()
        self.sound_switch.setFixedSize(52, 28)
        sound_layout.addWidget(self.sound_label)
        sound_layout.addStretch()
        sound_layout.addWidget(self.sound_switch)
        layout.addLayout(sound_layout)

        hide_faceit_layout = QHBoxLayout()
        self.hide_faceit_label = QLabel("Показывать очередь Faceit")
        self.hide_faceit_label.setStyleSheet("color: #dddddd; font-size: 11pt;")
        self.hide_faceit_switch = SwitchButton()
        self.hide_faceit_switch.setFixedSize(52, 28)
        hide_faceit_layout.addWidget(self.hide_faceit_label)
        hide_faceit_layout.addStretch()
        hide_faceit_layout.addWidget(self.hide_faceit_switch)
        layout.addLayout(hide_faceit_layout)

        update_layout = QHBoxLayout()
        self.update_label = QLabel("Проверять наличие обновлений")
        self.update_label.setStyleSheet("color: #dddddd; font-size: 11pt;")
        self.update_switch = SwitchButton()
        self.update_switch.setFixedSize(52, 28)
        update_layout.addWidget(self.update_label)
        update_layout.addStretch()
        update_layout.addWidget(self.update_switch)
        layout.addLayout(update_layout)

        rpc_layout = QHBoxLayout()
        self.rpc_label = QLabel("Устанавливать статус в Discord")
        self.rpc_label.setStyleSheet("color: #dddddd; font-size: 11pt;")
        self.rpc_switch = SwitchButton()
        self.rpc_switch.setFixedSize(52, 28)
        rpc_layout.addWidget(self.rpc_label)
        rpc_layout.addStretch()
        rpc_layout.addWidget(self.rpc_switch)
        layout.addLayout(rpc_layout)


        lang_layout = QHBoxLayout()
        self.lang_label = QLabel("Язык / Language")
        self.lang_label.setStyleSheet("color: #dddddd; font-size: 11pt;")
        self.lang_dropdown = DropDown(["Русский", "English"])
        lang_layout.setContentsMargins(0, 8, 0, 8)
        lang_layout.setSpacing(10)
        lang_layout.addWidget(self.lang_label)
        lang_layout.addStretch()
        lang_layout.addWidget(self.lang_dropdown)
        layout.addLayout(lang_layout)

        moretabs_layout = QHBoxLayout()
        self.moretabs_label = QLabel("Расширеный режим интерфейса")
        self.moretabs_label.setStyleSheet("color: #dddddd; font-size: 11pt;")
        self.moretabs_switch = SwitchButton()
        self.moretabs_switch.setFixedSize(52, 28)
        moretabs_layout.addWidget(self.moretabs_label)
        moretabs_layout.addStretch()
        moretabs_layout.addWidget(self.moretabs_switch)
        layout.addLayout(moretabs_layout)

        # Для петрушки - подключаем все сигналы кнопок и переключателей настроек.
        # Для петрушки - Сигналы используем для того чтобы передавать данные между потоками
        try:
            self.moretabs_switch.stateChanged.connect(
                lambda checked: self.settings_changed.emit("moretabs", checked)
            )
        except Exception as e:
            print(e)

        try:
            self.lang_dropdown.valueChanged.connect(
                lambda checked: self.settings_changed.emit("lang", checked)
            )
        except Exception as e:
            print(e)

        try:
            self.sound_switch.stateChanged.connect(
                lambda checked: self.settings_changed.emit("sound_enabled", checked)
            )
        except Exception as e:
            print(e)

        try:
            self.hide_faceit_switch.stateChanged.connect(
                lambda checked: self.settings_changed.emit("hide_faceit", checked)
            )
        except Exception as e:
            print(e)

        try:
            self.hide_faceit_switch.stateChanged.connect(
                lambda checked: self.settings_changed.emit("hide_faceit", checked)
            )
        except Exception as e:
            print(e)

        try:
            self.update_switch.stateChanged.connect(
                lambda checked: self.settings_changed.emit("update", checked)
            )
        except Exception as e:
            print(e)

        try:
            self.rpc_switch.stateChanged.connect(
                lambda checked: self.settings_changed.emit("rpc", checked)
            )
        except Exception as e:
            print(e)

        layout.addStretch()
        return card

    def update_names(self, occ, names):
        text = "\n".join(f"{i + 1}. {name}\n 🏆ELO: {elo}" for i, (name, elo) in enumerate(names[:occ]))
        self.names_label.setText(text)
        self.waitlist.adjustSize()

    def get_queue_string(self, occupied, total):
        return "🟢" * occupied + "⚪" * (total - occupied)

    def update_queue(self, occupied, total_slots):
        self.queue_label.setText(self.get_queue_string(occupied, total_slots))
        remaining = total_slots - occupied
        word = (
            "игроков" if 5 <= remaining or remaining == 0
            else "игрока" if 2 <= remaining <= 4
            else "игрок"
        )
        self.counter_label.setText(f"Осталось {remaining} {word} для начала")

    def _switch_tab(self, index):
        try:
            self.container_frame.setVisible(index == 0)
            self.mods_container.setVisible(index == 1)
            self.settings_container.setVisible(index == 2)
            self.installed_mods_container.setVisible(index == 3)
            self.moderator_container.setVisible(index == 4)
            self.tab_news_btn.setChecked(index == 0)
            self.tab_mods_btn.setChecked(index == 1)
            self.tab_settings_btn.setChecked(index == 2)
            self.tab_installed_mods_btn.setChecked(index == 3)
            self.tab_shaders_btn.setChecked(index == 4)
            self.tab_resourcepacks_btn.setChecked(index == 5)
            self.ping_frame.setVisible(index == 0)
            self.play_frame.setVisible(index == 0)
            self.online_frame.setVisible(index == 0)
            if index == 0 and self.show_faceit == True:
                self.waitlist.setVisible(True)
            else:
                self.waitlist.setVisible(False)
            self.buttons_block.setVisible(index == 0)
            for toast in self._toast_widgets:
                toast.setVisible(index == 0)
            self.dim_layer.setVisible(index in (1, 2, 3, 4, 5))
            self.shaders_container.setVisible(index == 4)
            self.resourcepacks_container.setVisible(index == 5)
            self.container_frame.raise_()
            if index == 0:
                self.news_page.raise_()
                self.fade_overlay.raise_()
            elif index == 3:
                self._populate_installed_mods()

        except Exception as e:
            print(e)

    def _get_installed_mods(self):
        # Для петрушки - метод не смотря на свое название сканирует не только моды а еще ресурспаки и шейдеры
        installed_items = []

        mods_dir = os.path.join(MC_DIR, "mods")
        if os.path.exists(mods_dir):
            for file in os.listdir(mods_dir):
                if file.endswith('.jar'):
                    base_name = file.replace('.jar', '')
                    slug_guess = base_name.split('-')[0].lower().replace('_', '-')
                    mod_data = next((m for m in self.mods_data if m["slug"] == slug_guess), None)
                    if mod_data:
                        item = mod_data.copy()
                        item["type"] = "mod"
                        item["installed"] = True
                        installed_items.append(item)
                    else:
                        installed_items.append({
                            "name": base_name.replace('-', ' '),
                            "slug": slug_guess,
                            "desc": "Неизвестный мод",
                            "installed": True,
                            "type": "mod",
                            "display_name": f"[Mod] {base_name.replace('-', ' ')}"
                        })

        shaders_dir = os.path.join(MC_DIR, "shaderpacks")
        if os.path.exists(shaders_dir):
            for file in os.listdir(shaders_dir):
                if file.endswith(('.zip', '.rar')) or os.path.isdir(os.path.join(shaders_dir, file)):
                    name = file
                    if os.path.isdir(os.path.join(shaders_dir, file)):
                        name = file
                    slug_guess = file.lower().split('.')[0].replace(' ', '-')
                    shader_data = next(
                        (s for s in self.shaders_data if s["slug"] in slug_guess or slug_guess in s["slug"]), None)
                    if shader_data:
                        item = shader_data.copy()
                        item["type"] = "shader"
                        item["installed"] = True
                        item["display_name"] = f"[Shader] {shader_data['name']}"
                        installed_items.append(item)
                    else:
                        installed_items.append({
                            "name": name,
                            "slug": slug_guess,
                            "desc": "Шейдер из папки",
                            "installed": True,
                            "type": "shader",
                            "display_name": f"[Shader] {name}"
                        })

        rp_dir = os.path.join(MC_DIR, "resourcepacks")
        if os.path.exists(rp_dir):
            for file in os.listdir(rp_dir):
                if file.endswith('.zip') or os.path.isdir(os.path.join(rp_dir, file)):
                    name = file.rsplit('.', 1)[0] if '.' in file else file
                    slug_guess = name.lower().replace(' ', '-')
                    rp_data = next(
                        (r for r in self.resourcepacks_data if r["slug"] in slug_guess or slug_guess in r["slug"]),
                        None)
                    if rp_data:
                        item = rp_data.copy()
                        item["type"] = "resourcepack"
                        item["installed"] = True
                        item["display_name"] = f"[Resourcepack] {rp_data['name']}"
                        installed_items.append(item)
                    else:
                        installed_items.append({
                            "name": name,
                            "slug": slug_guess,
                            "desc": "Локальный ресурспак",
                            "installed": True,
                            "type": "resourcepack",
                            "display_name": f"[Resourcepack] {name}"
                        })

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

            btn.clicked.connect(lambda _, s=slug, t=item_type: self._remove_installed_item(s, t))

            layout.addWidget(btn)

            row = i // 3
            col = i % 3
            self.installed_mods_layout.addWidget(card, row, col)

        self.installed_mods_content.adjustSize()

    def _primary_screen(self):
        from PyQt5.QtWidgets import QApplication
        return QApplication.primaryScreen()

    def _remove_installed_item(self, slug: str, item_type: str):
        if item_type == "mod":
            self.mod_action.emit(slug, "remove")
        elif item_type == "shader":
            self.shader_action.emit(slug, "remove")
        elif item_type == "resourcepack":
            self.resourcepack_action.emit(slug, "remove")

    def bg_loop(self):
        if self.dynamic_bg:
            self.pix = QPixmap(self.resource_path(f"assets/background{self.current_bg_index}.png"))
            if self.current_bg_index == 13:
                self.current_bg_index = 1
            else:
                self.current_bg_index += 1
        else:
            self.pix = QPixmap(self.resource_path(f"assets/background.png"))

        if not self.pix.isNull():
            self.pix = self.pix.scaled(1024, 580, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self.bg.setPixmap(self.pix)

        self.bg.setGeometry(0, 0, 1024, 580)


    def update_ui(self, lang, bg, moretabs):
        self.lang = lang
        self.dynamic_bg = bool(bg)
        self.bg_loop()
        self.tab_news_btn.setText(t(lang, "tabs_home"))
        self.tab_mods_btn.setText(t(lang, "tabs_mods"))
        self.tab_installed_mods_btn.setText(t(lang, "tabs_installed_mods"))
        self.tab_settings_btn.setText(t(lang, "tabs_information"))

        self.faceit_title_label.setText(t(lang, "faceit_title"))

        if not moretabs:
            self.tab_resourcepacks_btn.hide()
            self.tab_shaders_btn.hide()
        else:
            self.tab_resourcepacks_btn.show()
            self.tab_shaders_btn.show()

        self.about_title.setText(t(lang, "about_title"))
        self.main_label.setText(t(lang, "about_text"))
        self.tech_info_label.setText(f"version: {self.version} | IP: {'*' * len(self.ip)} ({t(lang, 'ip_hover_label')})")

        self.settings_title.setText(t(lang, "settings_title"))
        self.nick_label.setText(t(lang, "nick_label"))
        self.nickname_input.setPlaceholderText(t(lang, "nick_placeholder"))
        self.sound_label.setText(t(lang, "faceit_sound"))
        self.update_label.setText(t(lang, "updates"))
        self.rpc_label.setText(t(lang, "rpc"))

        self.search_edit.setPlaceholderText(t(lang, "mod_search"))
        self.installed_edit.setPlaceholderText(t(lang, "installed_mods_text"))

        self.reinstall_btn.setToolTip(t(lang, "reinstall_btn_tooltip"))

        self.play_btn.setText(t(lang, "play_button"))
        self.moretabs_switch.setChecked(bool(moretabs))

        self.hide_faceit_label.setText(t(lang, "hidef"))



    def set_play_status(self, text):
        self.play_btn.setText(text)

    def set_play_enabled(self, yes: bool):
        self.play_btn.setEnabled(yes)

    def update_online_label(self, text):
        self.online_label.setText(text)

    def update_ping_label(self, text):
        self.ping_label.setText(text)

    def update_online_and_ping_labels(self, text: str, ping_text: str):
        self.online_label.setText(text)
        self.ping_label.setText(ping_text)
        try:
            ping_value = int(float(ping_text.replace(t(self.lang, "ms_locale"), "").strip()))
        except ValueError:
            self.ping_frame.setStyleSheet("background-color:#323232; border-radius:8px;")
            return
        if ping_value < 65:
            color = "#45a800"
        elif ping_value < 100:
            color = "#FFCC00"
        else:
            color = "#d32f2f"

        self.ping_frame.setStyleSheet(f"background-color:{color}; border-radius:8px;")

    def update_news(self, news_list: list):
        while self.news_layout.count():
            item = self.news_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.news_data = news_list

        for news in news_list:
            news_block = QFrame(self.news_content)
            news_block.setStyleSheet("background-color: rgba(50,50,50,200); border-radius:10px;")

            block_layout = QVBoxLayout(news_block)
            block_layout.setContentsMargins(10, 10, 10, 10)

            title = QLabel(news.get("title", "Без заголовка"), news_block)
            title.setStyleSheet("color:white;")
            title.setFont(QFont("sans-serif", 18))
            title.setWordWrap(True)
            title.setFixedWidth(380)
            block_layout.addWidget(title)

            text = QLabel(news.get("text", ""), news_block)
            text.setStyleSheet("color:white;")
            text.setFont(QFont("sans-serif", 14))
            text.setWordWrap(True)
            text.setFixedWidth(380)
            block_layout.addWidget(text)

            if "date" in news:
                date_label = QLabel(news["date"], news_block)
                date_label.setStyleSheet("color:gray; font-style: italic;")
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

    def setup_mods_search(self):
        search_widget = QWidget()
        search_layout = QHBoxLayout(search_widget)
        search_layout.setContentsMargins(10, 10, 10, 10)

        self.search_edit.setPlaceholderText("Поиск модов на Modrinth...")
        self.search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #555;
                color: white;
                border-radius: 5px;
                padding: 8px;
                border: none;
            }
            QLineEdit:focus {
                background-color: #666;
            }
        """)
        search_layout.addWidget(self.search_edit)
        mods_container_layout = self.mods_container.layout()
        if mods_container_layout is None:
            mods_container_layout = QVBoxLayout(self.mods_container)
            self.mods_container.setLayout(mods_container_layout)

        mods_container_layout.insertWidget(0, search_widget)
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)
        self.search_edit.textChanged.connect(lambda text: self.search_timer.start(250))

        self.search_timer.start(50)   # Для петрушки - сразу грузим популярные моды

    def setup_mods_label(self):
        installed_widget = QWidget()
        installed_layout = QHBoxLayout(installed_widget)
        installed_layout.setContentsMargins(10, 10, 10, 10)

        self.installed_edit.setPlaceholderText(t(self.lang, "installed_mods_text"))
        self.installed_edit.setStyleSheet("""
            QLineEdit {
                background-color: #555;
                color: white;
                border-radius: 5px;
                padding: 8px;
                border: none;
            }
            QLineEdit:focus {
                background-color: #666;
            }
        """)
        self.installed_edit.setEnabled(False)
        installed_layout.addWidget(self.installed_edit)
        installed_mods_container_layout = self.installed_mods_container.layout()
        if installed_mods_container_layout is None:
            installed_mods_container_layout = QVBoxLayout(self.installed_mods_container)
            self.installed_mods_container.setLayout(installed_mods_container_layout)

        installed_mods_container_layout.insertWidget(0, installed_widget )


    def _perform_search(self):
        query = self.search_edit.text().strip()
        index = "downloads" if not query else "relevance"
        self._fetch_mods(query, index)

    def _fetch_mods(self, query, index="relevance"):
        try:
            facets_str = f'[["project_type:mod"],["categories:fabric"],["versions:{VERSION}"]]'
            url = f"https://api.modrinth.com/v2/search?query={urllib.parse.quote(query)}&facets={urllib.parse.quote(facets_str)}&limit=54&index={index}"

            banned_mods = ["Entity Culling", "Xaero's Minimap"]

            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read().decode('utf-8'))
                hits = data['hits']
                mods_data = []
                for hit in hits:
                    if hit['title'] not in banned_mods and "Xaero's" not in hit['title'] and "Xaero" not in hit['title']:
                        installed = self._is_mod_installed(hit['slug'])
                        mods_data.append({
                            "name": hit['title'],
                            "slug": hit['slug'],
                            "desc": hit['description'][:150] + '...' if len(hit['description']) > 150 else hit[
                                'description'],
                            "installed": installed,
                            "project_id": hit['project_id']
                        })
                self.mods_data = mods_data
                self._clear_mods()
                self._populate_mods(self.mods_data)
        except Exception as e:
            print(e)

    def _is_mod_installed(self, slug: str) -> bool:
        return is_mod_installed(str(MC_DIR), slug)

    def _clear_mods(self):
        while self.mods_layout.count():
            item = self.mods_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.mod_cards.clear()
        self.mod_buttons.clear()
        self.mod_labels.clear()
        self.mods_content.adjustSize()

    def _populate_mods(self, mods_data):
        self._clear_mods()
        card_width = (self.mods_container.width() - 40) // 3
        card_height = 150

        for i, mod in enumerate(mods_data):
            name = mod["name"]
            slug = mod["slug"]
            desc = mod["desc"]
            installed = self._is_mod_installed(slug)
            mod["installed"] = installed

            card = QFrame(self.mods_content)
            card.setFixedSize(card_width, card_height)
            card.setStyleSheet("""
                QFrame {
                    background-color: #555555;  /* Непрозрачный фон */
                    border-radius: 10px;  /* Скругленные края */
                    border: none;
                }
            """)

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 10, 10, 10)
            card_layout.setSpacing(5)

            title_label = QLabel(name, card)
            title_label.setStyleSheet("color: white; font-weight: bold;")
            title_label.setFont(QFont("sans-serif", 12))
            title_label.setWordWrap(True)
            title_label.setFixedHeight(40)
            title_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            card_layout.addWidget(title_label)

            desc_label = QLabel(desc, card)
            desc_label.setStyleSheet("color: #dddddd;")
            desc_label.setFont(QFont("sans-serif", 10))
            desc_label.setWordWrap(True)
            desc_label.setFixedHeight(60)
            desc_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
            card_layout.addWidget(desc_label)

            button_text = (t(self.lang, "btn_del") if installed else t(self.lang, "btn_local"))
            bg_color = "#d32f2f" if installed else "#45A049"
            hover_color = "#b71c1c" if installed else "#3d8b40"
            button = QPushButton(button_text, card)
            button.setFixedHeight(30)
            button.setStyleSheet(f"""
                            QPushButton {{
                                background-color: {bg_color};
                                color: white;
                                border-radius: 5px;
                                border: none;
                            }}
                            QPushButton:hover {{
                                background-color: {hover_color};
                            }}
                        """)
            # noinspection PyUnresolvedReferences
            action = "remove" if installed else "install"
            button.clicked.connect(lambda checked, s=slug, a=action: self.mod_action.emit(s, a))
            card_layout.addWidget(button)

            self.mod_cards[slug] = card
            self.mod_buttons[slug] = button
            self.mod_labels[slug] = (title_label, desc_label)

            row = i // 3
            col = i % 3
            self.mods_layout.addWidget(card, row, col)

        self.mods_content.adjustSize()

    def update_mod_status(self, mod_slug: str, action: str):
        print(f"Обновление статуса мода: {mod_slug}, действие={action}")

        if action in ("install", "remove"):
            if mod_slug in self.mod_buttons:
                button = self.mod_buttons[mod_slug]
                button.setEnabled(True)
                button.setText(t(self.lang, "btn_del") if action == "install" else t(self.lang, "btn_local"))
                button.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {"#d32f2f" if action == "install" else "#45A049"};
                        color: white;
                        border-radius: 5px;
                        border: none;
                    }}
                    QPushButton:hover {{
                        background-color: {"#b71c1c" if action == "install" else "#3d8b40"};
                    }}
                    QPushButton:disabled {{
                        background-color: #333;
                        color: #aaa;
                    }}
                """)
                action_signal = "remove" if action == "install" else "install"
                button.disconnect()
                button.clicked.connect(lambda checked, s=mod_slug, a=action_signal: self.mod_action.emit(s, a))
                button.setEnabled(True)
                for mod in self.mods_data:
                    if mod["slug"] == mod_slug:
                        mod["installed"] = (action == "install")
                        break

        if self.installed_mods_container.isVisible():
            self._populate_installed_mods()
        QtWidgets.QApplication.processEvents()


    def setup_shaders_search(self):
        search_widget = QWidget()
        search_layout = QHBoxLayout(search_widget)
        search_layout.setContentsMargins(10, 10, 10, 10)

        self.shader_search_edit.setPlaceholderText("Поиск шейдеров на Modrinth...")
        self.shader_search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #555;
                color: white;
                border-radius: 5px;
                padding: 8px;
                border: none;
            }
            QLineEdit:focus {
                background-color: #666;
            }
        """)
        search_layout.addWidget(self.shader_search_edit)
        self.shaders_container.layout().insertWidget(0, search_widget)

        self.shader_timer = QTimer()
        self.shader_timer.setSingleShot(True)
        self.shader_timer.timeout.connect(self._perform_shader_search)
        self.shader_search_edit.textChanged.connect(lambda: self.shader_timer.start(250))
        self.shader_timer.start(50)  # Для петрушки - сразу грузим популярные шейдеры

    def setup_resourcepacks_search(self):
        search_widget = QWidget()
        search_layout = QHBoxLayout(search_widget)
        search_layout.setContentsMargins(10, 10, 10, 10)

        self.resourcepack_search_edit.setPlaceholderText("Поиск ресурспаков на Modrinth...")
        self.resourcepack_search_edit.setStyleSheet("""
            QLineEdit {
                background-color: #555;
                color: white;
                border-radius: 5px;
                padding: 8px;
                border: none;
            }
            QLineEdit:focus {
                background-color: #666;
            }
        """)
        search_layout.addWidget(self.resourcepack_search_edit)
        self.resourcepacks_container.layout().insertWidget(0, search_widget)

        self.rp_timer = QTimer()
        self.rp_timer.setSingleShot(True)
        self.rp_timer.timeout.connect(self._perform_resourcepack_search)
        self.resourcepack_search_edit.textChanged.connect(lambda: self.rp_timer.start(250))
        self.rp_timer.start(50)

    def _perform_shader_search(self):
        query = self.shader_search_edit.text().strip()
        index = "downloads" if not query else "relevance"
        self._fetch_shaders(query, index)

    def _perform_resourcepack_search(self):
        query = self.resourcepack_search_edit.text().strip()
        index = "downloads" if not query else "relevance"
        self._fetch_resourcepacks(query, index)

    def _fetch_shaders(self, query="", index="relevance"):
        facets_json = [
            ["project_type:shader"],
            ["categories:iris"],        # Для петрушки - работаем только с шейдерами под Iris
            [f"versions:{VERSION}"]
        ]
        facets_str = json.dumps(facets_json)
        url = f"https://api.modrinth.com/v2/search?query={urllib.parse.quote(query)}&facets={urllib.parse.quote(facets_str)}&limit=54&index={index}"
        try:
            with urllib.request.urlopen(url) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                self.shaders_data = []
                for hit in data.get("hits", []):
                    installed = self._is_shader_installed(hit["slug"])
                    desc = hit["description"][:147] + "..." if len(hit["description"]) > 150 else hit["description"]
                    self.shaders_data.append({
                        "name": hit["title"],
                        "slug": hit["slug"],
                        "desc": desc,
                        "installed": installed,
                        "project_id": hit["project_id"]
                    })
                self._populate_shaders()
        except urllib.error.HTTPError as e:
            print(f"Shader HTTP error: {e.code} - {e.reason}. URL was: {url}")
        except Exception as e:
            print("Shader fetch error:", e)

    def _fetch_resourcepacks(self, query="", index="relevance"):
        facets_json = [
            ["project_type:resourcepack"],
            [f"versions:{VERSION}"]
        ]
        facets_str = json.dumps(facets_json)
        url = f"https://api.modrinth.com/v2/search?query={urllib.parse.quote(query)}&facets={urllib.parse.quote(facets_str)}&limit=54&index={index}"
        try:
            with urllib.request.urlopen(url) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                self.resourcepacks_data = []
                for hit in data.get("hits", []):
                    if "xray" not in hit["title"] and "Xray" not in hit["title"]:
                        installed = self._is_resourcepack_installed(hit["slug"])
                        desc = hit["description"][:147] + "..." if len(hit["description"]) > 150 else hit["description"]
                        self.resourcepacks_data.append({
                            "name": hit["title"],
                            "slug": hit["slug"],
                            "desc": desc,
                            "installed": installed,
                            "project_id": hit["project_id"]
                        })
                self._populate_resourcepacks()
        except urllib.error.HTTPError as e:
            print(f"RP HTTP error: {e.code} - {e.reason}. URL was: {url}")
        except Exception as e:
            print("RP fetch error:", e)

    def _clear_shaders(self):
        while self.shaders_grid.count():
            child = self.shaders_grid.takeAt(0).widget()
            if child:
                child.deleteLater()
        self.shader_cards.clear()
        self.shader_buttons.clear()

    def _clear_resourcepacks(self):
        while self.resourcepacks_grid.count():
            child = self.resourcepacks_grid.takeAt(0).widget()
            if child:
                child.deleteLater()
        self.resourcepack_cards.clear()
        self.resourcepack_buttons.clear()

    def _populate_shaders(self):
        self._clear_shaders()
        card_w = (self.shaders_container.width() - 40) // 3
        for i, item in enumerate(self.shaders_data):
            card = QFrame(self.shaders_content)
            card.setFixedSize(card_w, 150)
            card.setStyleSheet("QFrame { background-color: #555555; border-radius: 10px; border: none; }")

            layout = QVBoxLayout(card)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(5)

            title = QLabel(item["name"])
            title.setStyleSheet("color: white; font-weight: bold;")
            title.setFont(QFont("sans-serif", 12))
            title.setWordWrap(True)
            layout.addWidget(title)

            desc = QLabel(item["desc"])
            desc.setStyleSheet("color: #dddddd;")
            desc.setFont(QFont("sans-serif", 10))
            desc.setWordWrap(True)
            layout.addWidget(desc)

            btn_text = t(self.lang, "btn_del") if item["installed"] else t(self.lang, "btn_local")
            color = "#d32f2f" if item["installed"] else "#45A049"
            hover = "#b71c1c" if item["installed"] else "#3d8b40"

            btn = QPushButton(btn_text)
            btn.setFixedHeight(30)
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: {color}; color: white; border-radius: 5px; border: none; }}
                QPushButton:hover {{ background-color: {hover}; }}
            """)
            action = "remove" if item["installed"] else "install"
            btn.clicked.connect(lambda _, s=item["slug"], a=action: self.shader_action.emit(s, a))

            layout.addWidget(btn)

            self.shader_cards[item["slug"]] = card

            self.shader_buttons[item["slug"]] = btn

            self.shaders_grid.addWidget(card, i // 3, i % 3)

        self.shaders_content.adjustSize()

    def _populate_resourcepacks(self):
        self._clear_resourcepacks()
        card_w = (self.resourcepacks_container.width() - 40) // 3
        for i, item in enumerate(self.resourcepacks_data):
            card = QFrame(self.resourcepacks_content)
            card.setFixedSize(card_w, 150)
            card.setStyleSheet("QFrame { background-color: #555555; border-radius: 10px; border: none; }")

            layout = QVBoxLayout(card)
            layout.setContentsMargins(10, 10, 10, 10)

            title = QLabel(item["name"])
            title.setStyleSheet("color: white; font-weight: bold; font-size: 12pt;")
            title.setWordWrap(True)
            layout.addWidget(title)

            desc = QLabel(item["desc"])
            desc.setStyleSheet("color: #dddddd; font-size: 10pt;")
            desc.setWordWrap(True)
            layout.addWidget(desc)

            btn_text = t(self.lang, "btn_del") if item["installed"] else t(self.lang, "btn_local")
            color = "#d32f2f" if item["installed"] else "#45A049"
            hover = "#b71c1c" if item["installed"] else "#3d8b40"

            btn = QPushButton(btn_text)
            btn.setFixedHeight(30)
            btn.setStyleSheet(f"""
                QPushButton {{ background-color: {color}; color: white; border-radius: 5px; border: none; }}
                QPushButton:hover {{ background-color: {hover}; }}
            """)
            action = "remove" if item["installed"] else "install"
            btn.clicked.connect(lambda _, s=item["slug"], a=action: self.resourcepack_action.emit(s, a))

            layout.addWidget(btn)

            self.resourcepack_cards[item["slug"]] = card

            self.resourcepack_buttons[item["slug"]] = btn

            self.resourcepacks_grid.addWidget(card, i // 3, i % 3)

        self.resourcepacks_content.adjustSize()

    # проверка установки
    def _is_shader_installed(self, slug):
        dir_path = os.path.join(MC_DIR, "shaderpacks")
        if not os.path.exists(dir_path): return False
        return any(slug.lower() in f.lower() for f in os.listdir(dir_path))

    def _is_resourcepack_installed(self, slug):
        dir_path = os.path.join(MC_DIR, "resourcepacks")
        if not os.path.exists(dir_path): return False
        return any(slug.lower() in f.lower() for f in os.listdir(dir_path))

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
