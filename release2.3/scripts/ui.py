from threading import Thread
import json
import sys
import urllib.parse, urllib.request

# from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
# from PyQt6.QtWebEngineWidgets import QWebEngineView

from .utilties import *
from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QDesktopServices, QPixmap, QFont, QCursor, QIcon, QMovie, QColor
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QFrame, QStackedLayout, QHBoxLayout, \
    QGraphicsDropShadowEffect, QVBoxLayout, QGridLayout, QScrollArea, QLineEdit, QComboBox, QCheckBox


class LauncherUI(QWidget):
    _mods_search_finished = pyqtSignal(object)
    play_clicked = pyqtSignal()
    reinstall_client = pyqtSignal()
    mod_action = pyqtSignal(str, str)
    reset_settings = pyqtSignal()

    def __init__(self, version, ip, parent=None):
        super().__init__(parent)
        self._mods_loading = False
        self._mods_pending_url = None
        self._mods_search_finished.connect(self._apply_mods_search)
        self.news_data = []
        self.launcher = parent
        self.version = version
        self.ip = ip
        self._active_toasts = 0  # Счетчик активных тостов
        self.mods_data = []
        self.mod_cards = {}
        self.mod_buttons = {}
        self.mod_labels = {}
        self._toast_widgets = []
        self.discord_id = None
        self.moderators = []
        self.prepared = False
        self._build_ui()

    def resource_path(self, relative_path):
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    def _build_ui(self):
        ww = 1024
        wh = 580
        self.setFixedSize(ww, wh)

        bg = QLabel(self)
        pix = QPixmap(self.resource_path("assets/background.png"))
        if not pix.isNull():
            pix = pix.scaled(ww, wh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            bg.setPixmap(pix)
        bg.setGeometry(0, 0, ww, wh)

        self.dim_layer = QFrame(self)
        self.dim_layer.setGeometry(0, 0, ww, wh)
        self.dim_layer.setStyleSheet("background-color: rgba(0, 0, 0, 0.6);")
        self.dim_layer.setVisible(False)  # По умолчанию скрыт

        self.search_edit = QLineEdit()

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
        self.logo_separator.setFrameShape(QFrame.Shape.VLine)
        self.logo_separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.logo_separator.setStyleSheet("background-color: #777;")
        self.logo_separator.setFixedWidth(3)
        self.logo_separator.setFixedHeight(self.logo.height())
        self.logo_separator.move(self.logo.x() + self.logo.width() + 10, self.logo.y())

        self.tab_news_btn = QPushButton("Главная", self.header_frame)
        self.tab_news_btn.setGeometry(200, 5, 100, 30)
        self.tab_news_btn.setStyleSheet(tabs_style)
        self.tab_news_btn.setCheckable(True)
        self.tab_news_btn.setChecked(True)
        self.tab_news_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.tab_mods_btn = QPushButton("Модпаки", self.header_frame)
        self.tab_mods_btn.setGeometry(310, 5, 100, 30)
        self.tab_mods_btn.setStyleSheet(tabs_style)
        self.tab_mods_btn.setCheckable(True)
        self.tab_mods_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.tab_installed_mods_btn = QPushButton("Установки", self.header_frame)
        self.tab_installed_mods_btn.setGeometry(420, 5, 100, 30)  # Position after "Settings"
        self.tab_installed_mods_btn.setStyleSheet(tabs_style)
        self.tab_installed_mods_btn.setCheckable(True)
        self.tab_installed_mods_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.tab_settings_btn = QPushButton("Информация", self.header_frame)
        self.tab_settings_btn.setGeometry(530, 5, 100, 30)  # Позиция после "Модпаки"
        self.tab_settings_btn.setStyleSheet(tabs_style)
        self.tab_settings_btn.setCheckable(True)
        self.tab_settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.tab_moderator_btn = QPushButton("Модерация", self.header_frame)
        self.tab_moderator_btn.setGeometry(640, 5, 100, 30)  # Позиция после "Информация"
        self.tab_moderator_btn.setStyleSheet(tabs_disabled_style)
        self.tab_moderator_btn.setCheckable(True)
        # self.tab_moderator_btn.setEnabled(False)
        self.tab_moderator_btn.setCursor(QCursor(Qt.CursorShape.ForbiddenCursor))

        self.close_btn = QPushButton("✕", self.header_frame)
        self.close_btn.setGeometry(ww - 40, 5, 30, 30)
        self.close_btn.setFont(QFont("sans-serif", 11, QFont.Weight.Bold))
        self.close_btn.setStyleSheet("""
                    QPushButton { background-color: transparent; color: red; border: none; }
                    QPushButton:hover { color: darkred; }
                """)
        # noinspection PyUnresolvedReferences
        self.close_btn.clicked.connect(sys.exit)
        self.close_btn.raise_()
        self.close_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.min_btn = QPushButton("—", self.header_frame)
        self.min_btn.setGeometry(ww - 80, 5, 30, 30)
        self.min_btn.setFont(QFont("sans-serif", 11, QFont.Weight.Bold))
        self.min_btn.setStyleSheet("""
                    QPushButton { background-color: transparent; color: yellow; border: none; }
                    QPushButton:hover { color: gray; }
                """)
        # noinspection PyUnresolvedReferences
        self.min_btn.clicked.connect(self.launcher.showMinimized)
        self.min_btn.raise_()
        self.min_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

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


        self.news_page = QScrollArea(self.container_frame)
        self.news_page.setWidgetResizable(True)
        self.news_page.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.news_page.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.news_page.setStyleSheet("background-color: transparent; border: none;")
        self.news_content = QWidget(self.news_page)
        self.news_content.setStyleSheet("background-color: transparent;")
        self.news_layout = QVBoxLayout(self.news_content)
        self.news_layout.setContentsMargins(10, 10, 12, 10)
        self.news_layout.setSpacing(10)
        self.news_page.setWidget(self.news_content)
        self.container_layout.addWidget(self.news_page)

        mods_content_height = wh - 40
        self.mods_container = QFrame(self)
        self.mods_container.setGeometry(20, 40, ww - 40, mods_content_height)
        self.mods_container.setVisible(False)

        self.installed_mods_container = QFrame(self)
        self.installed_mods_container.setGeometry(20, 40, self.width() - 40, mods_content_height)
        self.installed_mods_container.setVisible(False)
        self.installed_mods_container.setStyleSheet("background-color: transparent;")

        # Layout for installed mods
        installed_mods_container_layout = QVBoxLayout(self.installed_mods_container)
        installed_mods_container_layout.setContentsMargins(0, 0, 0, 0)
        self.installed_mods_page = QScrollArea(self.installed_mods_container)
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

        # Лейаут
        settings_layout = QHBoxLayout(self.settings_container)
        settings_layout.setContentsMargins(10, 10, 10, 10)
        settings_layout.setSpacing(20)
        settings_layout.addStretch()  # Центрируем карточки
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 150))

        # Карточка "Об проекте"
        about_card = QFrame(self.settings_container)
        about_card.setFixedWidth(400)
        about_card.setStyleSheet("""
            QFrame {
                background-color: rgba(50,50,50,200);
                border-radius: 10px;
                border: none;
            }
        """)
        about_shadow = QGraphicsDropShadowEffect()
        about_shadow.setBlurRadius(15)
        about_shadow.setOffset(0, 2)
        about_shadow.setColor(QColor(0, 0, 0, 150))
        about_card.setGraphicsEffect(about_shadow)
        about_layout = QVBoxLayout(about_card)
        about_layout.setContentsMargins(15, 15, 15, 15)
        about_layout.setSpacing(10)

        about_title_label = QLabel("Немного про лаунчер", about_card)
        about_title_label.setStyleSheet("color: white; font-weight: bold;")
        about_title_label.setFont(QFont("sans-serif", 16))
        about_title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        about_layout.addWidget(about_title_label)

        about_text = (
            "Лаунчер CounterMine2 - это неофициальный лаунчер созданный благодаря комьюнити игроков. "
            "В лаунчер не было и не будет рекламы, так что проект остается абсолютно неоплачиваемым. "
            "Лаунчер является абсолютно бесплатным и не требует никаких денежных средств "
            "и в связи с этим, мы просим расширять инфо об проекте между игроками для поддержания "
            "популярности и для мотивации развивать проект дальше"
            "\n \n Лаунчер разработан игроком raizor \n По вопросам вы всегда можете обратится в\n"
            "   - Discord: raizor000\n"
            "   - Mail: m4215284@gmail.com\n"
            "\n \nПримечание: лаунчер собирает следующие данные: Инфо об процессоре, количество"
            " оперативной памяти, объём накопителя, часовой пояс, текущая дата и время, версия Windows "
            "а также проверяет на наличие вашего IP в списках банов. Мы не имеем доступа к вашему IP"
            f"\nversion: {self.version} | IP: {self.ip}"
        )
        about_text_label = QLabel(about_text, about_card)
        about_text_label.setStyleSheet("color: #dddddd; font-size: 12pt;")
        about_text_label.setFont(QFont("sans-serif", 10))
        about_text_label.setWordWrap(True)
        about_text_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        about_layout.addWidget(about_text_label)

        # Растягиваем содержимое по вертикали
        about_layout.addStretch()
        settings_layout.addWidget(about_card)

        # Центрируем карточки
        settings_layout.addStretch()

        mods_container_layout = QVBoxLayout(self.mods_container)
        mods_container_layout.setContentsMargins(0, 0, 0, 0)
        self.mods_page = QScrollArea(self.mods_container)
        self.mods_page.setWidgetResizable(True)
        self.mods_page.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.mods_page.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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

        # Изначально показываем кнопку логина
        self._show_moderator_login()


        # noinspection PyUnresolvedReferences
        self.tab_news_btn.clicked.connect(lambda: self._switch_tab(0))
        # noinspection PyUnresolvedReferences
        self.tab_mods_btn.clicked.connect(lambda: self._switch_tab(1))
        # noinspection PyUnresolvedReferences
        self.tab_settings_btn.clicked.connect(lambda: self._switch_tab(2))
        # noinspection PyUnresolvedReferences
        self.tab_installed_mods_btn.clicked.connect(lambda: self._switch_tab(3))
        # noinspection PyUnresolvedReferences
        # self.tab_moderator_btn.clicked.connect(lambda: self._switch_tab(4))

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
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
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
        self.reinstall_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        ofw, ofh = 241, 64
        self.online_frame = QFrame(self)
        self.online_frame.setGeometry(20, self.height() - ofh - 10, ofw, ofh)
        self.online_frame.setStyleSheet("background-color:#323232; border-radius:8px;")
        online_layout = QHBoxLayout(self.online_frame)
        online_layout.setContentsMargins(10, 5, 10, 5)
        online_layout.setSpacing(10)

        self.online_gif_label = QLabel(self.online_frame)
        movie = QMovie(self.resource_path("assets/online_animation.gif"))
        movie.setScaledSize(QSize(55, 50))
        if movie.isValid():
            self.online_gif_label.setMovie(movie)
            movie.start()
        online_layout.addWidget(self.online_gif_label)

        self.online_label = QLabel("ИГРАЮТ - ЧЕЛ.", self.online_frame)
        self.online_label.setStyleSheet("color:white; font-weight:bold;")
        self.online_label.setFont(QFont("sans-serif", 11))
        online_layout.addWidget(self.online_label)

        pfw, pfh = 240, ofh
        self.play_frame = QFrame(self)
        self.play_frame.setGeometry(self.width() - pfw - 120, self.height() - pfh - 10, pfw, pfh)
        self.play_frame.setStyleSheet("background:transparent;")
        self.play_btn = QPushButton("Играть", self.play_frame)
        self.play_btn.setGeometry(0, 0, pfw, pfh)
        self.play_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.play_btn.setFont(QFont("sans-serif", 13, QFont.Weight.Bold))
        self.play_btn.setStyleSheet("""
                    QPushButton { background-color: #45A049; color:white; border-radius:10px; }
                    QPushButton:hover:!disabled { background-color: #45a800; }
                    QPushButton:disabled { background-color:#2e6b35; color:#aaa; }
                """)
        # noinspection PyUnresolvedReferences
        self.play_btn.clicked.connect(self.play_clicked.emit)

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
            # self.tab_moderator_btn.setChecked(index == 4)
            self.play_frame.setVisible(index == 0)
            self.online_frame.setVisible(index == 0)
            self.buttons_block.setVisible(index == 0)
            for toast in self._toast_widgets:
                toast.setVisible(index == 0)
            self.dim_layer.setVisible(index in (1, 2, 3, 4))  # Затемнение для всех кроме Главной
            self.container_frame.raise_()
            if index == 0:
                self.news_page.raise_()
            elif index == 3:
                self._populate_installed_mods()
            elif index == 4:
                self._show_moderator_login()
                self._check_moderator_access()  # Проверяем доступ при переключении
        except Exception as e:
            print(e)

    def _get_installed_mods(self):
        mods_dir = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), ".countermine", "mods")
        installed_mods = []
        print(f"Сканирование папки: {mods_dir}")

        if not os.path.exists(mods_dir):
            print("Папка mods не существует")
            return installed_mods

        for file in os.listdir(mods_dir):
            if file.endswith('.jar'):
                print(f"Обнаружен мод: {file}")
                base_name = file.replace('.jar', '')
                parts = base_name.split('-')
                slug_guess = parts[0]
                slug = slug_guess.lower().replace('_', '-')

                mod_data = next((mod for mod in self.mods_data if mod["slug"] == slug), None)
                if mod_data:
                    mod_data["installed"] = True
                    installed_mods.append(mod_data)
                else:
                    installed_mods.append({
                        "name": base_name.replace('-', ' '),
                        "slug": slug,
                        "desc": "Описание мода не найдено",
                        "installed": True,
                        "project_id": slug,
                    })

        print(f"Найдено установленных модов: {len(installed_mods)}")
        return installed_mods

    def _populate_installed_mods(self):
        self._refresh_installed_mods = True
        self._fetch_mods("", "downloads")
        self._render_installed_mods()

    def _render_installed_mods(self):
        """Заполняет вкладку установленных модов."""
        while self.installed_mods_layout.count():
            item = self.installed_mods_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        installed_mods = self._get_installed_mods()

        card_width = (self.installed_mods_container.width() - 40) // 3
        card_height = 180

        for i, mod in enumerate(installed_mods):
            name = mod["name"]
            slug = mod["slug"]
            desc = mod["desc"]

            card = QFrame(self.installed_mods_content)
            card.setFixedSize(card_width, card_height)
            card.setStyleSheet("""
                QFrame {
                    background-color: #555555;
                    border-radius: 10px;
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
            title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            card_layout.addWidget(title_label)

            desc_label = QLabel(desc, card)
            desc_label.setStyleSheet("color: #dddddd;")
            desc_label.setFont(QFont("sans-serif", 10))
            desc_label.setWordWrap(True)
            desc_label.setFixedHeight(60)
            desc_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            card_layout.addWidget(desc_label)

            button = QPushButton("Удалить", card)
            button.setFixedHeight(30)
            button.setStyleSheet("""
                QPushButton {
                    background-color: #d32f2f;
                    color: white;
                    border-radius: 5px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #b71c1c;
                }
            """)
            button.clicked.connect(lambda checked, s=slug: self.mod_action.emit(s, "remove"))
            card_layout.addWidget(button)

            row = i // 3
            col = i % 3
            self.installed_mods_layout.addWidget(card, row, col)

        self.installed_mods_content.adjustSize()

    def _primary_screen(self):
        from PyQt6.QtWidgets import QApplication
        return QApplication.primaryScreen()

    def show_toast(self, text: str, timeout=10000, icon_path: str = None):
        toast = QWidget(self)
        toast.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        toast.setStyleSheet("""
            QWidget {
                background-color: rgba(60, 60, 60, 200);
                border-radius: 10px;
            }
            QLabel {
                color: white;
                font-size: 12pt;
            }
        """)

        layout = QHBoxLayout(toast)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        if icon_path:
            icon_label = QLabel()
            pixmap = QPixmap(icon_path).scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            icon_label.setPixmap(pixmap)
            layout.addWidget(icon_label)

        text_label = QLabel(text)
        text_label.setWordWrap(True)
        layout.addWidget(text_label)

        toast.adjustSize()

        header = self.header_frame
        margin = 25
        x = header.width() - toast.width() - margin - self.buttons_block.width()
        y = self.buttons_block.y() + self._active_toasts * (toast.height() + 10)
        toast.move(x, y)
        toast.raise_()

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 150))
        toast.setGraphicsEffect(shadow)

        toast.show()
        self._active_toasts += 1
        self._toast_widgets.append(toast)

        def close():
            if toast in self._toast_widgets:
                self._toast_widgets.remove(toast)
                toast.deleteLater()
                self._active_toasts -= 1

        if timeout:
            QTimer.singleShot(timeout, close)

    def set_play_status(self, text):
        self.play_btn.setText(text)

    def set_play_enabled(self, yes: bool):
        self.play_btn.setEnabled(yes)

    def update_online_label(self, text):
        self.online_label.setText(text)

    def update_news(self, news_list: list):
        # Очищаем старый контент
        while self.news_layout.count():
            item = self.news_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.news_data = news_list  # Сохраняем данные

        for news in news_list:  # Добавляем блоки для каждой новости
            news_block = QFrame(self.news_content)
            news_block.setStyleSheet("background-color: rgba(50,50,50,200); border-radius:10px;")

            block_layout = QVBoxLayout(news_block)  # Layout внутри блока
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

            if "date" in news:  # Опционально добавляем дату
                date_label = QLabel(news["date"], news_block)
                date_label.setStyleSheet("color:gray; font-style: italic;")
                date_label.setFont(QFont("sans-serif", 10))
                block_layout.addWidget(date_label)

            self.news_layout.addWidget(news_block)

    def _setup_mods_search(self):
        # Добавляем поисковую строку
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
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)
        self.search_edit.textChanged.connect(lambda text: self.search_timer.start(250))


        self.search_timer.start(50)

    def _perform_search(self):
        query = self.search_edit.text().strip()
        index = "downloads" if not query else "relevance"
        self._fetch_mods(query, index)

    def _fetch_mods(self, query, index="relevance"):
        facets_str = f'[["project_type:mod"],["categories:fabric"],["versions:{VERSION}"]]'
        url = f"https://api.modrinth.com/v2/search?query={urllib.parse.quote(query)}&facets={urllib.parse.quote(facets_str)}&limit=54&index={index}"
        self._mods_pending_url = url
        if not self._mods_loading:
            self._start_mods_search()

    def _start_mods_search(self):
        url = self._mods_pending_url
        self._mods_pending_url = None
        self._mods_loading = True
        finished = self._mods_search_finished

        def fetch():
            try:
                with urllib.request.urlopen(url, timeout=8) as response:
                    hits = json.load(response)["hits"]
            except (OSError, ValueError, KeyError, TypeError) as error:
                print(error)
                hits = None
            try:
                finished.emit(hits)
            except RuntimeError:
                pass  # The window was destroyed while the request was running.

        Thread(target=fetch, daemon=True).start()

    def _apply_mods_search(self, hits):
        self._mods_loading = False
        if self._mods_pending_url is not None:
            self._start_mods_search()
            return
        if hits is None or (hasattr(self, "search_timer") and self.search_timer.isActive()):
            return
        try:
            banned_mods = ["Entity Culling"]
            mods_data = []
            for hit in hits:
                if hit['title'] not in banned_mods:
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
            if getattr(self, "_refresh_installed_mods", False):
                self._refresh_installed_mods = False
                self._render_installed_mods()
        except (TypeError, KeyError, OSError) as error:
            print(error)

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
            installed = self._is_mod_installed(slug)  # Проверяем реальный статус
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
            title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            card_layout.addWidget(title_label)

            desc_label = QLabel(desc, card)
            desc_label.setStyleSheet("color: #dddddd;")
            desc_label.setFont(QFont("sans-serif", 10))
            desc_label.setWordWrap(True)
            desc_label.setFixedHeight(60)
            desc_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            card_layout.addWidget(desc_label)

            button_text = "Удалить" if installed else "Установить"
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
        """Обновляет статус мода (установка, удаление, включение, отключение)."""
        print(f"Обновление статуса мода: {mod_slug}, действие={action}")

        if action in ("install", "remove"):

            if mod_slug in self.mod_buttons:
                button = self.mod_buttons[mod_slug]
                button.setEnabled(True)
                button.setText("Remove" if action == "install" else "Install")
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

    def _check_moderator_access(self):
        if not self.discord_id:
            self._show_moderator_login()
            return
        # Получаем список модераторов с сервера
        try:
            response = requests.get(MODERATORS_URL)
            response.raise_for_status()
            self.moderators = response.json()
            if self.discord_id in self.moderators:
                self._show_moderator_ui()
            else:
                self._show_access_denied()
        except Exception as e:
            print(f"Ошибка загрузки модераторов: {e}")
            self._show_access_denied()

    def _show_moderator_login(self):
        # Очищаем контент
        while self.moderator_layout.count():
            item = self.moderator_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        login_btn = QPushButton("Авторизоваться через Discord", self.moderator_content)
        login_btn.setFixedSize(300, 50)
        login_btn.setStyleSheet("""
            QPushButton { background-color: #7289da; color: white; border-radius: 5px; }
            QPushButton:hover { background-color: #677bc4; }
        """)
        login_btn.clicked.connect(self._start_discord_auth)
        self.moderator_layout.addWidget(login_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        # self._start_discord_auth()
    def _start_discord_auth(self):
        # Popup для OAuth
        # self.auth_window = QWebEngineView()
        # self.auth_window.setWindowTitle("Авторизация Discord")
        # self.auth_window.setFixedSize(600, 800)
        # self.auth_window.load(QUrl(DISCORD_AUTH_URL))
        #
        # Перехватчик для code
        # profile = QWebEngineProfile.defaultProfile()
        # interceptor = RequestInterceptor(self)
        # profile.setUrlRequestInterceptor(interceptor)
        # page = QWebEnginePage(profile, self.auth_window)
        # self.auth_window.setPage(page)
        #
        # interceptor.codeChanged.connect(self._on_discord_code)
        # self.auth_window.show()
        pass

    def _on_discord_code(self, code):
        # Обмен code на token
        data = {
            'client_id': DISCORD_CLIENT_ID,
            'client_secret': DISCORD_CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': DISCORD_REDIRECT_URI
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        response = requests.post(DISCORD_TOKEN_URL, data=data, headers=headers)
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data['access_token']
            # Получаем user ID
            headers = {'Authorization': f'Bearer {access_token}'}
            user_response = requests.get(DISCORD_USER_URL, headers=headers)
            if user_response.status_code == 200:
                user_data = user_response.json()
                self.discord_id = user_data['id']
                self._check_moderator_access()
                self.auth_window.close()
            else:
                print("Ошибка получения user ID")
        else:
            print("Ошибка обмена code на token")

    def _show_access_denied(self):
        while self.moderator_layout.count():
            item = self.moderator_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        denied_label = QLabel("Нет доступа к данному разделу 🔒", self.moderator_content)
        denied_label.setStyleSheet("color: white; font-size: 24pt;")
        denied_label.setFont(QFont("sans-serif", 24, QFont.Weight.Bold))
        denied_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.moderator_layout.addWidget(denied_label, alignment=Qt.AlignmentFlag.AlignCenter)

    def _show_moderator_ui(self):
        while self.moderator_layout.count():
            item = self.moderator_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Раздел бана/разбана
        ban_frame = QFrame()
        ban_layout = QHBoxLayout(ban_frame)
        ip_input = QLineEdit()
        ip_input.setPlaceholderText("Введите IP")
        ban_btn = QPushButton("Бан")
        ban_btn.clicked.connect(lambda: self._ban_ip(ip_input.text()))
        unban_btn = QPushButton("Разбан")
        unban_btn.clicked.connect(lambda: self._unban_ip(ip_input.text()))
        ban_layout.addWidget(ip_input)
        ban_layout.addWidget(ban_btn)
        ban_layout.addWidget(unban_btn)
        self.moderator_layout.addWidget(ban_frame)

        # Раздел управления модераторами
        mod_list_scroll = QScrollArea()
        mod_list_scroll.setWidgetResizable(True)
        mod_list_content = QWidget()
        mod_list_layout = QVBoxLayout(mod_list_content)
        for mod_id in self.moderators:
            mod_frame = QFrame()
            mod_frame_layout = QHBoxLayout(mod_frame)
            mod_label = QLabel(mod_id)
            remove_btn = QPushButton("Удалить")
            remove_btn.clicked.connect(lambda _, id=mod_id: self._remove_moderator(id))
            mod_frame_layout.addWidget(mod_label)
            mod_frame_layout.addWidget(remove_btn)
            mod_list_layout.addWidget(mod_frame)
        mod_list_scroll.setWidget(mod_list_content)
        self.moderator_layout.addWidget(mod_list_scroll)

        # Добавление нового модератора
        add_frame = QFrame()
        add_layout = QHBoxLayout(add_frame)
        new_id_input = QLineEdit()
        new_id_input.setPlaceholderText("Новый Discord ID")
        add_btn = QPushButton("Добавить")
        add_btn.clicked.connect(lambda: self._add_moderator(new_id_input.text()))
        add_layout.addWidget(new_id_input)
        add_layout.addWidget(add_btn)
        self.moderator_layout.addWidget(add_frame)

    def _ban_ip(self, ip):
        pass
        # if ip:
        #     response = requests.post(BANNED_IPS_ADD_URL, json={"ip": ip})
        #     if response.status_code == 200:
        #         self.show_toast("IP забанен")
        #     else:
        #         self.show_toast("Ошибка бана")

    def _unban_ip(self, ip):
        pass
        # if ip:
        #     response = requests.post(BANNED_IPS_REMOVE_URL, json={"ip": ip})
        #     if response.status_code == 200:
        #         self.show_toast("IP разбанен")
        #     else:
        #         self.show_toast("Ошибка разбана")

    def _add_moderator(self, mod_id):
        pass
        # if mod_id:
        #     response = requests.post(MODERATORS_ADD_URL, json={"id": mod_id})
        #     if response.status_code == 200:
        #         self._check_moderator_access()  # Обновляем UI
        #     else:
        #         self.show_toast("Ошибка добавления")

    def _remove_moderator(self, mod_id):
        pass
        # response = requests.post(MODERATORS_REMOVE_URL, json={"id": mod_id})
        # if response.status_code == 200:
        #     self._check_moderator_access()  # Обновляем UI
        # else:
        #     self.show_toast("Ошибка удаления")


# class RequestInterceptor(QtWebEngineCore.QWebEngineUrlRequestInterceptor):
#     codeChanged = pyqtSignal(str)
#
#     def interceptRequest(self, info):
#         url = info.requestUrl().toString()
#         if url.startswith(DISCORD_REDIRECT_URI):
#             params = urllib.parse.parse_qs(info.requestUrl().query())
#             if "code" in params:
#                 code = params["code"][0]
#                 self.codeChanged.emit(code)
#