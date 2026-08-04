import os
from pathlib import *
from PyQt6 import QtCore
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QPixmap

from scripts.plugin_manager import BasePlugin

class AutumnCollectionBackgroundPlugin(BasePlugin):
    name = "CounterMine2 Collection - Autumn"
    description = "Заменяет обои на осенние."
    version = "0.0.1"
    author = "raizor"

    icon = "collection-autumn.png"

    def on_load(self):
        print(f"[{self.name}] Плагин загружен.")

    def on_ui_ready(self):
        ui = self.app.ui
        print(f"[{self.name}] Замена фона...")
        if hasattr(ui, "background_label"):
            try:
                CURRENT_PLUGIN_DIR = BasePlugin.get_plugin_path(self, "autumncollection")

                pixmap = QPixmap(str(CURRENT_PLUGIN_DIR)+"/collection-autumn-background.png")
                scaled_pixmap = pixmap.scaled(
                    QSize(self.app.width(), self.app.height()),
                    QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation
                )
                ui.background_label.setPixmap(scaled_pixmap)
                print(f"[{self.name}] Замена фона завершена")
            except Exception as e:
                print(f"[{self.name}] Ошибка замены фона: {e}")
        else:
            print(f"[{self.name}] Не найден фон для замены")