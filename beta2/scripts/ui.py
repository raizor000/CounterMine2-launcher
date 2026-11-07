from threading import Thread
import json
import os
import sys
import urllib

from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QDesktopServices, QPixmap, QFont, QCursor, QIcon, QMovie, QColor
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QFrame, QStackedLayout, QHBoxLayout, \
    QGraphicsDropShadowEffect, QVBoxLayout, QGridLayout, QScrollArea, QLineEdit, QComboBox, QSlider, QCheckBox


class LauncherUI(QWidget):
    _mods_search_finished = pyqtSignal(object)
    play_clicked = pyqtSignal()
    reinstall_client = pyqtSignal()
    mod_action = pyqtSignal(str, str)
    window_size_changed = pyqtSignal(str)  # Передает строку вида "WxH" (например, "1280x720")
    fullscreen_changed = pyqtSignal(bool)  # True/False для полноэкранного режима
    nickname_changed = pyqtSignal(str)  # Передает никнейм
    reset_settings = pyqtSignal()  # Сигнал для сброса настроек


    def __init__(self, parent=None):
        super().__init__(parent)
        self._mods_loading = False
        self._mods_pending_url = None
        self._mods_search_finished.connect(self._apply_mods_search)
        self.launcher = parent
        self._active_toasts = 0  # Счетчик активных тостов
        self._toast_widgets = []
        self.prepared = False
        self._build_ui()

    def resource_path(self, relative_path):
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    def _build_ui(self):
        screen = self._primary_screen()
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
        self.tab_news_btn.setStyleSheet("""
                    QPushButton { background-color: #555; color: white; border-radius: 5px; border: none; }
                    QPushButton:hover { background-color: #666; }
                    QPushButton:checked { background-color: #45A049; }
                """)
        self.tab_news_btn.setCheckable(True)
        self.tab_news_btn.setChecked(True)
        self.tab_mods_btn = QPushButton("Модпаки", self.header_frame)
        self.tab_mods_btn.setGeometry(310, 5, 100, 30)
        self.tab_mods_btn.setStyleSheet("""
                    QPushButton { background-color: #555; color: white; border-radius: 5px; border: none; }
                    QPushButton:hover { background-color: #666; }
                    QPushButton:checked { background-color: #45A049; }
                """)
        self.tab_mods_btn.setCheckable(True)

        self.tab_settings_btn = QPushButton("Настройки", self.header_frame)
        self.tab_settings_btn.setGeometry(420, 5, 100, 30)  # Позиция после "Модпаки"
        self.tab_settings_btn.setStyleSheet("""
            QPushButton { background-color: #555; color: white; border-radius: 5px; border: none; }
            QPushButton:hover { background-color: #666; }
            QPushButton:checked { background-color: #45A049; }
        """)
        self.tab_settings_btn.setCheckable(True)



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

        self.separator_min = QFrame(self.header_frame)
        self.separator_min.setFrameShape(QFrame.Shape.VLine)
        self.separator_min.setFrameShadow(QFrame.Shadow.Sunken)
        self.separator_min.setStyleSheet("background-color: #777;")
        self.separator_min.setFixedWidth(3)
        self.separator_min.setFixedHeight(self.logo.height())
        self.separator_min.setGeometry(self.min_btn.x() - 12, 8, 2, 24)

        self.container_frame = QFrame(self)
        self.container_frame.setGeometry(20, 60, 400, 300)
        self.container_layout = QStackedLayout(self.container_frame)

        self.news_page = QFrame(self.container_frame)
        self.news_block = QFrame(self.news_page)
        self.news_block.setGeometry(0, 0, 400, 10)
        self.news_block.setStyleSheet("background-color: rgba(50,50,50,200); border-radius:10px;")

        self.news_title = QLabel("Загрузка новостей...", self.news_block)
        self.news_title.setStyleSheet("color:white;")
        self.news_title.setFont(QFont("sans-serif", 18))
        self.news_title.setWordWrap(True)
        self.news_title.setFixedWidth(380)
        self.news_title.move(10, 10)
        self.news_title.adjustSize()

        self.news_text = QLabel("", self.news_block)
        self.news_text.setStyleSheet("color:white;")
        self.news_text.setFont(QFont("sans-serif", 14))
        self.news_text.setWordWrap(True)
        self.news_text.setFixedWidth(380)
        self.news_text.move(10, self.news_title.height() + 15)
        self.news_text.adjustSize()
        self._resize_news_block()
        self.container_layout.addWidget(self.news_page)

        mods_content_height = wh - 40
        self.mods_container = QFrame(self)
        self.mods_container.setGeometry(20, 40, ww - 40, mods_content_height)
        self.mods_container.setVisible(False)

        # Настройки для Minecraft
        mods_content_height = wh - 40
        self.settings_container = QFrame(self)
        self.settings_container.setGeometry(20, 40, ww - 40, mods_content_height)
        self.settings_container.setVisible(False)
        self.settings_container.setStyleSheet("background-color: transparent;")

        # Лейаут для настроек
        settings_layout = QHBoxLayout(self.settings_container)
        settings_layout.setContentsMargins(10, 10, 10, 10)
        settings_layout.setSpacing(20)
        settings_layout.addStretch()  # Центрируем карточки

        # Карточка настроек
        settings_card = QFrame(self.settings_container)
        settings_card.setFixedWidth(400)
        settings_card.setStyleSheet("""
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
        settings_card.setGraphicsEffect(shadow)
        card_layout = QVBoxLayout(settings_card)
        card_layout.setContentsMargins(15, 15, 15, 15)
        card_layout.setSpacing(10)

        # Заголовок
        title_label = QLabel("Настройки Minecraft", settings_card)
        title_label.setStyleSheet("color: white; font-weight: bold;")
        title_label.setFont(QFont("sans-serif", 16))
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        card_layout.addWidget(title_label)

        # Никнейм
        nickname_label = QLabel("Никнейм в игре", settings_card)
        nickname_label.setStyleSheet("color: white; font-weight: bold;")
        nickname_label.setFont(QFont("sans-serif", 12))
        card_layout.addWidget(nickname_label)

        self.nickname_edit = QLineEdit(settings_card)
        self.nickname_edit.setPlaceholderText("Введите ваш никнейм...")
        self.nickname_edit.setStyleSheet("""
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
        # noinspection PyUnresolvedReferences
        self.nickname_edit.textChanged.connect(lambda text: self.nickname_changed.emit(text))
        card_layout.addWidget(self.nickname_edit)

        # Полноэкранный режим
        self.fullscreen_checkbox = QCheckBox("Полноэкранный режим", settings_card)
        self.fullscreen_checkbox.setStyleSheet("""
            QCheckBox {
                color: white;
                font-size: 12pt;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 5px;
                border: 2px solid #555;
                background-color: #333;
            }
            QCheckBox::indicator:checked {
                background-color: #45A049;
                border: 2px solid #45A049;
            }
            QCheckBox::indicator:hover {
                background-color: #666;
            }
        """)
        # noinspection PyUnresolvedReferences
        self.fullscreen_checkbox.stateChanged.connect(
            lambda state: self.fullscreen_changed.emit(state == Qt.CheckState.Checked)
        )
        card_layout.addWidget(self.fullscreen_checkbox)

        # Размер окна (необязательный)
        size_label = QLabel("Размер окна", settings_card)
        size_label.setStyleSheet("color: white; font-weight: bold;")
        size_label.setFont(QFont("sans-serif", 12))
        card_layout.addWidget(size_label)

        self.window_size_combo = QComboBox(settings_card)
        resolutions = ["854x480", "1280x720", "1366x768", "1600x900", "1920x1080"]
        self.window_size_combo.addItems(resolutions)
        self.window_size_combo.setCurrentText("1280x720")  # По умолчанию
        self.window_size_combo.setStyleSheet("""
            QComboBox {
                background-color: #555;
                color: white;
                border-radius: 5px;
                padding: 8px;
                border: none;
            }
            QComboBox:hover {
                background-color: #666;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #555;
                color: white;
                selection-background-color: #45A049;
                selection-color: white;
            }
        """)
        # noinspection PyUnresolvedReferences
        self.window_size_combo.currentTextChanged.connect(lambda text: self.window_size_changed.emit(text))
        card_layout.addWidget(self.window_size_combo)

        # Кнопка сброса настроек
        reset_button = QPushButton("Сбросить настройки", settings_card)
        reset_button.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
                border-radius: 5px;
                padding: 8px;
                border: none;
            }
            QPushButton:hover {
                background-color: #b71c1c;
            }
        """)
        # noinspection PyUnresolvedReferences
        reset_button.clicked.connect(self.reset_settings.emit)
        card_layout.addWidget(reset_button)

        # Растягиваем карточку по вертикали
        card_layout.addStretch()
        settings_layout.addWidget(settings_card)

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
            "\n \n Лаунчер разработан игроком raizor \n По вопросам вы всегда можете обратится в"
            "- Discord: raizor000\n"
            "- Mail: m4215284@gmail.com\n"
            "\n \n Примечание: лаунчер собирает следующие данные: Инфо об процессоре, количество"
            " оперативной памяти, объём накопителя, часовой пояс, текущая дата и время, версия Windows "
            "а также проверяет на наличие вашего IP в списках банов. Мы не имеем доступа к вашему IP"
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

        # noinspection PyUnresolvedReferences
        self.tab_news_btn.clicked.connect(lambda: self._switch_tab(0))
        # noinspection PyUnresolvedReferences
        self.tab_mods_btn.clicked.connect(lambda: self._switch_tab(1))
        # noinspection PyUnresolvedReferences
        self.tab_settings_btn.clicked.connect(lambda: self._switch_tab(2))

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
        self.container_frame.setVisible(index == 0)
        self.mods_container.setVisible(index == 1)
        self.settings_container.setVisible(index == 2)
        self.tab_news_btn.setChecked(index == 0)
        self.tab_mods_btn.setChecked(index == 1)
        self.tab_settings_btn.setChecked(index == 2)
        self.play_frame.setVisible(index == 0)
        self.online_frame.setVisible(index == 0)
        self.buttons_block.setVisible(index == 0)
        for toast in self._toast_widgets:
            toast.setVisible(index == 0)
        self.dim_layer.setVisible(index == 1 or index == 2)  # Затемнение для модов и настроек
        if index == 0:
            self._resize_news_block()
        elif index == 1:
            try:
                if not self.prepared:
                    self._setup_mods_search()
                    self.prepared = True
                self._perform_search()
            except Exception as e:
                print(e)

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

    def update_news(self, title, text):
        self.news_title.setText(title)
        self.news_text.setText(text)
        self.news_title.adjustSize()
        self.news_text.adjustSize()
        self._resize_news_block()

    def _resize_news_block(self):
        h = 10 + self.news_title.height() + 15 + self.news_text.height() + 10
        self.news_block.setFixedHeight(h)
        self.container_frame.setFixedHeight(h)

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

        # Добавляем поисковую строку перед QScrollArea
        mods_container_layout.insertWidget(0, search_widget)
        # Таймер для дебаунсинга поиска
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)
        self.search_edit.textChanged.connect(lambda text: self.search_timer.start(150))


        self.search_timer.start(50)

    def _perform_search(self):
        query = self.search_edit.text().strip()
        if not query:

            self._fetch_mods("", index="downloads")
        else:
            self._fetch_mods(query, index="relevance")

    def _fetch_mods(self, query, index="relevance"):
        facets_str = '[["project_type:mod"],["categories:fabric"],["versions:1.21.8"]]'
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
            mods_data = []
            for hit in hits:
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
        except (TypeError, KeyError, OSError) as error:
            print(error)

    def _is_mod_installed(self, slug):
        APPDATA = os.getenv("APPDATA") or os.path.expanduser("~")
        mods_dir = os.path.join(os.path.join(APPDATA, ".countermine"), "mods")
        if os.path.exists(mods_dir):
            for file in os.listdir(mods_dir):
                if file.endswith('.jar') and slug in file:  # Более мягкая проверка
                    return True
        return False

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
            disabled_color = "#540000" if installed else "#064500"
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
            if mod["name"] == "???":
                button.setEnabled(False)
                button.setStyleSheet(f"""
                                            QPushButton {{
                                                background-color: {disabled_color};
                                                color: white;
                                                border-radius: 5px;
                                                border: none;
                                            }}
                                            
                                        """)
            card_layout.addWidget(button)

            self.mod_cards[slug] = card
            self.mod_buttons[slug] = button
            self.mod_labels[slug] = (title_label, desc_label)

            row = i // 3
            col = i % 3
            self.mods_layout.addWidget(card, row, col)

        self.mods_content.adjustSize()

    def update_mod_status(self, mod_slug: str, new_installed: bool):
        print(f"Updating mod status: {mod_slug}, installed={new_installed}")  # Для отладки
        if mod_slug in self.mod_buttons:
            button = self.mod_buttons[mod_slug]
            button.setEnabled(True)
            button.setText("Remove" if new_installed else "Install")
            button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {"#d32f2f" if new_installed else "#45A049"};
                    color: white;
                    border-radius: 5px;
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: {"#b71c1c" if new_installed else "#3d8b40"};
                }}
                QPushButton:disabled {{
                    background-color: #333;
                    color: #aaa;
                }}
            """)
            # Обновляем действие кнопки
            action = "remove" if new_installed else "install"
            button.disconnect()  # Отключаем старый сигнал
            button.clicked.connect(lambda checked, s=mod_slug, a=action: self.mod_action.emit(s, a))
            # Обновляем mods_data
            for mod in self.mods_data:
                if mod["slug"] == mod_slug:
                    mod["installed"] = new_installed
                    break
        QtWidgets.QApplication.processEvents()  # Обновляем UI