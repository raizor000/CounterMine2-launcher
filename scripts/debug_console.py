import os
import sys
import subprocess
import datetime
from pathlib import Path

from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCharFormat, QColor, QTextCursor, QFont, QIcon

LOG_COLORS = {
    "INFO":  "#00FF00",
    "WARN":  "#ffea00",
    "ERROR": "#ff5252",
    "GAME":  "#80d8ff",
}
def get_resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parent.parent / relative_path

class DebugConsoleWindow(QtWidgets.QWidget):
    closed_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CounterMine2 Launcher")
        icon = str(get_resource_path("assets/icons/icon.webp"))
        self.setWindowIcon(QIcon(icon))
        self.resize(900, 550)
        self.setMinimumSize(500, 300)

        self.setStyleSheet("""
            QWidget {
                background-color: #121212;
                color: #e0e0e0;
                font-family: 'Segoe UI', sans-serif;
            }
            QTextEdit {
                background-color: #0c0c0c;
                color: #00e676;
                border: 1px solid #2a2a2a;
                border-radius: 4px;
                font-family: 'Consolas', 'Lucida Console', 'Courier New', monospace;
                font-size: 10pt;
            }
            QPushButton {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 9pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #fbac18;
                color: #121212;
                border-color: #fbac18;
            }
            QPushButton:pressed {
                background-color: #e69500;
            }
            QLabel#level_legend {
                font-size: 9pt;
                padding: 2px 8px;
                border-radius: 4px;
            }
        """)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        control_layout = QtWidgets.QHBoxLayout()
        control_layout.setSpacing(10)

        for level, color in [("INFO", "#00FF00"), ("WARN", "#ffea00"), ("ERROR", "#ff5252"), ("INGAME", "#80d8ff")]:
            lbl = QtWidgets.QLabel(f"● {level}")
            lbl.setObjectName("level_legend")
            lbl.setStyleSheet(f"color: {color}; background: transparent; font-size: 9pt;")
            control_layout.addWidget(lbl)

        control_layout.addStretch()

        self.copy_btn = QtWidgets.QPushButton("Copy All")
        self.copy_btn.clicked.connect(self.copy_all)
        control_layout.addWidget(self.copy_btn)

        self.export_btn = QtWidgets.QPushButton("Export Log")
        self.export_btn.clicked.connect(self.export_log)
        control_layout.addWidget(self.export_btn)

        layout.addLayout(control_layout)

        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self._max_lines = 5000
        self._line_count = 0
        layout.addWidget(self.log_text)

        self.all_log_lines = []

    def update_ui(self, lang):
        from scripts.translations import translations
        def t(l, k):
            return translations.get(l, {}).get(k, k)

        self.setWindowTitle(f"CounterMine2 Launcher")
        self.copy_btn.setText(t(lang, 'console_copy'))
        self.export_btn.setText(t(lang, 'console_export'))

    def _insert_colored_line(self, text: str, level: str):
        color_hex = LOG_COLORS.get(level, "#00FF00")

        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color_hex))
        fmt.setFont(QFont("Consolas", 10))

        if not self.log_text.document().isEmpty():
            cursor.insertText("\n", QTextCharFormat())

        cursor.insertText(text, fmt)

    def append_log(self, text: str, level: str = "INFO"):
        text = text.rstrip('\r\n')
        if not text:
            return

        self.all_log_lines.append((level, text))

        self._line_count += 1
        if self._line_count > self._max_lines:
            doc = self.log_text.document()
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.select(QTextCursor.SelectionType.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()
            self._line_count -= 1
            if self.all_log_lines:
                self.all_log_lines.pop(0)

        scrollbar = self.log_text.verticalScrollBar()
        was_at_bottom = (scrollbar.maximum() == 0) or (scrollbar.value() >= scrollbar.maximum() - 20)

        self._insert_colored_line(text, level)

        if was_at_bottom:
            QtCore.QTimer.singleShot(0, lambda: scrollbar.setValue(scrollbar.maximum()))

    def copy_all(self):
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(self.log_text.toPlainText())

    def export_log(self):
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Log File",
            "launcher_debug_console.log",
            "Log Files (*.log);;Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.log_text.toPlainText())
                if sys.platform == 'win32':
                    subprocess.Popen(f'explorer /select,"{os.path.abspath(file_path)}"')
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Export Error", f"Failed to save log: {e}")

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.closed_signal.emit()
