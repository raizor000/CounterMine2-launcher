from PyQt6 import QtWidgets
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

class CustomDialog(QDialog):
    def __init__(self, parent=None, title="Подтверждение", message="Вы уверены?", icon_path=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)  # Убираем стандартную рамку окна
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # Прозрачный фон
        self.setFixedSize(400, 200)  # Фиксированный размер окна

        # Основной контейнер
        self.main_widget = QtWidgets.QWidget(self)
        self.main_widget.setStyleSheet("""
            QWidget {
                background-color: #2E2E2E;
                border-radius: 10px;
                color: #FFFFFF;
                font-family: Arial;
            }
        """)
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        # Заголовок
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #FFFFFF;
        """)
        self.main_layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Иконка и сообщение
        message_layout = QHBoxLayout()
        if icon_path:
            icon_label = QLabel()
            icon_label.setPixmap(QIcon(icon_path).pixmap(32, 32))
            message_layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignLeft)
        message_label = QLabel(message)
        message_label.setStyleSheet("""
            font-size: 14px;
            color: #FFFFFF;
        """)
        message_label.setWordWrap(True)
        message_layout.addWidget(message_label, stretch=1)
        self.main_layout.addLayout(message_layout)

        self.main_layout.addStretch()

        # Кнопки
        button_layout = QHBoxLayout()
        self.yes_button = QPushButton("Да")
        self.yes_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 8px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.no_button = QPushButton("Нет")
        self.no_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border-radius: 5px;
                padding: 8px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c1170a;
            }
        """)
        button_layout.addWidget(self.yes_button)
        button_layout.addWidget(self.no_button)
        self.main_layout.addLayout(button_layout)

        # Основной layout для диалога
        dialog_layout = QVBoxLayout(self)
        dialog_layout.addWidget(self.main_widget)
        self.setLayout(dialog_layout)

        # Подключение сигналов
        self.yes_button.clicked.connect(self.accept)
        self.no_button.clicked.connect(self.reject)

    def showEvent(self, event):
        # Центрируем окно относительно родителя
        if self.parent():
            parent_rect = self.parent().geometry()
            self.move(parent_rect.center() - self.rect().center())
        super().showEvent(event)