import threading
import requests
from PyQt6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, QTimer, QSize
from PyQt6.QtGui import QCursor, QColor, QPixmap, QPalette, QGuiApplication, QPainter, QBrush, QPainterPath, QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect, QApplication
from scripts.plugin_manager import BasePlugin
from scripts.utilties import t
import PyQt6.QtCore as QtCore
from PyQt6 import QtGui, QtWidgets

translations = {
    "ru_ru": {
        "ranked_plugin_name": "Ranked Queue",
        "ranked_plugin_description": "Интеграция очереди Ranked",
        "ranked_queue_title": "Очередь Ranked",
        "ranked_queue_remaining_1": "Остался 1 игрок для начала",
        "ranked_queue_remaining_2_4": "Осталось {count} игрока для начала",
        "ranked_queue_remaining_5_plus": "Осталось {count} игроков для начала",
        "ranked_sound_notification": "Звук уведомления Ranked",
        "ranked_match_starting": "МАТЧ НАЧИНАЕТСЯ",
    },
    "en_us": {
        "ranked_plugin_name": "Ranked Queue",
        "ranked_plugin_description": "Ranked Queue Integration",
        "ranked_queue_title": "Ranked Queue",
        "ranked_queue_remaining_1": "1 player remaining to start",
        "ranked_queue_remaining_2_4": "{count} players remaining to start",
        "ranked_queue_remaining_5_plus": "{count} players remaining to start",
        "ranked_sound_notification": "Ranked Notification Sound",
        "ranked_match_starting": "MATCH IS STARTING",
    }
}

def t(lang, key):
    return translations.get(lang, {}).get(key, key)

QUEUE_URL = "http://185.246.223.118:25593/ranked/api"

class QueueFetcher(QtCore.QObject):
    queueFetched = QtCore.pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.lang = "en_us"
        self.in_game = False
        self._stop_event = threading.Event()
        self._session = None
        self._threads = []

    def fetch_queue_async(self):
        thread = threading.Thread(target=self._run_queue, daemon=True)
        thread.start()
        self._threads.append(thread)

    def _safe_request(self, method, url, **kwargs):
        if not self._session:
            self._session = requests.Session()
            self._session.headers.update({'Connection': 'close'})
        try:
            resp = self._session.request(method, url, **kwargs)
            return resp
        except Exception as e:
            print(f"[Fetcher] Request to {url} failed: {e}. Resetting session connection pool.")
            if self._session:
                try:
                    self._session.close()
                except:
                    pass
                self._session = None
            raise e
            
    def _run_queue(self):
        while not self._stop_event.is_set():
            if not self.in_game:
                try:
                    resp = self._safe_request(
                        "POST",
                        QUEUE_URL,
                        json={"action": "queue5vs5"},
                        headers={'User-Agent': 'CounterMine2-Launcher/5.0'},
                        timeout=5
                    )

                    if resp.status_code == 200:
                        data = resp.json()
                        players = data.get("ru", [])
                        names = []
                        for p in players:
                            nick = p.get("minecraft_nick")
                            rating = p.get("rating", "—")
                            if nick:
                                names.append((str(nick).strip(), str(rating).strip()))
                    else:
                        names = []

                except Exception as e:
                    names = ["error"*10]
                    print(f"[Fetcher] Queue Error: {e}")

                names.sort(key=lambda x: x[0] if isinstance(x[0], (str)) else 0, reverse=False)
                self.queueFetched.emit(names)

                if self._stop_event.wait(3):
                    break
            else:
                if self._stop_event.wait(1):
                    break

class RankedToggleButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._angle = 0
        self._scale = 1.0
        self._textColor = QColor("white")
        self.is_collapsed_mode = False
        
        self.scale_anim = QPropertyAnimation(self, b"buttonScale")
        self.scale_anim.setDuration(200)
        self.scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self.rot_anim = QPropertyAnimation(self, b"buttonRotation")
        self.rot_anim.setDuration(800)
        self.rot_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    @QtCore.pyqtProperty(float)
    def buttonScale(self): return self._scale
    @buttonScale.setter
    def buttonScale(self, v): self._scale = v; self.update()

    @QtCore.pyqtProperty(float)
    def buttonRotation(self): return self._angle
    @buttonRotation.setter
    def buttonRotation(self, v): self._angle = v % 360; self.update()

    def animate_rotation(self, collapsed):
        self.rot_anim.stop()
        current = self._angle % 360
        target = 180 if collapsed else 0
        delta = ((target - current + 540) % 360) - 180
        if abs(delta) < 0.1:
            self.buttonRotation = target
            return
        self.rot_anim.setStartValue(current)
        self.rot_anim.setEndValue(current + delta)
        self.rot_anim.start()

    @QtCore.pyqtProperty(QColor)
    def textColor(self): return self._textColor
    @textColor.setter
    def textColor(self, color): self._textColor = color; self.update()

    def enterEvent(self, event):
        if self.is_collapsed_mode:
            self.scale_anim.stop()
            self.scale_anim.setEndValue(1.2)
            self.scale_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.scale_anim.stop()
        self.scale_anim.setEndValue(1.0)
        self.scale_anim.start()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2
        painter.translate(cx, cy)
        painter.rotate(self._angle)
        painter.scale(self._scale, self._scale)
        painter.translate(-cx, -cy)
        opacity = 35 if self.underMouse() else 15
        painter.setBrush(QColor(255, 255, 255, opacity))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
        painter.setPen(self._textColor)
        font = QFont("sans-serif", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())

class RankedPlugin(BasePlugin):
    name = "Ranked Queue"
    description = "Интеграция очереди Ranked"
    author = "raizor"
    version = "1.0.0"
    icon = "assets/pixmaps/ranked.png"

    def on_load(self):
        self.name = t(self.app.lang, "ranked_plugin_name")
        self.description = t(self.app.lang, "ranked_plugin_description")
        self.occupied_last = None
        self.faceit_expanded = True
        self.prac_expanded = False
        self.notif = None
        self.last_queue_names = []

    def on_ui_ready(self):
        ui = self.app.ui
        self.waitlist = QWidget(ui)
        ui.waitlist = self.waitlist
        self.waitlist.setMinimumSize(0, 0)

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
        self.faceit_title_label = QLabel(t(self.app.lang, "ranked_queue_title"))
        self.faceit_title_label.setStyleSheet("font-weight: bold; font-size: 13pt; color: #f0f0f0; border: 0px;")
        header_layout.addWidget(self.faceit_title_label)
        header_layout.addStretch()

        self.toggle_faceit_btn = RankedToggleButton("−", self.waitlist) # Symbol, no translation needed
        self.toggle_faceit_btn.setFixedSize(28, 28)
        self.toggle_faceit_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        header_layout.addWidget(self.toggle_faceit_btn)
        wait_layout.addLayout(header_layout)

        self.faceit_content = QWidget()
        self.faceit_content.setStyleSheet("background: transparent; border: 0px;")
        faceit_content_layout = QVBoxLayout(self.faceit_content)
        
        self.queue_label = QLabel(self.get_queue_string(0, 10)) # This is dynamic, will be updated by update_ui_elements
        self.queue_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.queue_label.setStyleSheet("font-size: 13pt; letter-spacing: -1px;")
        faceit_content_layout.addWidget(self.queue_label)

        self.names_label = QLabel("")
        self.names_label.setStyleSheet("color: #dddddd; font-size: 10pt;")
        self.names_label.setTextFormat(Qt.TextFormat.RichText)
        faceit_content_layout.addWidget(self.names_label)

        self.counter_label = QLabel() # This is dynamic, will be updated by update_ui_elements
        self.counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.counter_label.setStyleSheet("color: #aaaaaa; font-size: 10pt;")
        faceit_content_layout.addWidget(self.counter_label)
        
        wait_layout.addWidget(self.faceit_content)
        
        margin_right = ui.buttons_block.width() + 30
        margin_top = 60
        self.waitlist.setGeometry(ui.width() - 280 - margin_right, margin_top, 280, 140)

        self.waitlist.setVisible(ui.tab_news_btn.isChecked())

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(22); shadow.setOffset(0, 4); shadow.setColor(QColor(0, 0, 0, 200))
        self.waitlist.setGraphicsEffect(shadow)

        self.toggle_faceit_btn.clicked.connect(self.toggle_faceit_queue)
        self.fetcher = QueueFetcher()
        self.fetcher.queueFetched.connect(self.on_queue_update)
        self.fetcher.fetch_queue_async()

        self.add_sound_setting()
        self.update_ui_texts(self.app.lang) 

    def on_language_change(self, lang):
        self.name = t(lang, "ranked_plugin_name")
        self.description = t(lang, "ranked_plugin_description")
        self.update_ui_texts(lang)

    def update_ui_texts(self, lang):
        if hasattr(self, 'faceit_title_label'):
            self.faceit_title_label.setText(t(lang, "ranked_queue_title"))
        if hasattr(self, 'sound_label'):
            self.sound_label.setText(t(lang, "ranked_sound_notification"))
        self.fetcher.fetch_queue_async() # Re-fetch to update dynamic labels

    def add_sound_setting(self):
        ui = self.app.ui
        if not hasattr(ui, 'plugin_settings_layout'):
            return

        from scripts.utilties import SwitchButton
        sound_layout = QHBoxLayout()
        self.sound_label = QLabel(t(self.app.lang, "ranked_sound_notification"))
        self.sound_label.setStyleSheet("color: #dddddd; font-size: 11pt; background: transparent;")
        sound_switch = SwitchButton()
        sound_switch.setOnColor("#fbac18")
        sound_switch.setChecked(self.app.sound_enabled)
        sound_switch.stateChanged.connect(lambda checked: self.app.on_settings_changed("sound_enabled", checked))
        sound_layout.addWidget(self.sound_label)
        sound_layout.addStretch()
        sound_layout.addWidget(sound_switch)
        ui.plugin_settings_layout.addLayout(sound_layout)
        ui.plugin_settings_separator.setVisible(True)

    def toggle_faceit_queue(self):
        self.faceit_expanded = not self.faceit_expanded
        self.toggle_faceit_btn.is_collapsed_mode = not self.faceit_expanded
        self.toggle_faceit_btn.animate_rotation(not self.faceit_expanded)
        self.toggle_faceit_btn.setText("−" if self.faceit_expanded else "+")
        self._run_toggle_animation()

    def _run_toggle_animation(self):
        ui = self.app.ui
        margin_right = ui.buttons_block.width() + 30
        margin_top = 60
        expanded_w = 280
        collapsed_w = 56
        collapsed_h = 56
        self._toggle_anim_token = getattr(self, '_toggle_anim_token', 0) + 1
        token = self._toggle_anim_token
        
        if hasattr(self, 'anim_group') and self.anim_group.state() == QtCore.QAbstractAnimation.State.Running:
            self.anim_group.stop()

        self.anim_group = QtCore.QSequentialAnimationGroup()

        if not self.faceit_expanded:
            anim_h = QPropertyAnimation(self.waitlist, b"geometry")
            anim_h.setDuration(200)
            anim_h.setStartValue(self.waitlist.geometry())
            anim_h.setEndValue(QtCore.QRect(ui.width() - expanded_w - margin_right, margin_top, expanded_w, collapsed_h))
            
            anim_w = QPropertyAnimation(self.waitlist, b"geometry")
            anim_w.setDuration(200)
            anim_w.setStartValue(QtCore.QRect(ui.width() - expanded_w - margin_right, margin_top, expanded_w, collapsed_h))
            anim_w.setEndValue(QtCore.QRect(ui.width() - collapsed_w - margin_right, margin_top, collapsed_w, collapsed_h))
            
            self.anim_group.addAnimation(anim_h)
            self.anim_group.addAnimation(anim_w)

            anim_h.finished.connect(lambda: self.faceit_content.hide())
            anim_w.finished.connect(lambda: self.faceit_title_label.hide())
            anim_w.finished.connect(self.toggle_faceit_btn.raise_)
        else:
            self.faceit_title_label.show()
            self.faceit_content.show()
            self.waitlist.layout().activate()
            final_h = max(self.waitlist.sizeHint().height(), 140)
            
            anim_w = QPropertyAnimation(self.waitlist, b"geometry")
            anim_w.setDuration(200)
            anim_w.setStartValue(self.waitlist.geometry())
            anim_w.setEndValue(QtCore.QRect(ui.width() - expanded_w - margin_right, margin_top, expanded_w, collapsed_h))
            
            anim_h = QPropertyAnimation(self.waitlist, b"geometry")
            anim_h.setDuration(200)
            anim_h.setStartValue(QtCore.QRect(ui.width() - expanded_w - margin_right, margin_top, expanded_w, collapsed_h))
            anim_h.setEndValue(QtCore.QRect(ui.width() - expanded_w - margin_right, margin_top, expanded_w, final_h))
            
            self.anim_group.addAnimation(anim_w)
            self.anim_group.addAnimation(anim_h)
            
            self.toggle_faceit_btn.raise_()

        def finalize(token=token):
            if token != self._toggle_anim_token:
                return
            if self.faceit_expanded:
                self.faceit_title_label.show()
                self.faceit_content.show()
                self.waitlist.layout().activate()
                final_h = max(self.waitlist.sizeHint().height(), 140)
                self.waitlist.setGeometry(ui.width() - expanded_w - margin_right, margin_top, expanded_w, final_h)
            else:
                self.faceit_content.hide()
                self.faceit_title_label.hide()
                self.waitlist.setGeometry(ui.width() - collapsed_w - margin_right, margin_top, collapsed_w, collapsed_h)
            self.toggle_faceit_btn.raise_()

        self.anim_group.finished.connect(finalize)
        self.anim_group.start()

    def on_queue_update(self, names):
        occupied = len(names)
        current_user_nickname = self.app.nickname

        if names and names[0][0] == "error"*10:
            occupied = 0
            names = []
            self.counter_label.hide()
            self.queue_label.hide()
            
        if occupied == 0 and len(self.last_queue_names) == 9 and current_user_nickname:
            was_in_queue = any(
                name.lower() == current_user_nickname.lower() for name, rating in self.last_queue_names
            )
            if was_in_queue:
                self._show_match_notification()

        self.last_queue_names = names
        self.update_ui_elements(occupied, names)

    def update_ui_elements(self, occupied, names):
        self.queue_label.setText(self.get_queue_string(occupied, 10))
        
        remaining = 10 - occupied
        if remaining == 1:
            text = t(self.app.lang, "ranked_queue_remaining_1")
        elif 2 <= remaining <= 4:
            text = t(self.app.lang, "ranked_queue_remaining_2_4").format(count=remaining)
        else:
            text = t(self.app.lang, "ranked_queue_remaining_5_plus").format(count=remaining)

        self.counter_label.setText(text)

        try:
            safe = [(name, elo) for name, elo in names if isinstance(name, str) and name.strip()]
        except ValueError:
            safe = []
        html = '<table style="width:100%;">'  
        for i, (name, elo) in enumerate(safe[:occupied]):
            html += f'<tr><td style="text-align:left;">{i+1}. {name}</td><td style="text-align:right;">🏆{elo}</td></tr>'
        html += '</table>'
        self.names_label.setText(html)
        
        if self.faceit_expanded:
            QtCore.QTimer.singleShot(0, self._adjust_waitlist_height)  

    def _adjust_waitlist_height(self):
        if not self.faceit_expanded:
            return
        if hasattr(self, 'anim_group') and self.anim_group.state() == QtCore.QAbstractAnimation.State.Running:
            return
            
        ui = self.app.ui
        self.waitlist.layout().activate()
        h = max(self.waitlist.sizeHint().height(), 140)
        w = 280
        margin_right = ui.buttons_block.width() + 30
        margin_top = 60
        self.waitlist.setGeometry(ui.width() - w - margin_right, margin_top, w, h)

    def get_queue_string(self, occ, total):
        return "🟢" * occ + "⚪" * (total - occ)

    def _show_match_notification(self):
        if self.notif: self.notif.close()  

        self.notif = QWidget()
        self.notif.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.notif.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.notif.setFixedSize(330, 80)

        label = QLabel(t(self.app.lang, "ranked_match_starting"), self.notif)
        label.setGeometry(0, 0, 300, 80)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("background-color: rgba(40, 40, 40, 220); border-radius: 10px; font-size: 24px; font-weight: bold; color: white;")

        close_btn = QPushButton("✕", self.notif)
        close_btn.setGeometry(275, 25, 30, 30)
        close_btn.setStyleSheet("color: #fbac18; border: none; font-size: 18px; font-weight: bold;")
        close_btn.clicked.connect(self.notif.close)  

        self.notif.move(-330, 20)
        self.notif.show()

        if self.app.sound_enabled:
            try:
                self.app.sound_accept.play()
            except: pass

        anim = QPropertyAnimation(self.notif, b"pos")
        anim.setDuration(400); anim.setStartValue(QPoint(-330, 20)); anim.setEndValue(QPoint(10, 20))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic); anim.start()

        self.pulse_timer = QTimer()
        self._color_phase = False
        def pulse():
            self._color_phase = not self._color_phase
            label.setStyleSheet(f"background-color: rgba(40, 40, 40, 220); border-radius: 10px; font-size: 24px; font-weight: bold; color: {'#ff0000' if self._color_phase else '#ffffff'};")
        self.pulse_timer.timeout.connect(pulse)
        self.pulse_timer.start(500)

        QTimer.singleShot(15000, self.notif.close)