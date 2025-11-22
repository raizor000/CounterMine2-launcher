from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QFrame, QWidget

translations = {
    "ru_ru": {
        "title": "Установщик CounterMine2",
        "label1": "Установка CounterMine2",
        "label": "Программа CounterMine2 будет установлена на ваш компьютер",
        "label2": "Разработано игроком raizor. Все права на игровой проект CounterMine2 защищены. Посетите https://cherry.pizza/legal/privacy_policy чтобы узнать больше",
        "btn1": "Установить",
        "btn2": "Удалить лаунчер",
        "btn3": "Закрыть",
        "btn4": "Запустить лаунчер",
        "label1_del": "Удаление...",
        "label1_del_suc": "Удалено успешно",
        "label1_get": "Получение информации о последней версии...",
        "label1_download": "Скачивание версии {version}... \n\nСкорость загрузки зависит от вашей скорости интернета",
        "label1_hashfail": "Файл поврежден! Установка прервана",
        "label1_ready": "Установка завершена!",
        "fail": "Ошибка",
        "network_fail": "Ошибка сети",
        "retrieve_fail": "Не удалось получить обновление:"
    },
    "en_us": {
        "title": "CounterMine2 Setup",
        "label1": "Install CounterMine2",
        "label": "CounterMine2 will be installed on your computer",
        "label2": "Developed by raizor. All rights for CounterMine2 project are reserved. Visit https://cherry.pizza/legal/privacy_policy to learn more",
        "btn1": "Install",
        "btn2": "Uninstall",
        "btn3": "Exit",
        "btn4": "Finish and launch",
        "label1_del": "Uninstalling...",
        "label1_del_suc": "Uninstalled successfully",
        "label1_get": "Revealing latest version information...",
        "label1_download": "Downloading version {version}...",
        "label1_hashfail":  "File is corrupted! Installation aborted",
        "label1_ready": "Installed successfully",
        "fail": "Error",
        "network_fail": "Network error",
        "retrieve_fail": "Error while retrieving update:"
    },
}

class DropDown(QWidget):
    valueChanged = pyqtSignal(str)

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setFixedSize(80, 32)
        self.items = items
        self.current = items[0] if items else ""
        self.expanded = False
        self.popup = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle()
        super().mousePressEvent(event)

    def toggle(self):
        if self.expanded:
            self.close_popup()
        else:
            self.open_popup()

    def open_popup(self):
        if self.popup:
            self.popup.deleteLater()
        self.expanded = True

        self.popup = QFrame(self, flags=Qt.Popup)
        self.popup.setStyleSheet("background-color: #2E2E2E; border: 1px solid #555; border-radius: 6px;")
        layout = QVBoxLayout(self.popup)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for item in self.items:
            label = QLabel(item)
            label.setStyleSheet(f"""
                QLabel {{
                    color: {'#45A049' if item == self.current else 'white'};
                    padding: 6px 10px;
                }}
                QLabel:hover {{
                    background-color: #3A3A3A;
                }}
            """)
            label.mousePressEvent = lambda e, text=item: self.select_item(text)
            layout.addWidget(label)

        self.popup.setLayout(layout)
        self.popup.setFixedWidth(self.width())
        self.popup.move(self.mapToGlobal(self.rect().bottomLeft()))
        self.popup.show()

    def close_popup(self):
        if self.popup:
            self.popup.close()
            self.popup.deleteLater()
            self.popup = None
        self.expanded = False
        self.update()

    def select_item(self, item):
        self.current = item
        self.valueChanged.emit(item)
        self.close_popup()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # рамка и фон
        painter.setBrush(QColor("#2E2E2E"))
        painter.setPen(QColor("#555"))
        painter.drawRoundedRect(0, 0, self.width(), 32, 8, 8)

        # текст выбранного значения
        painter.setPen(QColor("white"))
        painter.drawText(12, 21, self.current)

        # стрелка ▼
        painter.setPen(QColor("white"))
        painter.drawText(self.width() - 20, 21, "▼" if not self.expanded else "▲")
