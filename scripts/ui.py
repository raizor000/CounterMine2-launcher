import json
import sys
import urllib.parse
import urllib.request
import zipfile

from PyQt6 import QtWidgets
from PyQt6.QtCore import QSize, QUrl, QPoint, QObject, QThread, pyqtSlot, QSizeF
from PyQt6.QtGui import QDesktopServices, QPixmap, QFont, QIcon, QMovie, QFontDatabase
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QGraphicsVideoItem
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import QPushButton, QStackedLayout, QGraphicsDropShadowEffect, QGridLayout, QLineEdit, \
    QTextBrowser, QSizePolicy, QGraphicsView, \
    QGraphicsScene

from .utilties import *


class ModSearchWorker(QObject):
    finished = pyqtSignal(list)

    def __init__(self, query, index):
        super().__init__()
        self.query = query
        self.index = index
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            facets_str = f'[["project_type:mod"],["categories:fabric"],["versions:{VERSION}"]]'
            url = f"https://api.modrinth.com/v2/search?query={urllib.parse.quote(self.query)}&facets={urllib.parse.quote(facets_str)}&limit=54&index={self.index}"

            banned_mods = ["Entity Culling", "Xaero's Minimap"]
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
                hits = data['hits']
                mods_data = []
                for hit in hits:
                    if self._stop:
                        return
                    if hit['title'] not in banned_mods:
                        mods_data.append({
                            "name": hit['title'],
                            "slug": hit['slug'],
                            "desc": hit['description'][:150] + '...' if len(hit['description']) > 150 else hit[
                                'description'],
                            "installed": False,
                            "project_id": hit['project_id']
                        })
            if not self._stop:
                self.finished.emit(mods_data)
        except Exception as e:
            print("Mod search error:", e)
            if not self._stop:
                self.finished.emit([])


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
    cleanup_clicked = pyqtSignal()
    quitSignal = pyqtSignal()

    def __init__(self, version, ip, lang, parent=None):
        super().__init__(parent)

        self.status = None
        QFontDatabase.addApplicationFont(str(self.resource_path("assets/PressStart2P-Regular.ttf")))
        QFontDatabase.addApplicationFont(str(self.resource_path("assets/PIXY.ttf")))

        self.balance_frame = None
        self.top = None
        self.worker = None
        self.thread = QThread()
        self.prac_expanded = None
        self.faceit_expanded = None
        self.pix = None
        self.news_data = []
        self.launcher = parent
        self.version = version
        self.ip = ip
        self.lang = lang
        self.mods_data = []
        self.mod_cards = {}
        self.mod_buttons = {}
        self.mod_labels = {}
        self.shaders_data = []
        self.resourcepacks_data = []
        self.shader_buttons = {}
        self.resourcepack_buttons = {}
        self.information_container = None
        self.moresettings_container = None

        self._build_ui()

        self.installEventFilter(self)

    def _on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            print("Media loaded, now play")
            self.media_player.play()

    def resource_path(self, relative_path):
        # Для петрушки - получаем из ексешки ассеты
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    def _build_ui(self):
        ww = 1024
        wh = 580
        self.setFixedSize(ww, wh)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene, self)
        self.view.setGeometry(0, 0, ww, wh)
        self.view.setStyleSheet("background: transparent; border: none;")
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setFrameShape(QFrame.Shape.NoFrame)

        self.video_item = QGraphicsVideoItem()
        self.video_item.setSize(QSizeF(ww, wh+2))
        self.scene.addItem(self.video_item)

        self.media_player = QMediaPlayer(self)
        self.media_player.setVideoOutput(self.video_item)
        abs_path = os.path.abspath(str(self.resource_path("assets/intro_backgroud.mkv")))
        self.media_player.setSource(QUrl.fromLocalFile(abs_path))
        self.media_player.play()

        self.first_intro_played = False

        def _on_media_status_changed(status):
            if status == QMediaPlayer.MediaStatus.EndOfMedia:
                if not self.first_intro_played:
                    self.first_intro_played = True
                    bg_path = os.path.abspath(str(self.resource_path("assets/background.mkv")))
                    self.media_player.setSource(QUrl.fromLocalFile(bg_path))
                    self.media_player.setLoops(QMediaPlayer.Loops.Infinite)
                    self.media_player.play()

        self.media_player.mediaStatusChanged.connect(_on_media_status_changed)

        self.dim_layer = QFrame(self)
        self.dim_layer.setGeometry(0, 0, ww, wh)
        self.dim_layer.setStyleSheet("background-color: rgba(0, 0, 0, 0.7);")
        self.dim_layer.setVisible(
            False)  # Для петрушки - по ум. скрыт. Показывается на всех страницах кроме 0 (главной)

        self.search_edit = QLineEdit()
        self.installed_edit = QLineEdit()

        self.header_frame = QFrame(self)
        self.header_frame.setGeometry(0, 0, ww, 40)
        self.header_frame.setStyleSheet("background-color: rgba(50,50,50,190);")

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
        self.tab_news_btn.setStyleSheet(tabs_style_new)
        self.tab_news_btn.setCheckable(True)
        self.tab_news_btn.setChecked(True)
        self.tab_news_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                            ))

        self.tab_mods_btn = QPushButton("Модпаки", self.header_frame)
        self.tab_mods_btn.setGeometry(310, 5, 100, 30)
        self.tab_mods_btn.setStyleSheet(tabs_style_new)
        self.tab_mods_btn.setCheckable(True)
        self.tab_mods_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                            ))

        self.tab_installed_mods_btn = QPushButton("Установки", self.header_frame)
        self.tab_installed_mods_btn.setGeometry(420, 5, 100, 30)
        self.tab_installed_mods_btn.setStyleSheet(tabs_style_new)
        self.tab_installed_mods_btn.setCheckable(True)
        self.tab_installed_mods_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                                      ))

        self.tab_settings_btn = QPushButton("Настройки", self.header_frame)
        self.tab_settings_btn.setGeometry(530, 5, 100, 30)
        self.tab_settings_btn.setStyleSheet(tabs_style_new)
        self.tab_settings_btn.setCheckable(True)
        self.tab_settings_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                                ))

        self.separator_ending = QFrame(self.header_frame)
        self.separator_ending.setFrameShape(QFrame.Shape.VLine)
        self.separator_ending.setFrameShadow(QFrame.Shadow.Sunken)
        self.separator_ending.setStyleSheet("background-color: #777;")
        self.separator_ending.setFixedWidth(3)
        self.separator_ending.setFixedHeight(self.logo.height())
        self.separator_ending.setGeometry(self.tab_settings_btn.x() + self.tab_settings_btn.width() + 10, 8, 2, 24)

        self.close_btn = QPushButton("✕", self.header_frame)
        self.close_btn.setGeometry(ww - 40, 5, 30, 30)
        self.close_btn.setFont(QFont("sans-serif", 11, QFont.Weight.Bold))

        self.close_btn.setStyleSheet("""
                    QPushButton { background-color: transparent; color: red; border: none; }
                    QPushButton:hover { color: darkred; }
                """)
        # noinspection PyUnresolvedReferences
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
        # noinspection PyUnresolvedReferences
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
        self.container_frame.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.news_page = QScrollArea(self.container_frame)
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

        self.update_news([{'date': 'Загрузка... | Прокрутите ниже чтобы узнать больше', 'id': 1,
                           'text': 'Подождите, идет загрузка новостей с сервера.....\n' * 4,
                           'title': '    ----- Загрузка новостей... -----'}])
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

        title = QLabel("Про продукт тут")
        title.setFixedHeight(42)
        title.setStyleSheet("color: #ffffff; font-weight: bold; background: transparent;")
        title.setFont(QFont("sans-serif", 20))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay.addWidget(title)

        text = QTextBrowser()
        text.setFont(QFont("sans-serif", 13))
        text.setOpenExternalLinks(True)
        text.setStyleSheet("""
        QTextBrowser {
            background: transparent;
            border: none;
            color: #e0e0e0;
        }
        """)
        text.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # насрал политики
        text.setHtml("""
        <p>
        Лаунчер разработан командой игроков. В неё входят:
        </p>

        <ul>
        <li>Концепт, дизайн, логика, кодинг, 3D-Графика и сборка — <span style="color:#6cf">raizor</span></li>
        <li>API Очереди Практики — <span style="color:#6cf">__petryshka__</span></li>
        </ul>
        <p>А также, в ней раньше состояли следующие игроки:</p>
        <ul>
        <li>API Очереди Faceit — <span style="color:#6cf">furanixx  (До версии 3.0)</span></li>
        <li>Обои — <span style="color:#6cf">vladrompus  (До версии 4.0)</span></li>
        </ul>
        
        <p style="color:#aaa">
        Команда разработки не имеет никакого отношения к разработчикам проекта
        <span style="color:#ff7777">CounterMine2</span>.
        </p>

        <p style="color:#aaa">
        Все логотипы, дизайн, текстовая информация и графические изображения
        принадлежат непосредственно <b>CounterMine2</b>.
        </p>

        <p>
        Посетите
        <a href="https://cherry.pizza/legal/terms_of_service">Terms of Service</a>
        и
        <a href="https://cherry.pizza/legal/privacy_policy">Privacy Policy</a>,
        чтобы ознакомиться с политикой проекта.
        </p>

        <hr>

        <p><b>Политика использования данного продукта:</b></p>

        <ul>
        <li>Используя данный продукт, вы подтверждаете своё согласие с настоящим сводом правил.</li>
        <li>Вы соглашаетесь с тем, что данный продукт предоставляется «как есть», без каких-либо гарантий, явных или подразумеваемых.</li>
        <li>Вы обязуетесь не претендовать на какие-либо имущественные, интеллектуальные или иные права, связанные с данным продуктом.</li>
        <li>Вы обязуетесь не выдавать данный проект, полностью или частично, за результат собственной разработки.</li>
        <li>Запрещается модификация, декомпиляция, обратное проектирование или распространение продукта без явного разрешения команды разработки.</li>
        <li>Запрещается использование продукта в коммерческих целях, а также в целях, нарушающих действующее законодательство.</li>
        <li>Команда разработки оставляет за собой право в любой момент изменять функциональность продукта, условия его использования или прекратить его распространение без предварительного уведомления.</li>
        <li>Команда разработки не несёт ответственности за возможные убытки, потерю данных, блокировки аккаунтов или иные последствия, возникшие в результате использования продукта.</li>
        <li>Любое использование продукта после внесения изменений в настоящие правила означает автоматическое согласие с обновлённой редакцией.</li>
        </ul>

        <p style="color:#888; font-size:11px">
        Незнание правил не освобождает от ответственности. Используйте продукт осознанно.
        </p>
        """)

        card_lay.addWidget(text)

        back_btn = QPushButton("← Назад в настройки")
        back_btn.setFixedHeight(44)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #444;
                color: white;
                border-radius: 8px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #555; }
        """)
        back_btn.clicked.connect(lambda: self._switch_tab(2))
        card_lay.addWidget(back_btn)

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
        form_card2.setStyleSheet("background-color: rgba(50,50,50,160); border-radius:12px;")
        form_card2.setMinimumHeight(400)

        card_lay2 = QVBoxLayout(form_card2)
        card_lay2.setContentsMargins(30, 30, 30, 30)
        card_lay2.setSpacing(18)

        self.more_settings_title = QLabel("Настройки")
        self.more_settings_title.setFixedHeight(42)
        self.more_settings_title.setStyleSheet("color: #ffffff; font-weight: bold; background: transparent;")
        self.more_settings_title.setFont(QFont("sans-serif", 20))
        self.more_settings_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_lay2.addWidget(self.more_settings_title)

        snow_layout = QHBoxLayout()
        self.snow_label = QLabel("Показать Снежинки ❄")
        self.snow_label.setStyleSheet("color: #dddddd; font-size: 11pt; background: transparent;")
        self.snow_switch = SwitchButton()
        self.snow_switch.setFixedSize(52, 28)
        snow_layout.addWidget(self.snow_label)
        snow_layout.addStretch()
        snow_layout.addWidget(self.snow_switch)
        card_lay2.addLayout(snow_layout)

        update_layout = QHBoxLayout()
        self.update_label = QLabel("Проверять наличие обновлений")
        self.update_label.setStyleSheet("color: #dddddd; font-size: 11pt; background: transparent;")
        self.update_switch = SwitchButton()
        self.update_switch.setFixedSize(52, 28)
        update_layout.addWidget(self.update_label)
        update_layout.addStretch()
        update_layout.addWidget(self.update_switch)
        card_lay2.addLayout(update_layout)

        rpc_layout = QHBoxLayout()
        self.rpc_label = QLabel("Устанавливать статус в Discord")
        self.rpc_label.setStyleSheet("color: #dddddd; font-size: 11pt; background: transparent;")
        self.rpc_switch = SwitchButton()
        self.rpc_switch.setFixedSize(52, 28)
        rpc_layout.addWidget(self.rpc_label)
        rpc_layout.addStretch()
        rpc_layout.addWidget(self.rpc_switch)
        card_lay2.addLayout(rpc_layout)

        style_layout = QHBoxLayout()
        self.style_label = QLabel("Использовать новую цветовую тему")
        self.style_label.setStyleSheet("color: #dddddd; font-size: 11pt; background: transparent;")
        self.style_switch = SwitchButton()
        self.style_switch.setFixedSize(52, 28)
        style_layout.addWidget(self.style_label)
        style_layout.addStretch()
        style_layout.addWidget(self.style_switch)
        card_lay2.addLayout(style_layout)

        lang_layout = QHBoxLayout()
        self.lang_label = QLabel("Язык / Language")
        self.lang_label.setStyleSheet("color: #dddddd; font-size: 11pt; background: transparent;")
        self.lang_dropdown = DropDown(["Русский", "English"])
        lang_layout.setContentsMargins(0, 8, 0, 8)
        lang_layout.setSpacing(10)
        lang_layout.addWidget(self.lang_label)
        lang_layout.addStretch()
        lang_layout.addWidget(self.lang_dropdown)
        card_lay2.addLayout(lang_layout)

        # Для петрушки - подключаем все сигналы кнопок и переключателей настроек.
        # Для петрушки - Сигналы используем для того чтобы передавать данные между потоками

        try:
            self.style_switch.stateChanged.connect(
                lambda checked: self.settings_changed.emit("style", checked)
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
            self.snow_switch.stateChanged.connect(
                lambda checked: self.settings_changed.emit("snow", checked)
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

        card_lay2.addStretch()

        self.more_settings_back_btn = QPushButton("← Назад в настройки")
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
        self.more_settings_back_btn.clicked.connect(lambda: self._switch_tab(2))
        card_lay2.addWidget(self.more_settings_back_btn)

        form_layout2.addWidget(form_card2)
        form_layout2.addStretch()

        mods_container_layout = QVBoxLayout(self.mods_container)
        mods_container_layout.setContentsMargins(0, 0, 0, 0)
        self.mods_page = QScrollArea(self.mods_container)
        self.mods_page.setWidgetResizable(True)
        self.mods_page.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.mods_page.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.mods_page.setStyleSheet("background-color: transparent; border: none;")
        self.mods_content = QWidget(self.mods_page)
        self.mods_layout = QGridLayout(self.mods_content)
        self.mods_layout.setContentsMargins(10, 10, 10, 10)
        self.mods_layout.setSpacing(10)
        self.mods_page.setWidget(self.mods_content)
        mods_container_layout.addWidget(self.mods_page)

        self.mod_cards = {}
        self.mod_buttons = {}
        self.mod_labels = {}

        self._populate_mods([])

        # Для петрушки - подключаем кнопки переключения вкладок

        # noinspection PyUnresolvedReferences
        self.tab_news_btn.clicked.connect(lambda: self._switch_tab(0))
        # noinspection PyUnresolvedReferences
        self.tab_mods_btn.clicked.connect(lambda: self._switch_tab(1))
        # noinspection PyUnresolvedReferences
        self.tab_settings_btn.clicked.connect(lambda: self._switch_tab(2))
        # noinspection PyUnresolvedReferences
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
        self.buttons_block.setStyleSheet("background-color: rgba(50,50,50,140); border-radius:10px; padding:2px;")

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
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                  ))
            # noinspection PyUnresolvedReferences
            btn.clicked.connect(lambda checked=False, url=link: QDesktopServices.openUrl(QUrl(url)))
            btn.setStyleSheet("border:none; background-color: rgba(50,50,50,140); border-radius: 2px;")
            btn.setToolTip(str(icon.replace(".png", "")))

        self.cleanup_btn = QPushButton(self.buttons_block)
        self.cleanup_btn.setGeometry(12, block_height - 2 * button_size - spacing + 9, button_size, button_size)
        self.cleanup_btn.setIcon(QIcon(self.resource_path("assets/cleanup.png")))
        self.cleanup_btn.setIconSize(QSize(button_size, button_size))
        # noinspection PyUnresolvedReferences
        self.cleanup_btn.clicked.connect(lambda: self.cleanup_clicked.emit())
        self.cleanup_btn.setStyleSheet("border:none; background:#323232;")
        self.cleanup_btn.setToolTip("ОЧИСТИТЬ КЭШ")
        self.cleanup_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.reinstall_btn = QPushButton(self.buttons_block)
        self.reinstall_btn.setGeometry(12, block_height - button_size + 9, button_size, button_size)
        self.reinstall_btn.setIcon(QIcon(self.resource_path("assets/reinstall.png")))
        self.reinstall_btn.setIconSize(QSize(button_size, button_size))
        # noinspection PyUnresolvedReferences
        self.reinstall_btn.clicked.connect(lambda: self.reinstall_client.emit())
        self.reinstall_btn.setStyleSheet("border:none; background:#323232;")
        self.reinstall_btn.setToolTip("ПЕРЕУСТАНОВИТЬ КЛИЕНТ")
        self.reinstall_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                             ))

        self.waitlist = QWidget(self)
        self.waitlist.setFixedWidth(280)
        self.waitlist.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.waitlist.setStyleSheet("""
            QWidget {
                background-color: rgba(40, 40, 40, 100);
                border-radius: 10px;
                border: 1px solid rgba(255, 255, 255, 40);
            }
            QLabel { color: white; background: transparent; }
        """)

        wait_layout = QVBoxLayout(self.waitlist)
        wait_layout.setContentsMargins(15, 10, 15, 10)
        wait_layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self.faceit_title_label = QLabel("Очередь Faceit")
        self.faceit_title_label.setStyleSheet("font-weight: bold; font-size: 13pt; color: #f0f0f0;border: 0px; background: transparent;")
        header_layout.addWidget(self.faceit_title_label)
        header_layout.addStretch()

        self.toggle_faceit_btn = QPushButton("−")
        self.toggle_faceit_btn.setFixedSize(28, 28)
        self.toggle_faceit_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,15);
                color: white;
                border: none;
                border-radius: 14px;
                font-weight: bold;
                font-size: 16pt;
            }
            QPushButton:hover { background: rgba(255,255,255,35); }
        """)
        self.toggle_faceit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                                 ))
        header_layout.addWidget(self.toggle_faceit_btn)
        wait_layout.addLayout(header_layout)

        self.faceit_content = QWidget()
        self.faceit_content.setStyleSheet("background: transparent; border: 0px;")
        faceit_content_layout = QVBoxLayout(self.faceit_content)
        faceit_content_layout.setContentsMargins(0, 5, 0, 10)
        faceit_content_layout.setSpacing(8)

        self.names_label = QLabel(
            "Фураникс не оплатил хост. А нам лень убирать данный блок. Так что мы разместим здесь бананчика вованчика")
        self.names_label.setStyleSheet("color: #dddddd; font-size: 10pt;border: 0px;  background: transparent;")
        self.names_label.setWordWrap(True)
        faceit_content_layout.addWidget(self.names_label)

        img = QLabel()
        pix = QPixmap(self.resource_path("assets/bananvovan.png"))
        pix = pix.scaledToWidth(200, Qt.TransformationMode.SmoothTransformation)
        img.setPixmap(pix)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img.setStyleSheet("border: 0px;")
        faceit_content_layout.addWidget(img)

        self.counter_label = QLabel("Без обид бананчик, мы тебя любим ❤")
        self.counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.counter_label.setStyleSheet("color: #aaaaaa; font-size: 10pt;border: 0px;  background: transparent;")
        faceit_content_layout.addWidget(self.counter_label)

        wait_layout.addWidget(self.faceit_content)

        self.faceit_expanded = False
        self.faceit_content.setVisible(False)
        self.toggle_faceit_btn.setText("+")
        self.waitlist.setMinimumHeight(56)
        self.waitlist.setMaximumHeight(56)
        self.waitlist.setFixedHeight(56)

        self.toggle_faceit_btn.clicked.connect(self.toggle_faceit_queue)

        margin_x = 25
        x_pos = self.header_frame.width() - 280 - margin_x - self.buttons_block.width() - 20
        y_pos = self.buttons_block.y()
        self.waitlist.move(x_pos, y_pos)
        self.waitlist.setFixedHeight(56)
        self.waitlist.raise_()
        self.waitlist.hide()

        shadow1 = QGraphicsDropShadowEffect()
        shadow1.setBlurRadius(22)
        shadow1.setOffset(0, 4)
        shadow1.setColor(QColor(0, 0, 0, 200))
        self.waitlist.setGraphicsEffect(shadow1)

        self.practice_widget = QWidget(self)
        self.practice_widget.setFixedWidth(280)
        self.practice_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.practice_widget.setStyleSheet(self.waitlist.styleSheet())

        prac_layout = QVBoxLayout(self.practice_widget)
        prac_layout.setContentsMargins(15, 10, 15, 10)
        prac_layout.setSpacing(8)

        prac_header = QHBoxLayout()
        prac_header.setContentsMargins(0, 0, 0, 0)
        prac_header.setSpacing(8)

        self.prac_title = QLabel("Очередь Практики")
        self.prac_title.setStyleSheet("font-weight: bold; font-size: 13pt; color: #f0f0f0;border: 0px;")
        prac_header.addWidget(self.prac_title)
        prac_header.addStretch()

        self.toggle_prac_btn = QPushButton("−")
        self.toggle_prac_btn.setFixedSize(28, 28)
        self.toggle_prac_btn.setStyleSheet(self.toggle_faceit_btn.styleSheet())
        self.toggle_prac_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                               ))
        prac_header.addWidget(self.toggle_prac_btn)
        prac_layout.addLayout(prac_header)

        self.prac_content = QWidget()
        self.prac_content.setStyleSheet("background: transparent; border: 0px;")
        prac_content_layout = QVBoxLayout(self.prac_content)
        prac_content_layout.setContentsMargins(0, 8, 0, 10)
        prac_content_layout.setSpacing(6)

        self.prac_header_label = QLabel("Никто из команд не ищет прак")
        self.prac_header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.prac_header_label.setStyleSheet("color: #cccccc; font-size: 12pt;border: 0px;  background: transparent;")
        self.prac_header_label.setWordWrap(True)
        prac_content_layout.addWidget(self.prac_header_label)

        self.prac_status_label = QLabel("Сейчас нету активных праков")
        self.prac_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.prac_status_label.setStyleSheet("color: #999999; font-size: 11pt;border: 0px;  background: transparent;")
        self.prac_status_label.setWordWrap(True)
        prac_content_layout.addWidget(self.prac_status_label)

        prac_layout.addWidget(self.prac_content)

        self.prac_expanded = True
        self.toggle_prac_btn.clicked.connect(self.toggle_practice_widget)

        self.practice_widget.setMinimumHeight(140)
        self.practice_widget.setMaximumHeight(500)
        self.update_practice_position()
        self.practice_widget.raise_()

        shadow2 = QGraphicsDropShadowEffect()
        shadow2.setBlurRadius(22)
        shadow2.setOffset(0, 4)
        shadow2.setColor(QColor(0, 0, 0, 200))
        self.practice_widget.setGraphicsEffect(shadow2)

        self.waitlist.setMinimumHeight(56)
        self.waitlist.setMaximumHeight(400)

        ofw, ofh = 231, 64
        self.online_frame = QFrame(self)
        self.online_frame.setGeometry(28, self.height() - ofh - 10, ofw, ofh)
        self.online_frame.setStyleSheet("background-color: rgba(50,50,50,190); border-radius:8px;")
        online_layout = QHBoxLayout(self.online_frame)
        online_layout.setContentsMargins(10, 5, 10, 5)
        online_layout.setSpacing(15)

        self.online_gif_label = QLabel(self.online_frame)
        self.static_pixmap = QPixmap(self.resource_path("assets/online_static.png")).scaled(55, 50)
        self.movie = QMovie(self.resource_path("assets/online_animation.gif"))
        self.movie.setScaledSize(QSize(55, 50))

        self.online_gif_label.setStyleSheet("background: transparent;")


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
        self.online_label.setStyleSheet("color:white; font-weight:bold; background: transparent;")
        self.online_label.setFont(QFont("sans-serif", 11))
        online_layout.addWidget(self.online_label)

        pifw, pifh = 80, 64
        self.ping_frame = QFrame(self)
        self.ping_frame.setGeometry(268, self.height() - pifh - 10, pifw, pifh)
        self.ping_frame.setStyleSheet("background-color: rgba(50,50,50,190); border-radius:8px; ")
        ping_layout = QHBoxLayout(self.ping_frame)
        ping_layout.setContentsMargins(10, 5, 10, 5)
        ping_layout.setSpacing(15)

        self.ping_label = QLabel(f"- {t(self.lang, 'ms_locale')}", self.ping_frame)
        self.ping_label.setStyleSheet("color:white; font-weight:bold; background: transparent;")
        self.ping_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self.play_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor
                                        ))
        self.play_btn.setFont(QFont("sans-serif", 13, QFont.Weight.Bold))
        self.play_btn.setStyleSheet("""
            QPushButton { background-color: #45A049; color:white; border-radius:10px; }
            QPushButton:hover:!disabled { background-color: #45a800; }
            QPushButton:disabled { background-color:#2e6b35; color:#aaa; }
        """)
        # noinspection PyUnresolvedReferences
        self.play_btn.clicked.connect(self.play_clicked.emit)
        self.play_frame.raise_()

    def update_faceit_height(self):
        if not self.faceit_expanded:
            return

        target_height = self.waitlist.sizeHint().height()
        target_height = max(target_height, 120)

        self.waitlist.setMinimumHeight(target_height)
        self.waitlist.setMaximumHeight(target_height)

        self.update_practice_position()

    def toggle_faceit_queue(self):
        self.faceit_expanded = not self.faceit_expanded
        self.faceit_content.setVisible(self.faceit_expanded)
        self.toggle_faceit_btn.setText("−" if self.faceit_expanded else "+")

        if self.faceit_expanded:
            target_faceit_height = max(self.waitlist.sizeHint().height(), 120)

            self.prac_expanded = False
            self.prac_content.setVisible(self.prac_expanded)
            self.toggle_prac_btn.setText("−" if self.prac_expanded else "+")
            self.update_practice_position()

        else:
            target_faceit_height = 56
            self.prac_expanded = True
            self.prac_content.setVisible(self.prac_expanded)
            self.toggle_prac_btn.setText("−" if self.prac_expanded else "+")
            self.update_practice_position()

        gap = 12
        target_practice_y = self.waitlist.y() + target_faceit_height + gap

        self.anim_practice_y = QPropertyAnimation(self.practice_widget, b"pos")
        self.anim_practice_y.setDuration(260)
        self.anim_practice_y.setStartValue(self.practice_widget.pos())
        self.anim_practice_y.setEndValue(QPoint(self.practice_widget.x(), target_practice_y))
        self.anim_practice_y.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.anim_height1 = QPropertyAnimation(self.waitlist, b"minimumHeight")
        self.anim_height1.setDuration(260)
        self.anim_height1.setStartValue(self.waitlist.height())
        self.anim_height1.setEndValue(target_faceit_height)
        self.anim_height1.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.anim_height2 = QPropertyAnimation(self.waitlist, b"maximumHeight")
        self.anim_height2.setDuration(260)
        self.anim_height2.setStartValue(self.waitlist.maximumHeight())
        self.anim_height2.setEndValue(target_faceit_height)
        self.anim_height2.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.anim_height1.start()
        self.anim_height2.start()
        self.anim_practice_y.start()

    def toggle_practice_widget(self):
        self.prac_expanded = not self.prac_expanded

        self.toggle_prac_btn.setText("−" if self.prac_expanded else "+")

        if self.prac_expanded:
            target_h = max(140, self.practice_widget.sizeHint().height())
            min_h = 140
            max_h = 800
        else:
            target_h = 56
            min_h = 56
            max_h = 56

        self.anim_height1_prac = QPropertyAnimation(self.practice_widget, b"minimumHeight")
        self.anim_height1_prac.setDuration(260)
        self.anim_height1_prac.setStartValue(self.practice_widget.height())
        self.anim_height1_prac.setEndValue(min_h)
        self.anim_height1_prac.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.anim_height2_prac = QPropertyAnimation(self.practice_widget, b"maximumHeight")
        self.anim_height2_prac.setDuration(260)
        self.anim_height2_prac.setStartValue(self.practice_widget.maximumHeight())
        self.anim_height2_prac.setEndValue(max_h)
        self.anim_height2_prac.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.anim_height3_prac = QPropertyAnimation(self.prac_content, b"maximumHeight")
        self.anim_height3_prac.setDuration(260)
        self.anim_height3_prac.setStartValue(self.prac_content.maximumHeight())
        self.anim_height3_prac.setEndValue(0 if not self.prac_expanded else 300)
        self.anim_height3_prac.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.anim_height1_prac.start()
        self.anim_height2_prac.start()
        self.anim_height3_prac.start()

    def update_practice_position(self):
        base_y = self.waitlist.y()
        gap = 12
        new_y = base_y
        self.practice_widget.move(self.waitlist.x(), new_y)

        if self.prac_expanded:
            self.practice_widget.setMinimumHeight(125)
            self.practice_widget.setMaximumHeight(300)
            # self.practice_widget.adjustSize()
        else:
            self.practice_widget.setFixedHeight(56)

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
        self.about_title.setStyleSheet("color: white; font-weight: bold; background: transparent;")
        self.about_title.setFont(QFont("sans-serif", 16))
        self.about_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.about_title)

        about_main_text = (
            "Лаунчер CounterMine2 - это неофициальный лаунчер проекта CounterMine2. "
            "В лаунчере не было и не будет рекламы, так что проект остается полностью неоплачиваемым.\n\n"
        )
        self.main_label = QLabel(about_main_text)
        self.main_label.setStyleSheet("color: #dddddd; font-size: 12pt; background: transparent;")
        self.main_label.setFont(QFont("sans-serif", 10))
        self.main_label.setWordWrap(True)
        self.main_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.main_label)

        self.more_title2 = QLabel("Настройки")
        self.more_title2.setStyleSheet("color: white; font-weight: bold; background: transparent;")
        self.more_title2.setFont(QFont("sans-serif", 13))
        self.more_title2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.more_title2)

        self.more_btn = QPushButton("Перейти →")
        self.more_btn.setFixedHeight(42)
        self.more_btn.setStyleSheet("""
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
                    """)
        self.more_btn.clicked.connect(lambda: self._switch_to_moresettings_page())

        layout.addWidget(self.more_btn)

        self.more_title = QLabel("Всякие интересные штуки")
        self.more_title.setStyleSheet("color: white; font-weight: bold; background: transparent;")
        self.more_title.setFont(QFont("sans-serif", 13))
        self.more_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.more_title)

        self.formalities_btn = QPushButton("Перейти →")
        self.formalities_btn.setFixedHeight(42)
        self.formalities_btn.setStyleSheet("""
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
                    """)
        self.formalities_btn.clicked.connect(lambda: self._switch_to_formalities_page())
        layout.addWidget(self.formalities_btn)

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
        self.information_container.setVisible(True)
        self.tab_settings_btn.setChecked(True)

    def _switch_to_moresettings_page(self):
        self.settings_container.setVisible(False)
        self.dim_layer.setVisible(True)
        self.moresettings_container.setVisible(True)
        self.tab_settings_btn.setChecked(True)

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
            pix = QPixmap(self.resource_path("assets/cherry.png")).scaled(22, 22, Qt.AspectRatioMode.KeepAspectRatio,
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
        </svg>'''  # тупо с сайта черепицы взял свгшку
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
        if user_data:
            self.auth_logged_in_frame.show()
            self.stats_container.show()
            self.auth_logged_out_frame.hide()

            nick = user_data.get("nickname", "Player")
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

    def _switch_tab(self, index):
        try:
            self.container_frame.setVisible(index == 0)
            self.mods_container.setVisible(index == 1)
            self.settings_container.setVisible(index == 2)
            self.installed_mods_container.setVisible(index == 3)
            self.tab_news_btn.setChecked(index == 0)
            self.tab_mods_btn.setChecked(index == 1)
            self.tab_settings_btn.setChecked(index == 2)
            self.tab_installed_mods_btn.setChecked(index == 3)
            self.ping_frame.setVisible(index == 0)
            self.play_frame.setVisible(index == 0)
            self.online_frame.setVisible(index == 0)
            self.practice_widget.setVisible(index == 0)
            self.information_container.setVisible(False)
            self.moresettings_container.setVisible(False)
            try:
                if index == 0:
                    self.waitlist.setVisible(False)
                    if hasattr(self, 'media_player'):
                        self.container_frame.raise_()

                    if hasattr(self, 'video_widget'):
                        self.video_widget.show()
                        self.video_widget.lower()
                else:
                    self.waitlist.setVisible(False)
                    if hasattr(self, 'video_widget'):
                        self.video_widget.hide()

                for i in range(self.container_layout.count()):
                    page = self.container_layout.widget(i)
                    page.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
                    page.setAutoFillBackground(False)

            except Exception as e:
                print(e)

            self.buttons_block.setVisible(index == 0)
            self.dim_layer.setVisible(index in (1, 2, 3))

            self.container_frame.raise_()
            if index == 0:
                self.news_page.raise_()
                self.fade_overlay.raise_()
            elif index == 3:
                self._populate_installed_mods()

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
                                    # We keep the slug guess for Modrinth actions,
                                    # but the ID from JSON might be more accurate for local ID
                                    json_id = data.get("id")
                                    if json_id:
                                        mod_info["mod_id"] = json_id
                    except Exception as e:
                        print(f"Error reading mod {file}: {e}")

                    # Try to match with modrinth data if available
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
        if item_type == "mod":
            self.mod_action.emit(filename if filename else slug, "remove")

    def update_ui(self, lang):
        self.lang = lang
        self.tab_news_btn.setText(t(lang, "tabs_home"))
        self.tab_mods_btn.setText(t(lang, "tabs_mods"))
        self.tab_installed_mods_btn.setText(t(lang, "tabs_installed_mods"))
        self.tab_settings_btn.setText(t(lang, "tabs_information"))

        self.about_title.setText(t(lang, "about_title"))
        self.reinstall_btn.setToolTip(t(lang, "reinstall_btn_tooltip"))
        self.cleanup_btn.setToolTip(t(lang, "cleanup_title"))
        self.main_label.setText(t(lang, "about_text"))
        self.tech_info_label.setText(f"version: {self.version} by raizor")

        self.settings_title.setText(t(lang, "settings_title"))
        self.update_label.setText(t(lang, "updates"))
        self.rpc_label.setText(t(lang, "rpc"))
        self.snow_label.setText(t(lang, "snow_label"))
        self.style_label.setText(t(lang, "style_label"))
        self.lang_label.setText(t(lang, "lang_label"))
        self.more_settings_title.setText(t(lang, "tabs_information"))
        self.more_settings_back_btn.setText(t(lang, "back_btn"))

        self.search_edit.setPlaceholderText(t(lang, "mod_search"))
        self.more_title2.setText(t(lang, "more_settings_header"))
        self.more_btn.setText(t(lang, "more_btn_text"))
        self.more_title.setText(t(lang, "extra_info_header"))
        self.formalities_btn.setText(t(lang, "more_btn_text"))
        self.auth_login_label.setText(t(lang, "login_btn"))
        self.logout_menu_btn.setText(t(lang, "logout_btn"))
        self.installed_edit.setPlaceholderText(t(lang, "installed_mods_text"))

        self.reinstall_btn.setToolTip(t(lang, "reinstall_btn_tooltip"))

        self.play_btn.setText(t(lang, "play_button"))

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
            self.ping_frame.setStyleSheet("background-color: rgba(50,50,50,190); border-radius:8px;")
            return
        if ping_value < 65:
            color = "rgba(69,168,0,190)"
        elif ping_value < 100:
            color = "rgba(255,204,0,190)"
        else:
            color = "rgba(211,47,47,190)"

        self.ping_frame.setStyleSheet(f"background-color:{color}; border-radius:8px;")

    def update_news(self, news_list: list):
        while self.news_layout.count():
            item = self.news_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.news_data = news_list

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

        try:
            mods_container_layout.insertWidget(0, search_widget)
            self.search_timer = QTimer()
            self.search_timer.setSingleShot(True)
            self.search_timer.timeout.connect(self._perform_search)
            self.search_edit.textChanged.connect(lambda text: self.search_timer.start(500))

            self.search_timer.start(50)  # Для петрушки - сразу грузим популярные моды
        except Exception as e:
            print(e)

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

        installed_mods_container_layout.insertWidget(0, installed_widget)

    def _perform_search(self):
        try:
            if hasattr(self, 'thread') and self.thread is not None:
                try:
                    if self.thread.isRunning():
                        if hasattr(self, 'worker') and self.worker:
                            self.worker.stop()
                            try:
                                self.worker.finished.disconnect()
                            except:
                                pass
                        self.thread.quit()
                except RuntimeError:
                    self.thread = None
                    self.worker = None

            query = self.search_edit.text().strip()
            index = "downloads" if not query else "relevance"
            self.worker = ModSearchWorker(query, index)
            self.thread = QThread()
            self.worker.moveToThread(self.thread)
            self.thread.started.connect(self.worker.run)
            self.worker.finished.connect(self._on_search_finished)
            self.worker.finished.connect(self.thread.quit)
            self.worker.finished.connect(self.worker.deleteLater)
            self.thread.finished.connect(self.thread.deleteLater)
            self.thread.finished.connect(self._clear_search_refs)
            self.thread.start()
        except Exception as e:
            print(e)

    def _clear_search_refs(self):
        self.thread = None
        self.worker = None

    def _on_search_finished(self, mods_data):
        self.mods_data = mods_data
        self._clear_mods()
        self._populate_mods(self.mods_data)

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
                    if hit['title'] not in banned_mods and "Xaero's" not in hit['title'] and "Xaero" not in hit[
                        'title']:
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
