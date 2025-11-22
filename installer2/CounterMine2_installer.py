import hashlib
import os

import requests
import shutil
import subprocess
import sys

import psutil
import winshell
from PyQt5 import QtWidgets
from PyQt5.QtCore import *
from PyQt5.QtGui import QFont, QCursor, QPixmap, QIcon
from PyQt5.QtWidgets import QPushButton, QLabel, QFrame, QHBoxLayout
from translations import *

APPDATA = os.getenv("APPDATA") or os.path.expanduser("~")
LAUNCHER_DIR = os.path.join(APPDATA, ".countermine-launcher")
os.makedirs(LAUNCHER_DIR, exist_ok=True)

args = sys.argv

style = """
    QPushButton { background-color: #45A049; color: white; border-radius: 5px; border: none; }
    QPushButton:hover { background-color: #666; }
"""



def t(lang, key):
    return translations[lang].get(key, key)
class Installer(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.target_path = None
        self.old_pos = None
        self.lang = "ru_ru"
        self.setWindowTitle(t(self.lang, "title"))
        self.setFixedSize(450, 350)
        self.setWindowFlags(Qt.FramelessWindowHint)


        bg = QLabel(self)
        pix = QPixmap(self.resource_path("assets/background.png"))
        if not pix.isNull():
            pix = pix.scaled(450, 350, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            bg.setPixmap(pix)
        bg.setGeometry(0, 0, 450, 350)
        bg.lower()
        self.dim_layer = QFrame(self)
        self.dim_layer.setGeometry(0, 0, 450, 350)
        self.dim_layer.setStyleSheet("background-color: rgba(0, 0, 0, 0.6);")

        self.header_frame = QFrame(self)
        self.header_frame.setGeometry(0, 0, 450, 40)
        self.header_frame.setStyleSheet("background-color: rgba(50,50,50,200);")
        self.header_frame.raise_()

        # lang_layout = QHBoxLayout()
        # self.lang_label = QLabel("Язык / Language")
        # self.lang_label.setStyleSheet("color: #dddddd; font-size: 11pt;")
        # self.lang_dropdown = DropDown(["Русский", "English"])
        # lang_layout.setContentsMargins(0, 8, 0, 8)
        # lang_layout.setSpacing(10)
        # lang_layout.addWidget(self.lang_label)
        # lang_layout.addStretch()
        # lang_layout.addWidget(self.lang_dropdown)
        
        self.setWindowIcon(QIcon(self.resource_path("assets/icon.ico")))

        self.logo = QLabel(self.header_frame)
        self.logo_pix = QPixmap(self.resource_path("assets/logo.png"))
        if not self.logo_pix.isNull():
            self.logo.setPixmap(self.logo_pix)
            self.logo.setScaledContents(True)
        self.logo.setGeometry(10, 8, 168, 24)

        self.close_btn = QPushButton("✕", self.header_frame)
        self.close_btn.setGeometry(450 - 40, 5, 30, 30)
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
        self.min_btn.setGeometry(450 - 80, 5, 30, 30)
        self.min_btn.setFont(QFont("sans-serif", 11, QFont.Bold))
        self.min_btn.setStyleSheet("""
                            QPushButton { background-color: transparent; color: yellow; border: none; }
                            QPushButton:hover { color: gray; }
                        """)
        # noinspection PyUnresolvedReferences
        self.min_btn.clicked.connect(self.showMinimized)
        self.min_btn.raise_()
        self.min_btn.setCursor(QCursor(Qt.PointingHandCursor))

        self.container = QtWidgets.QWidget(self)
        self.container.setGeometry(0, 40, 450, 310)  # под хедером
        self.layout = QtWidgets.QVBoxLayout(self.container)

        self.label1 = QtWidgets.QLabel(t(self.lang, "label1"))
        self.label1.setWordWrap(True)
        self.label1.setStyleSheet("""
            color: white;
            font-size: 20px;
            font-weight: bold;  
            margin: 5px;  
            }
        """)
        self.layout.addWidget(self.label1, alignment=Qt.AlignTop)

        self.label = QtWidgets.QLabel(t(self.lang, "label"))
        self.label.setWordWrap(True)
        self.label.setStyleSheet("""
                    color: white;
                    font-size: 15px;
                    font-weight: bold;  
                    margin: 10px;  
                """)
        self.layout.addWidget(self.label, alignment=Qt.AlignTop)

        self.label2 = QtWidgets.QLabel(t(self.lang, "label2"))
        self.label2.setWordWrap(True)
        self.label2.setStyleSheet("""
                            color: gray;
                            font-size: 9px;
                            /* font-weight: bold; */ 
                            margin: 10px;  
                        """)
        self.layout.addWidget(self.label2, alignment=Qt.AlignBottom)

        self.progress = QtWidgets.QProgressBar()
        self.progress.hide()
        self.progress.setStyleSheet("""
                    color: white;
                    background-color: transparent;
                    """)
        self.layout.addWidget(self.progress)

        buttons = QtWidgets.QHBoxLayout()
        self.btn_install = QtWidgets.QPushButton(t(self.lang, "btn1"))
        self.btn_del = QtWidgets.QPushButton(t(self.lang, "btn2"))
        self.btn_exit = QtWidgets.QPushButton(t(self.lang, "btn3"))
        self.launch_btn = QtWidgets.QPushButton(t(self.lang, "btn4"))
        self.btn_install.setStyleSheet(style)
        self.btn_del.setStyleSheet(style)
        self.btn_exit.setStyleSheet(style)
        self.launch_btn.setStyleSheet(style)

        for btn in (self.btn_install, self.btn_del, self.btn_exit, self.launch_btn):
            btn.setFixedHeight(35)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
        self.layout.setContentsMargins(10, 10, 10, 10)
        buttons.setSpacing(10)

        buttons.addWidget(self.btn_install)
        buttons.addWidget(self.btn_del)
        buttons.addWidget(self.launch_btn)
        buttons.addWidget(self.btn_exit)

        self.layout.addLayout(buttons)

        self.btn_install.clicked.connect(self.install)
        self.btn_exit.clicked.connect(self.close)
        self.launch_btn.clicked.connect(self.launch)
        self.launch_btn.hide()


        files = []
        for file in os.listdir(LAUNCHER_DIR):
            files.append(file)

        if len(files) == 0:
            self.btn_del.setStyleSheet("""
                    QPushButton { background-color: #307033; color: white; border-radius: 5px; border: none; }
                    QPushButton:hover { background-color: #666; }
                """)
            self.btn_del.setCursor(QCursor(Qt.ForbiddenCursor))
        else:
            self.btn_del.clicked.connect(self.uninstall)


        self.server_url = "http://f1.delonix.cc:6443"
        self.latest_url = f"{self.server_url}/updates/latest.json"
        self.install_dir = LAUNCHER_DIR
        self.header_frame.mousePressEvent = self.start_move
        self.header_frame.mouseMoveEvent = self.do_move


    def resource_path(self, relative_path):
        if hasattr(sys, "_MEIPASS"):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    def uninstall(self):
        self.btn_exit.setEnabled(False)
        self.btn_del.hide()
        self.btn_install.hide()
        QtWidgets.QApplication.processEvents()
        try:
            self.label.setText(t(self.lang, "label1_del"))
            QtWidgets.QApplication.processEvents()
            os.makedirs(self.install_dir, exist_ok=True)

            if os.path.exists(self.install_dir):
                shutil.rmtree(self.install_dir)

            desktop = winshell.desktop()
            path = os.path.join(desktop, "CounterMine2.lnk")
            if os.path.exists(path):
                os.remove(path)

            self.label.setText(t(self.lang, "label1_del_suc"))
            self.btn_exit.setEnabled(True)

        except Exception as e:
            QtWidgets.QMessageBox.critical(self, t(self.lang, "fail"), str(e))
            self.close()

    def install(self):
        self.btn_exit.hide()
        self.btn_install.hide()
        self.progress.show()
        self.progress.setValue(0)
        self.btn_del.hide()
        QtWidgets.QApplication.processEvents()
        try:
            self.label.setText(t(self.lang, "label1_get"))
            QtWidgets.QApplication.processEvents()
            response = requests.get(self.latest_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            version = data["version"]
            url = data["download_url"]
            checksum = data.get("checksum", None)
            for task in psutil.process_iter():
                if "countermine2_v" in task.name().lower():
                    task.terminate()
            exe_name = f"CounterMine2_v{version}.exe"
            os.makedirs(self.install_dir, exist_ok=True)
            self.target_path = os.path.join(self.install_dir, exe_name)
            self.label.setText(t(self.lang, "label1_download").format(version=version))
            QtWidgets.QApplication.processEvents()
            with requests.get(url, stream=True, timeout=10) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                downloaded = 0
                with open(self.target_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total:
                                self.progress.setValue(int(downloaded * 100 / total))
                            QtWidgets.QApplication.processEvents()
            if checksum:
                with open(self.target_path, "rb") as f:
                    file_hash = hashlib.sha256(f.read()).hexdigest()
                if file_hash.lower() != checksum.lower():
                    self.label.setText(t(self.lang, "label1_hashfail"))
                    return
            self.label.setText(t(self.lang, "label1_ready"))
            self.progress.hide()
            self.btn_exit.show()
            self.launch_btn.show()

            desktop = winshell.desktop()
            path = os.path.join(desktop, "CounterMine2.lnk")
            if os.path.exists(path):
                os.remove(path)
            with winshell.shortcut(path) as shortcut:
                shortcut.path = self.target_path
                shortcut.description = f"CounterMine2 Launcher.\nVersion {version} by raizor"
                shortcut.icon_location = (self.target_path, 0)

        except requests.exceptions.RequestException as e:
            QtWidgets.QMessageBox.critical(self, t(self.lang, "network_fail"), f"{t(self.lang, 'retrieve_fail')}\n{e}")
            self.close()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, t(self.lang, "fail"), str(e))
            self.close()

    def launch(self):
        subprocess.Popen([self.target_path], shell=True, cwd=self.install_dir,
                         creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        self.close()


    def start_move(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def do_move(self, event):
        if self.old_pos:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()


if "--update" in args:
    app = QtWidgets.QApplication(sys.argv)
    w = Installer()
    w.show()
    w.raise_()
    w.install()
    sys.exit(app.exec_())
elif "--uninstall" in args:
    app = QtWidgets.QApplication(sys.argv)
    w = Installer()
    w.show()
    w.raise_()
    w.uninstall()
    sys.exit(app.exec_())
else:
    app = QtWidgets.QApplication(sys.argv)
    w = Installer()
    w.show()
    w.raise_()
    sys.exit(app.exec_())
