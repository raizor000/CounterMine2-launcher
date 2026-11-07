import os
import sys
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QUrl, QTimer
from PyQt6.QtGui import QDesktopServices, QPixmap, QFont, QCursor, QIcon, QMovie, QColor
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QFrame, QStackedLayout, QHBoxLayout, QGraphicsDropShadowEffect, QVBoxLayout,
    QGridLayout, QSizePolicy, QScrollArea
)

class LauncherUI(QWidget):
    play_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()
    mod_action = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.launcher = parent
        self._active_toasts = 0  # Счетчик активных тостов
        self._toast_widgets = []
        self._build_ui()

    def resource_path(self, relative_path):
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    def _build_ui(self):
        # Базовая геометрия
        screen = self._primary_screen()
        sw = screen.size().width()
        ww = int(sw * 0.4)
        wh = int(ww * 9 / 16)
        self.setFixedSize(ww, wh)

        # Фон
        bg = QLabel(self)
        pix = QPixmap(self.resource_path("background.jpg"))
        if not pix.isNull():
            pix = pix.scaled(ww, wh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            bg.setPixmap(pix)
        bg.setGeometry(0, 0, ww, wh)

        # Затемнённый слой (будет показан только на вкладке "Модпаки")
        self.dim_layer = QFrame(self)
        self.dim_layer.setGeometry(0, 0, ww, wh)
        self.dim_layer.setStyleSheet("background-color: rgba(0, 0, 0, 0.6);")
        self.dim_layer.setVisible(False)  # По умолчанию скрыт

        # Header frame
        self.header_frame = QFrame(self)
        self.header_frame.setGeometry(0, 0, ww, 40)
        self.header_frame.setStyleSheet("background-color: rgba(50,50,50,200);")

        # Logo
        self.logo = QLabel(self.header_frame)
        self.logo_pix = QPixmap(self.resource_path("4.png"))
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

        # Кнопки вкладок
        self.tab_news_btn = QPushButton("Основная", self.header_frame)
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

        # Close/minimize
        self.close_btn = QPushButton("✕", self.header_frame)
        self.close_btn.setGeometry(ww - 40, 5, 30, 30)
        self.close_btn.setFont(QFont("sans-serif", 11, QFont.Weight.Bold))
        self.close_btn.setStyleSheet("""
                    QPushButton { background-color: transparent; color: red; border: none; }
                    QPushButton:hover { color: darkred; }
                """)
        self.close_btn.clicked.connect(sys.exit)
        self.close_btn.raise_()

        self.min_btn = QPushButton("—", self.header_frame)
        self.min_btn.setGeometry(ww - 80, 5, 30, 30)
        self.min_btn.setFont(QFont("sans-serif", 11, QFont.Weight.Bold))
        self.min_btn.setStyleSheet("""
                    QPushButton { background-color: transparent; color: yellow; border: none; }
                    QPushButton:hover { color: gray; }
                """)
        self.min_btn.clicked.connect(self.launcher.showMinimized)
        self.min_btn.raise_()

        self.separator_min = QFrame(self.header_frame)
        self.separator_min.setFrameShape(QFrame.Shape.VLine)
        self.separator_min.setFrameShadow(QFrame.Shadow.Sunken)
        self.separator_min.setStyleSheet("background-color: #777;")
        self.separator_min.setFixedWidth(3)
        self.separator_min.setFixedHeight(self.logo.height())
        self.separator_min.setGeometry(self.min_btn.x() - 12, 8, 2, 24)

        # Контейнер для новостей
        self.container_frame = QFrame(self)
        self.container_frame.setGeometry(20, 60, 400, 300)  # Начальная высота для новостей
        self.container_layout = QStackedLayout(self.container_frame)

        # Страница новостей
        self.news_page = QFrame(self.container_frame)
        self.news_block = QFrame(self.news_page)
        self.news_block.setGeometry(0, 0, 400, 10)  # Начальная высота, будет обновляться
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

        # Отдельный контейнер для модпаков
        mods_content_height = wh - 40  # Высота окна минус хедер
        self.mods_container = QFrame(self)
        self.mods_container.setGeometry(20, 40, ww - 40, mods_content_height)
        self.mods_container.setVisible(False)  # Скрыт по умолчанию

        mods_container_layout = QVBoxLayout(self.mods_container)
        mods_container_layout.setContentsMargins(0, 0, 0, 0)

        # Страница модпаков
        self.mods_page = QScrollArea(self.mods_container)
        self.mods_page.setWidgetResizable(True)
        self.mods_page.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.mods_page.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # Без видимого скроллбара
        self.mods_page.setStyleSheet("background-color: transparent; border: none;")

        self.mods_content = QWidget(self.mods_page)
        self.mods_content.setStyleSheet("background-color: transparent;")
        self.mods_layout = QGridLayout(self.mods_content)
        self.mods_layout.setContentsMargins(10, 10, 10, 10)
        self.mods_layout.setSpacing(10)
        self.mods_page.setWidget(self.mods_content)

        mods_container_layout.addWidget(self.mods_page)

        # Словари для доступа к элементам
        self.mod_cards = {}
        self.mod_buttons = {}
        self.mod_labels = {}  # name -> (title_label, desc_label)

        # Пример данных (можно менять позже)
        self.mods_data = [
            {"name": "ZoomSensitivityFix", "desc": "Фикс DPI при зуме \n Рекомендуется для всех игроков",
             "installed": False},
            {"name": "???",
             "desc": "Оптифайн пока что не доступен :(",
             "installed": False},
            {"name": "BadOptimizations", "desc": "Оптимизация игры", "installed": False},
            {"name": "???", "desc": "???", "installed": False},
            {"name": "???", "desc": "???", "installed": False},
        ]

        self._populate_mods(self.mods_data)

        # Подключаем переключение вкладок
        self.tab_news_btn.clicked.connect(lambda: self._switch_tab(0))
        self.tab_mods_btn.clicked.connect(lambda: self._switch_tab(1))

        # Social vertical block (right)
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

        # Icons
        icons = [("tg.png", "https://t.me/countermine2"), ("yt.png", "https://www.youtube.com/@CounterMine2"),
                 ("dc.png", "https://discord.com/invite/counter-mine-2-935258545170047006"),
                 ("vk.png", "https://vk.com/countermine"), ("cp.png", "https://cherry.pizza/")]
        for i, (icon, link) in enumerate(icons):
            btn = QPushButton(self.buttons_block)
            y = 10 + i * (button_size + spacing)
            btn.setGeometry(12, y, button_size, button_size)
            ico = QIcon(self.resource_path(icon))
            btn.setIcon(ico)
            btn.setIconSize(QSize(button_size, button_size))
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda checked=False, url=link: QDesktopServices.openUrl(QUrl(url)))
            btn.setStyleSheet("border:none; background:#323232;")
            btn.setToolTip(str(icon.replace(".png", "")))

        # Online frame (bottom-left)
        ofw, ofh = 241, 64
        self.online_frame = QFrame(self)
        self.online_frame.setGeometry(20, self.height() - ofh - 10, ofw, ofh)
        self.online_frame.setStyleSheet("background-color:#323232; border-radius:8px;")
        online_layout = QHBoxLayout(self.online_frame)
        online_layout.setContentsMargins(10, 5, 10, 5)
        online_layout.setSpacing(10)

        self.online_gif_label = QLabel(self.online_frame)
        movie = QMovie(self.resource_path("3.gif"))
        movie.setScaledSize(QSize(55, 50))
        if movie.isValid():
            self.online_gif_label.setMovie(movie)
            movie.start()
        online_layout.addWidget(self.online_gif_label)

        self.online_label = QLabel("ИГРАЮТ - ЧЕЛ.", self.online_frame)
        self.online_label.setStyleSheet("color:white; font-weight:bold;")
        self.online_label.setFont(QFont("sans-serif", 11))
        online_layout.addWidget(self.online_label)

        # Play button (bottom-right)
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
        self.play_btn.clicked.connect(self.play_clicked.emit)

    def _switch_tab(self, index):
        self.container_frame.setVisible(index == 0)
        self.mods_container.setVisible(index == 1)
        self.tab_news_btn.setChecked(index == 0)
        self.tab_mods_btn.setChecked(index == 1)
        self.play_frame.setVisible(index == 0)
        self.online_frame.setVisible(index == 0)
        self.buttons_block.setVisible(index == 0)
        for toast in self._toast_widgets:
            toast.setVisible(index == 0)
        self.dim_layer.setVisible(index == 1)
        if index == 0:
            self._resize_news_block()

    def _primary_screen(self):
        from PyQt6.QtWidgets import QApplication
        return QApplication.primaryScreen()

    def show_toast(self, text: str, timeout=10000, icon_path: str = None):
        # Контейнер для иконки + текста
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

        # Позиция под хедером справа
        header = self.header_frame
        margin = 25
        x = header.width() - toast.width() - margin - self.buttons_block.width()
        y = self.buttons_block.y() + self._active_toasts * (toast.height() + 10)  # 10 px spacing
        toast.move(x, y)
        toast.raise_()

        # Тень
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 150))
        toast.setGraphicsEffect(shadow)

        toast.show()
        self._active_toasts += 1
        self._toast_widgets.append(toast)  # Добавляем тост в список

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

    def _populate_mods(self, mods_data):
        card_width = (self.mods_container.width() - 40) // 3
        card_height = 150  # Фиксированная высота для карточек

        for i, mod in enumerate(mods_data):
            name = mod["name"]
            desc = mod["desc"]
            installed = mod["installed"]

            # Карточка
            card = QFrame(self.mods_content)
            card.setFixedSize(card_width, card_height)
            card.setStyleSheet("""
                QFrame {
                    background-color: #555555;  /* Непрозрачный фон */
                    border-radius: 10px;  /* Скругленные края */
                    border: none;
                }
            """)

            # Layout для карточки
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 10, 10, 10)
            card_layout.setSpacing(5)

            # Название
            title_label = QLabel(name, card)
            title_label.setStyleSheet("color: white; font-weight: bold;")
            title_label.setFont(QFont("sans-serif", 12))
            title_label.setWordWrap(True)
            title_label.setFixedHeight(40)  # Фиксированная высота для влезания
            title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            card_layout.addWidget(title_label)

            # Описание
            desc_label = QLabel(desc, card)
            desc_label.setStyleSheet("color: #dddddd;")
            desc_label.setFont(QFont("sans-serif", 10))
            desc_label.setWordWrap(True)
            desc_label.setFixedHeight(60)  # Фиксированная высота для влезания
            desc_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            card_layout.addWidget(desc_label)

            # Кнопка
            button_text = "Remove" if installed else "Install"
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
            button.clicked.connect(lambda checked, n=name: self._handle_mod_button_click(n))
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

            # Добавляем в словари
            self.mod_cards[name] = card
            self.mod_buttons[name] = button
            self.mod_labels[name] = (title_label, desc_label)

            # Добавляем в грид: 3 в ряд
            row = i // 3
            col = i % 3
            self.mods_layout.addWidget(card, row, col)

        # Обновляем размер контента
        self.mods_content.adjustSize()

    # ---- public API for launcher.py ----

    def _handle_mod_button_click(self, mod_name: str):
        action = None
        for mod in self.mods_data:
            if mod["name"] == mod_name:
                action = "remove" if mod["installed"] else "install"
                break

        if action:
            self.mod_action.emit(mod_name, action)

    def update_mod_status(self, mod_name: str, new_installed: bool):
        for mod in self.mods_data:
            if mod["name"] == mod_name:
                mod["installed"] = new_installed
                break

        # Очистка текущих карточек
        while self.mods_layout.count():
            item = self.mods_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Очистка словарей
        self.mod_cards.clear()
        self.mod_buttons.clear()
        self.mod_labels.clear()

        # Перезаполнение
        self._populate_mods(self.mods_data)