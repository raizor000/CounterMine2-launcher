import sys
import time
import ctypes
from typing import Literal

from PyQt6 import QtWidgets, QtCore, QtGui
import simplepbr
from panda3d.core import Vec4
from dataclasses import dataclass, field
import gltf
from panda3d.core import VirtualFileSystem
from panda3d import direct
from panda3d.core import Filename, get_model_path
from panda3d.core import loadPrcFileData, WindowProperties, Vec3, Vec4, AmbientLight, DirectionalLight, Shader, \
    PointLight, TransparencyAttrib, AntialiasAttrib, TextNode, Point2, DynamicTextFont, NodePath, \
    LoaderFileTypeRegistry, TexturePool, DepthOffsetAttrib
from direct.showbase.ShowBase import ShowBase
from scripts.plugin_manager import BasePlugin
from PyQt6.QtGui import QFont, QCursor
from PyQt6.QtCore import QTimer, QUrl
import os
from panda3d.core import GraphicsOutput, Texture
from scripts.utilties import DropDown


translations = {
    "ru_ru": {
        "cs2_theme_night_time": "Ночное время",
        "cs2_theme_map_selection": "Выбор карты",
        "cs2_theme_map_by": "от ",
        "cs2_theme_map_unknown_author": "Неизвестный автор"
    },
    "en_us": {
        "cs2_theme_night_time": "Night Time",
        "cs2_theme_map_selection": "Map Selection",
        "cs2_theme_map_by": "by ",
        "cs2_theme_map_unknown_author": "Unknown Author"
    }
}

def t(lang, key):
    return translations.get(lang, {}).get(key, key)

QWebEngineView = None


loadPrcFileData("", """
framebuffer-srgb true
framebuffer-multisample true
multisamples 8
""")

os.environ['PANDA_LOADER_PREFER_ASSIMP'] = '0'

loadPrcFileData("", "notify-level-assimp debug")
loadPrcFileData("", "notify-level-loader debug")

loadPrcFileData("", "notify-level-assimp debug")
loadPrcFileData("", "notify-level-loader debug")
loadPrcFileData("", "load-file-type p3assimp #f")


import sys
import os


def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, "scripts", "internal")
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)))


get_model_path().prepend_directory(Filename.from_os_specific(get_base_path()))

if getattr(sys, 'frozen', False):
    vfs = VirtualFileSystem.getGlobalPtr()
    vfs.mount(Filename.from_os_specific(sys._MEIPASS), ".", 0)
    vfs.mount(Filename.from_os_specific(sys._MEIPASS), "/", 0)

    vfs.mount(Filename.from_os_specific(os.path.join(sys._MEIPASS, "simplepbr")), "/simplepbr", 0)

    shaders_path = os.path.join(sys._MEIPASS, "scripts", "internal", "3D", "shaders")
    vfs.mount(Filename.from_os_specific(shaders_path), "/3D/shaders", 0)

    pbr_path = os.path.join(sys._MEIPASS, 'simplepbr')
    if os.path.exists(pbr_path):
        get_model_path().append_directory(pbr_path)

AVAILABLE_MAPS = {
    "Anubis": "3D/anubis.glb",
    "Ancient": "3D/ancient.glb",
    "Dust II": "3D/dust.glb",
    "Mirage": "3D/mirage.glb",
}

MAP_AUTHORS = {
    "Anubis": "entsvagin, maksim0711, b1tter, yoqqu",
    "Ancient": "_gdeya_ & ilya0day33",
    "Dust II": "entsvagin, maksim0711, b1tter, joozev",
    "Mirage": "entsvagin, maksim0711, b1tter, joozev, olegbyko",
}


@dataclass
class ParallaxConfig:
    model_path: str = "3D/background.glb"
    model_scale: float = 10.0
    model_pos: Vec3 = field(default_factory=lambda: Vec3(0, 0, 0))

    camera_pos: Vec3 = field(default_factory=lambda: Vec3(-80, -80, 55))
    base_h: float = 160.0
    base_p: float = 1.0
    base_r: float = 0.0
    max_angle: float = 6.0
    smoothness: float = 0.1

    ambient_color: Vec4 = field(default_factory=lambda: Vec4(0.18, 0.13, 0.10, 1))
    sun_color: Vec4 = field(default_factory=lambda: Vec4(0.5, 0.35, 0.2, 1))
    sun_hpr: Vec3 = field(default_factory=lambda: Vec3(140, -20, 5))


class BasePandaWidget(QtCore.QObject):
    frame_ready = QtCore.pyqtSignal(QtGui.QImage)
    scene_ready = QtCore.pyqtSignal()

    def __init__(self, launcher, icon_path, parent=None):
        super().__init__(parent)
        self.launcher = launcher
        self.last_mouse_time = None
        self.icon_path = icon_path

        self.panda = None
        self.timer2 = None

        self.target_width = launcher.width()
        self.target_height = launcher.height()

        QtCore.QTimer.singleShot(0, self._internal_init_panda)

    def _internal_init_panda(self):
        try:
            print(f"[{self.__class__.__name__}] Starting Panda3D initialization...")
            from panda3d.core import loadPrcFileData, WindowProperties, GraphicsOutput, Texture
            loadPrcFileData("", f"win-size {self.target_width} {self.target_height}")

            self.panda = ShowBase(windowType="offscreen")

            self.tex = Texture()
            try:
                self.panda.win.addRenderTexture(
                    self.tex,
                    GraphicsOutput.RTMCopyRam,
                    GraphicsOutput.RTPColor
                )
            except Exception as e:
                print(f"[{self.__class__.__name__}] Error adding render texture: {e}")
                raise

            print(f"[{self.__class__.__name__}] SimplePBR initialization...")

            import simplepbr
            pline = simplepbr.init(
                enable_shadows=True,
                use_normal_maps=True,
                use_occlusion_maps=True,
                max_lights=8,
                sdr_lut_factor=10.0
            )
            print(f"[{self.__class__.__name__}] SimplePBR initialized.")

            self.panda.render.setAntialias(AntialiasAttrib.MAuto)
            self.panda.disableMouse()
            print(f"[{self.__class__.__name__}] Panda3D core setup complete.")

            self.timer2 = QtCore.QTimer(self)
            self.timer2.timeout.connect(self._render_loop)
            print(f"[{self.__class__.__name__}] Starting render loop timer.")
            self.timer2.start(20)

            self.setup_scene()
            self.scene_ready.emit()
        except Exception as e:
            print(f"Error initializing Panda3D: {e}")

    def _render_loop(self):
        self.panda.taskMgr.step()
        try:
            if self.tex.hasRamImage():
                ram_image = self.tex.getRamImage()
                data = ram_image.getData()
                width = self.tex.getXSize()
                height = self.tex.getYSize()

                data_copy = bytes(data)

                img = QtGui.QImage(
                    data_copy,
                    width,
                    height,
                    width * 4,
                    QtGui.QImage.Format.Format_ARGB32
                ).mirrored(False, True)

                self.frame_ready.emit(img)
        except Exception as e:
            print(f"Error rendering: {e}")


        if (self.last_mouse_time is not None
                and time.monotonic() - self.last_mouse_time > 1.0):
            self.timer2.stop()

    def pause_render(self):
        if self.timer2 and self.timer2.isActive():
            self.timer2.stop()

    def resume_render(self):
        if self.timer2 and not self.timer2.isActive():
            self.timer2.start(20)

    def request_render(self):
        if self.panda:
            self._render_loop()

    def sync_to(self, launcher):
        if self.panda and self.panda.camLens:
            self.panda.camLens.setAspectRatio(launcher.width() / max(1, launcher.height()))

    def setup_scene(self):
        pass


class BillboardLabel:
    def __init__(
            self,
            panda,
            text="",
            pos=Vec3(0, 0, 0),
            scale=1.0,
            color=(1, 1, 1, 1),
    ):
        self.panda = panda

        self.text = TextNode("billboard_label")
        self.text.setText(text)
        font = DynamicTextFont("3D/minecraft.ttf")
        font.setPixelsPerUnit(80)
        font.setNativeAntialias(False)

        self.text.setFont(font)
        self.text.setAlign(TextNode.ACenter)
        self.text.setTextColor(*color)

        self.text.setCardColor(0, 0, 0, 0.8)
        self.text.setCardAsMargin(
            0.25,
            0.25,
            0.15,
            0.15
        )

        self.np = NodePath(self.text)

        self.np.setShaderOff()
        self.np.setShaderAuto(False)

        self.np.setPos(pos)
        self.np.setScale(scale)

        self.np.setDepthWrite(False)
        self.np.setTransparency(True)
        self.np.setBillboardPointEye()

    def reparentTo(self, parent):
        self.np.reparentTo(parent)

    def setPos(self, *args):
        self.np.setPos(*args)

    def setScale(self, *args):
        self.np.setScale(*args)

    def setText(self, text):
        self.text.setText(text)

    def node(self):
        return self.np


class BackgroundWidget(BasePandaWidget):
    def __init__(self, launcher, icon_path, config=None, parent=None):
        self.cfg = config or ParallaxConfig()

        self.cur_h = self.cfg.base_h
        self.cur_p = self.cfg.base_p
        self.parallax_enabled = True
        self.model = None
        self.nick_label = None
        self.sun = None
        self.amb = None
        self.model = None
        self.last_mouse_pos = None
        self._render_paused_manually = False
        
        super().__init__(launcher, icon_path, parent)
        self.parallax_timer = QtCore.QTimer(self)
        self.parallax_timer.timeout.connect(self._update_parallax_and_mouse)
        self.parallax_timer.start(20)


    def setup_scene(self):
        registry = LoaderFileTypeRegistry.getGlobalPtr()
        old_type = registry.getTypeFromExtension("glb")
        if old_type:
            registry.unregisterType(old_type)

        registry.registerType(gltf._loader.GltfLoader())

        print(f"DEBUG: Active loader for glb: {registry.getTypeFromExtension('glb')}")
        TexturePool.releaseAllTextures()

        self._load_model_internal(self.cfg.model_path)
        print(f"[{self.__class__.__name__}] Model loaded: {self.cfg.model_path}")

        print(f"[BackgroundWidget] Loaded model: {self.cfg.model_path}")
        print(f"[BackgroundWidget] Model scale: {self.cfg.model_scale}, position: {self.cfg.model_pos}")
        print(f"[BackgroundWidget] Camera position: {self.cfg.camera_pos}, base HPR: ({self.cfg.base_h}, {self.cfg.base_p}, {self.cfg.base_r})")
        print(f"[BackgroundWidget] Max angle: {self.cfg.max_angle}, smoothness: {self.cfg.smoothness}")
        print(f"[BackgroundWidget] Ambient color: {self.cfg.ambient_color}, Sun color: {self.cfg.sun_color}, Sun HPR: {self.cfg.sun_hpr}")
        print(f"[BackgroundWidget] Parallax enabled: {self.parallax_enabled}")
        print(f"[BackgroundWidget] Nick label: {self.nick_label}, Sun: {self.sun}, Ambient: {self.amb}, Model: {self.model}")
        print(f"[BackgroundWidget] Model analysis: {self.model.analyze() if self.model else 'No model loaded'}")
        print(f"[BackgroundWidget] Model bounds: {self.model.getBounds() if self.model else 'No model loaded'}")
        print(f"[BackgroundWidget] Model node count: {self.model.getNumChildren() if self.model else 'No model loaded'}")

        
        print(f"[{self.__class__.__name__}] Setting up lights.")
        self.panda.render.clearLight()
        self._setup_lights()

        self.sky_dome = self.panda.loader.loadModel("models/smiley")
        self.sky_dome.reparentTo(self.panda.render)
        self.sky_dome.setScale(500)
        self.sky_dome.setTwoSided(True)
        self.sky_dome.setDepthWrite(False)
        self.sky_dome.setBin("background", 0)

        print(f"[{self.__class__.__name__}] Loading sky shader.")
        sky_shader = Shader.load(Shader.SL_GLSL, vertex="3D/shaders/sky.vert",
                                 fragment="3D/shaders/sky.frag"
                                 )
        self.sky_dome.setShader(sky_shader)

        self.sun_direction = -self.sun_light_node.getQuat().getForward()
        self.sun_direction.normalize()

        print(f"[{self.__class__.__name__}] Setting sky shader input.")
        self.sky_dome.setShaderInput("sun_dir", self.sun_direction)

        self.panda.render.setShaderInput("lights", self.sun_light_node)

    def _setup_lights(self):
        self.amb = AmbientLight("ambient_light")
        self.amb.setColor(self.cfg.ambient_color)
        self.ambient_light_node = self.panda.render.attachNewNode(self.amb)
        print(f"[{self.__class__.__name__}] Ambient light set.")
        self.panda.render.setLight(self.ambient_light_node)

        self.sun = DirectionalLight("sun_light")
        self.sun.setColor(self.cfg.sun_color)
        self.sun.setShadowCaster(True, 4096, 4096)

        lens = self.sun.getLens()
        lens.setFilmSize(500, 500)
        lens.setNearFar(1, 500)

        self.sun_light_node = self.panda.render.attachNewNode(self.sun)
        self.sun_light_node.setHpr(self.cfg.sun_hpr)
        print(f"[{self.__class__.__name__}] Directional light set.")
        self.panda.render.setLight(self.sun_light_node)

    def set_label_text(self, text):
        try:
            self.nick_label.setText(text)
        except Exception as e:
            print(f"[BackgroundWidget] Error setting label text: {e}")

    def set_time(self, time: Literal['day', 'night']):
        if self.sun and self.amb:
            if time == 'night':
                self.sun.setColor(Vec4(0.10, 0.14, 0.26, 1))
                self.amb.setColor(Vec4(0.015, 0.025, 0.040, 1))
            elif time == 'day':
                self.sun.setColor(Vec4(0.5, 0.35, 0.2, 1))
                self.amb.setColor(Vec4(0.18, 0.13, 0.10, 1))

    def _update_parallax_and_mouse(self):
        global_mouse_pos = QtGui.QCursor.pos()
        if self.last_mouse_pos is not None and self.last_mouse_pos != global_mouse_pos:
            self.last_mouse_time = time.monotonic()
            if not self.timer2.isActive() and not self._render_paused_manually:
                self.resume_render()
        self.last_mouse_pos = global_mouse_pos

        widget_global_top_left = self.launcher.mapToGlobal(self.launcher.rect().topLeft())
        widget_rect = QtCore.QRect(widget_global_top_left, self.launcher.size())

        if self.parallax_enabled and self.launcher.isActiveWindow():
            if widget_rect.contains(global_mouse_pos):
                local_pos = self.launcher.mapFromGlobal(global_mouse_pos)
                mx = (local_pos.x() / self.launcher.width() - 0.5) * -2
                my = (local_pos.y() / self.launcher.height() - 0.5) * -2
            else:
                mx = my = 0.0
        else:
            mx = my = 0.0

        target_h = self.cfg.base_h + mx * self.cfg.max_angle
        target_p = self.cfg.base_p + my * self.cfg.max_angle

        self.cur_h += (target_h - self.cur_h) * self.cfg.smoothness
        self.cur_p += (target_p - self.cur_p) * self.cfg.smoothness

        try:
            if self.panda and self.panda.camera:
                self.panda.camera.setPos(self.cfg.camera_pos)
                self.panda.camera.setHpr(self.cur_h, self.cur_p, self.cfg.base_r)
                if not hasattr(self, "nick_label") or self.nick_label is None:
                    self.nick_label = BillboardLabel(self.panda, "")
                    self.nick_label.reparentTo(self.panda.render)
                    self.nick_label.setPos(-101.6, -130, 63.3)
                    self.nick_label.setScale(1.5)
        except Exception as e:
            print(f"[{self.__class__.__name__}] Error updating parallax: {e}")

    def pause_render(self):
        self._render_paused_manually = True
        super().pause_render()

    def resume_render(self):
        self._render_paused_manually = False
        super().resume_render()

    def _load_model_internal(self, model_path):
        if self.model:
            self.model.removeNode()

        print(f"[{self.__class__.__name__}] Loading new model: {model_path}")
        path = Filename.from_os_specific(
            os.path.join(get_base_path(), model_path)
        )
        self.model = self.panda.loader.loadModel(path)
        self.model.reparentTo(self.panda.render)
        self.model.setScale(self.cfg.model_scale)
        self.model.setPos(self.cfg.model_pos)
        print(f"[{self.__class__.__name__}] New model loaded and positioned.")

        self.model.setAttrib(
            DepthOffsetAttrib.make(2)
        )

        if hasattr(self, 'nick_label') and self.nick_label:
            print(f"[{self.__class__.__name__}] Re-parenting nick_label.")
            self.nick_label.reparentTo(self.panda.render)

        for np in self.model.findAllMatches("**"):
            if "water" in np.getName().lower():
                np.setTransparency(TransparencyAttrib.MAlpha)
                np.setDepthWrite(False)
        print(f"[{self.__class__.__name__}] Transparency applied to water nodes.")

        self.cfg.model_path = model_path

    def change_model(self, new_model_path):
        if new_model_path == self.cfg.model_path:
            return
        self._load_model_internal(new_model_path)
        self.request_render()


    def set_camera_position(self, pos: Vec3):
        self.cfg.camera_pos = pos

    def set_parallax_enabled(self, state: bool):
        self.parallax_enabled = state

    def set_camera_rotation(self, h=None, p=None, r=None):
        if h is not None:
            self.cfg.base_h = h
        if p is not None:
            self.cfg.base_p = p
        if r is not None:
            self.cfg.base_r = r

    def set_sun_position(self, hpr: Vec3):
        self.cfg.sun_hpr = hpr

        if hasattr(self, "sun_light_node"):
            self.sun_light_node.setHpr(hpr)

            self.sun_direction = -self.sun_light_node.getQuat().getForward()
            self.sun_direction.normalize()

            if hasattr(self, "sky_dome"):
                self.sky_dome.setShaderInput(
                    "sun_dir",
                    self.sun_direction
                )

    def set_sun_color(self, color: Vec4):
        self.cfg.sun_color = color

        if hasattr(self, "sun_light_node"):
            self.sun_light_node.node().setColor(color)

    def set_ambient_color(self, color: Vec4):
        self.cfg.ambient_color = color

        if hasattr(self, "ambient_light_node"):
            self.ambient_light_node.node().setColor(color)

class NewsToggleButton(QtWidgets.QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._angle = 0
        self._scale = 1.0
        self.is_collapsed_mode = False
        
        self.scale_anim = QtCore.QPropertyAnimation(self, b"buttonScale")
        self.scale_anim.setDuration(200)
        self.scale_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        
        self.rot_anim = QtCore.QPropertyAnimation(self, b"buttonRotation")
        self.rot_anim.setDuration(920)
        self.rot_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutBack)

    @QtCore.pyqtProperty(float)
    def buttonScale(self): return self._scale
    @buttonScale.setter
    def buttonScale(self, v):
        self._scale = v
        self.update()

    @QtCore.pyqtProperty(float)
    def buttonRotation(self): return self._angle
    @buttonRotation.setter
    def buttonRotation(self, v):
        self._angle = v % 360
        self.update()

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
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2
        painter.translate(cx, cy)
        painter.rotate(self._angle)
        painter.scale(self._scale, self._scale)
        painter.translate(-cx, -cy)
        opacity = 35 if self.underMouse() else 15
        painter.setBrush(QtGui.QColor(255, 255, 255, opacity))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawEllipse(self.rect().adjusted(1, 1, -1, -1))
        painter.setPen(QtGui.QColor("white"))
        font = QtGui.QFont("sans-serif", 14, QtGui.QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, self.text())


from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *


def fit_button_font(button: QPushButton, min_size=7, max_size=13):
    text = button.text()

    if not text:
        return

    margins = button.contentsMargins()
    width = (
        button.width()
        - margins.left()
        - margins.right()
        - 2
    )
    height = (
        button.height()
        - margins.top()
        - margins.bottom()
        - 2
    )

    if width <= 0 or height <= 0:
        return

    for size in range(max_size, min_size - 1, -1):
        font = QFont("sans-serif", size, QFont.Weight.Bold)
        doc = QTextDocument()
        doc.setDefaultFont(font)
        doc.setPlainText(text)
        doc.setTextWidth(width)
        if doc.size().height() <= height:
            button.setFont(font)
            return

    button.setFont(QFont("sans-serif", min_size, QFont.Weight.Bold))


class AutoFontButton(QPushButton):
    def setText(self, text):
        super().setText(text)
        fit_button_font(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        fit_button_font(self)

class UI_Modifier(BasePlugin):
    name = "Counter-Strike 2 theme"
    description = "Плагин для изменения внешнего вида лаунчера под Counter-Strike 2"
    version = "1.0.0"
    author = "raizor"
    icon = "assets/pixmaps/settings.png"

    def __init__(self, app):
        super().__init__(app)

    def on_load(self):
        self.news_expanded = True
        self.selected_map = self.app.plugin_states.get("cs2_theme_map", "Anubis")
        self.is_night = self.app.plugin_states.get("cs2_theme_is_night", False)
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))


        print(f"[{self.name}] Плагин загружен.")

    def on_ui_ready(self):
        ui = self.app.ui
        if sys.platform == "win32":
            print(f"[{self.name}] UI готов, приступаю к модификации...")
            
            self.app.ui.settings_changed.connect(self.on_global_settings_changed)
            self.app.auth_manager.auth_finished.connect(self.on_auth)

            self.add_time_setting()
            self.add_map_setting()

            self.map_info_label = QtWidgets.QLabel(ui)
            self.map_info_label.setObjectName("map_info_label")
            self.map_info_label.setStyleSheet("color: rgba(255, 255, 255, 180); background: transparent; font-size: 9pt;")
            self.map_info_label.move(10, ui.height() - 30)
            self.map_info_label.show()
            self.update_map_info_label()


            self.init_web_tab()
            self.apply_custom_styles()

            self.setup_news_toggle()
            self.update_ui_texts(self.app.lang)
        else:
            print(f"[{self.name}] Плагин не поддерживается на этой платформе.")

    def on_language_change(self, lang):
        if lang == "ru_ru":
            ...
        elif lang == "en_us":
            ...
        self.update_ui_texts(lang)

    def update_ui_texts(self, lang):
        if hasattr(self, 'time_label'):
            self.time_label.setText(t(lang, "cs2_theme_night_time"))
        if hasattr(self, 'map_label'):
            self.map_label.setText(t(lang, "cs2_theme_map_selection"))
        if hasattr(self, 'map_info_label'):
            self.update_map_info_label()

        
    def update_map_info_label(self):
        map_name = self.selected_map
        author = MAP_AUTHORS.get(map_name, t(self.app.lang, "cs2_theme_map_unknown_author"))
        self.map_info_label.setText(f"{map_name} {t(self.app.lang, 'cs2_theme_map_by')}{author}")
        self.map_info_label.adjustSize()

    def add_time_setting(self):
        ui = self.app.ui
        if not hasattr(ui, 'plugin_settings_layout'):
            return

        from scripts.utilties import SwitchButton
        
        time_layout = QtWidgets.QHBoxLayout()
        self.time_label = QtWidgets.QLabel(t(self.app.lang, "cs2_theme_night_time"))
        self.time_label.setStyleSheet("color: #dddddd; font-size: 11pt; background: transparent;")

        self.time_switch = SwitchButton()
        self.time_switch.setOnColor("#fbac18")
        self.time_switch.setChecked(self.is_night)
        self.time_switch.stateChanged.connect(self.on_time_changed)

        time_layout.addWidget(self.time_label)
        time_layout.addStretch()
        time_layout.addWidget(self.time_switch)

        ui.plugin_settings_layout.addLayout(time_layout)
        ui.plugin_settings_separator.setVisible(True)


    def add_map_setting(self):
        ui = self.app.ui
        if not hasattr(ui, 'plugin_settings_layout'):
            return

        map_layout = QtWidgets.QHBoxLayout()
        self.map_label = QtWidgets.QLabel(t(self.app.lang, "cs2_theme_map_selection"))
        self.map_label.setStyleSheet("color: #dddddd; font-size: 11pt; background: transparent;")

        map_names = list(AVAILABLE_MAPS.keys())
        self.map_dropdown = DropDown(map_names)
        self.map_dropdown.setSelectedColor("#fbac18")
        self.map_dropdown.current = self.selected_map
        self.map_dropdown.valueChanged.connect(self.on_map_changed)

        map_layout.addWidget(self.map_label)
        map_layout.addStretch()
        map_layout.addWidget(self.map_dropdown)

        ui.plugin_settings_layout.addLayout(map_layout)
        ui.plugin_settings_separator.setVisible(True)


    def on_auth(self, data):
        try:
            new_nick = data.get("nickname")
            self.app.ui.bg3d.set_label_text(new_nick)
        except Exception as e:
            print(f"[{self.name}] Ошибка при установке нового ника: {e}")

    def on_time_changed(self, is_night):
        self.is_night = is_night
        self.app.plugin_states["cs2_theme_is_night"] = is_night
        self.app.save_settings()

        if hasattr(self.app.ui, 'bg3d') and self.app.ui.bg3d:
            self.app.ui.bg3d.set_time('night' if is_night else 'day')
            self.app.ui.bg3d.request_render()

    def on_map_changed(self, map_name):
        self.selected_map = map_name
        self.app.plugin_states["cs2_theme_map"] = map_name
        self.app.save_settings()

        if hasattr(self.app.ui, 'bg3d') and self.app.ui.bg3d:
            model_path = AVAILABLE_MAPS.get(map_name)
            self.app.ui.bg3d.change_model(model_path)
            self.app.ui.bg3d.request_render()

        self.update_map_info_label()

    def setup_news_toggle(self):
        ui = self.app.ui
        if not hasattr(ui, 'container_frame'):
            return

        self.toggle_news_btn = NewsToggleButton("−", ui.container_frame)
        self.toggle_news_btn.setFixedSize(28, 28)
        self.toggle_news_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.toggle_news_btn.move(14, 14)
        self.toggle_news_btn.clicked.connect(self.toggle_news)

    def init_web_tab(self):
        ui = self.app.ui
        if hasattr(self, 'web_tab_btn'):
            return

        self.web_tab_btn = QtWidgets.QPushButton("")
        self.web_tab_btn.setFixedSize(30, 30)
        self.web_tab_btn.setCheckable(True)
        self.web_tab_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self.web_tab_btn.setObjectName("web_tab_btn")
        self.web_tab_btn.setIcon(QtGui.QIcon(self.app.ui.resource_path("assets/icons/tv.png")))
        self.web_tab_btn.setIconSize(QtCore.QSize(24, 24))
        self.web_tab_btn.clicked.connect(self.on_web_tab_clicked)

        ui.tab_news_btn.clicked.connect(self.on_other_tab_clicked)
        ui.tab_settings_btn.clicked.connect(self.on_other_tab_clicked)
        ui.tab_installed_mods_btn.clicked.connect(self.on_other_tab_clicked)
        if hasattr(ui, 'modrinth_plugin_tab_btn') and ui.modrinth_plugin_tab_btn:
            ui.modrinth_plugin_tab_btn.clicked.connect(self.on_other_tab_clicked)

        if hasattr(ui, 'tabs_layout'):
            ui.tabs_layout.insertWidget(1, self.web_tab_btn)
            self.web_tab_btn.show()

    def _ensure_web_view(self):
        if hasattr(self, 'web_view'):
            return True

        global QWebEngineView
        if QWebEngineView is None:
            try:
                from PyQt6.QtWebEngineWidgets import QWebEngineView as LoadedWebEngineView
                QWebEngineView = LoadedWebEngineView
            except ImportError:
                return False

        ui = self.app.ui
        self.web_view = QWebEngineView(ui)
        self.web_view.setGeometry(0, 40, ui.width(), ui.height() - 40)
        self.web_view.page().loadFinished.connect(self._inject_scrollbar_css)
        self.web_view.hide()
        QtCore.QTimer.singleShot(0, lambda: self.web_view.setUrl(QUrl("https://cm2news.xyz")))
        return True

    def _inject_scrollbar_css(self, ok):
        if not ok or not hasattr(self, 'web_view'):
            return

        css = """
            ::-webkit-scrollbar {
                width: 8px;
                background-color: transparent;
            }
            ::-webkit-scrollbar-thumb {
                background-color: #fbac18;
                border-radius: 4px;
            }
            ::-webkit-scrollbar-thumb:hover {
                background-color: #e69500;
            }
            ::-webkit-scrollbar-track {
                background-color: rgba(40, 40, 40, 0.5);
            }
        """
        js_code = f"var style = document.createElement('style'); style.innerHTML = `{css.replace(os.linesep, '')}`; document.head.appendChild(style);"
        self.web_view.page().runJavaScript(js_code)

    def on_global_settings_changed(self, key, value):
        if key == "style":
            QtCore.QTimer.singleShot(1, self.apply_custom_styles)
        if key == "lang":
            QtCore.QTimer.singleShot(1, self.apply_custom_styles)

    def update_background(self, img):
        ui = self.app.ui
        label_size = ui.background_label.size()
        w = label_size.width()
        h = max(1, label_size.height())
        if hasattr(ui, 'bg3d') and ui.bg3d.panda and ui.bg3d.panda.camLens:
            ui.bg3d.panda.camLens.setAspectRatio(w / h)

        pixmap = QtGui.QPixmap.fromImage(img)
        scaled_pixmap = pixmap.scaled(
            label_size,
            QtCore.Qt.AspectRatioMode.IgnoreAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation
        )
        ui.background_label.setPixmap(scaled_pixmap)

    def recalculate_sizes(self):
        ui = self.app.ui
        ui.background_label.setGeometry(0, 0, ui.width(), ui.height())
        if hasattr(ui, 'bg3d') and ui.bg3d:
            ui.bg3d.sync_to(self.app)

        if hasattr(self, 'map_info_label'):
            self.map_info_label.move(10, ui.height() - self.map_info_label.height() - 10)



    def apply_custom_styles(self):
        ui = self.app.ui
        ui.background_label.show()
        ui.background_label.setScaledContents(False)
        ui.background_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        if not hasattr(ui, 'bg3d') or ui.bg3d is None:
            initial_map_name = self.app.plugin_states.get("cs2_theme_map", "Anubis")
            initial_model_path = AVAILABLE_MAPS.get(initial_map_name, "3D/anubis.glb")

            custom_config = ParallaxConfig(
                model_path=initial_model_path,
                max_angle=4.0,
                smoothness=0.08,
                sun_color=Vec4(0.5, 0.35, 0.2, 1),
            )
            ui.bg3d = BackgroundWidget(
                launcher=self.app,
                config=custom_config,
                icon_path=self.app.icon_p
            )
            ui.bg3d.frame_ready.connect(self.update_background)
            ui.bg3d.scene_ready.connect(lambda: ui.bg3d.set_time('night' if self.is_night else 'day'))
            if self.app.nickname:
                ui.bg3d.set_label_text(self.app.nickname)

        else:
            ui.bg3d.set_time('night' if self.is_night else 'day')
            
        ui.bg3d.sync_to(self.app)
        self.app.raise_()
        QTimer.singleShot(100, self.recalculate_sizes)


        ui.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        ui.raise_()

        palette = ui.palette()
        palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(0, 0, 0, 0))
        ui.setPalette(palette)

        if hasattr(ui, 'logo'):
            ui.logo.hide()

        if hasattr(ui, 'tabs_container'):
            ui.tabs_container.move(10, 0)

        if hasattr(ui, 'header_frame'):
            ui.header_frame.setFixedHeight(40) 
            ui.header_frame.setStyleSheet("""
                QFrame {
                    background-color: rgba(40, 40, 40, 150);
                    border-radius: 0px;
                    border-bottom: 1px solid rgba(255, 255, 255, 40);
                    QLabel { color: white; background: transparent; border: none; }

                }
            """)

        if hasattr(ui, 'buttons_block') and hasattr(ui, 'open_game_directory_btn') and hasattr(ui, 'reinstall_btn'):
            ui.buttons_block.setFixedWidth(ui.buttons_block.width() - 6)
            ui.buttons_block.setFixedHeight(ui.height() - ui.header_frame.height())
            ui.buttons_block.move(ui.width() - ui.buttons_block.width(), ui.header_frame.height())
            
            ui.buttons_block.setStyleSheet("""
                QFrame {
                    background-color: rgba(40, 40, 40, 150);
                    border-radius: 0px;
                    border-left: 1px solid rgba(255, 255, 255, 40);
                }
                QLabel { color: white; background: transparent; border: none; }
            """)
            
            for btn in ui.buttons_block.findChildren(QtWidgets.QPushButton):
                new_x = (ui.buttons_block.width() - btn.width()) // 2
                btn.move(new_x, btn.y())

            ui.open_game_directory_btn.move(ui.open_game_directory_btn.x(), ui.buttons_block.height() - ui.open_game_directory_btn.height() - 65)
            ui.reinstall_btn.move(ui.reinstall_btn.x(), ui.buttons_block.height() - ui.reinstall_btn.height() - 10)

            if not hasattr(self, 'top_side_separator'):
                self.top_side_separator = QtWidgets.QFrame(ui.buttons_block)
                self.top_side_separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
                self.top_side_separator.setStyleSheet("background-color: rgba(255, 255, 255, 60); border: none;")
                self.top_side_separator.setFixedHeight(1)

            self.top_side_separator.setFixedWidth(ui.buttons_block.width())
            self.top_side_separator.move(0, 295)
            self.top_side_separator.show()

            if not hasattr(self, 'side_separator'):
                self.side_separator = QtWidgets.QFrame(ui.buttons_block)
                self.side_separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
                self.side_separator.setStyleSheet("background-color: rgba(255, 255, 255, 60); border: none;")
                self.side_separator.setFixedHeight(1)

            self.side_separator.setFixedWidth(ui.buttons_block.width())
            sep_x = (ui.buttons_block.width() - self.side_separator.width()) // 2
            self.side_separator.move(sep_x, ui.open_game_directory_btn.y() - 12)
            self.side_separator.show()


        common_btn_style = """
                QPushButton {
                    background-color: rgba(251, 172, 24, 110);
                    color: white;
                    border-radius: 5px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: rgba(211, 132, 24, 75);
                }
                QPushButton:pressed {
                    background-color: rgba(251, 172, 24, 145);
                    border: none;
                }
        """
        
        if hasattr(self, 'web_tab_btn') and hasattr(ui, 'tabs_layout'):
            self.web_tab_btn.setStyleSheet(common_btn_style + "padding: 0 10px;")
            if ui.tabs_layout.indexOf(self.web_tab_btn) == -1:
                ui.tabs_layout.insertWidget(1, self.web_tab_btn)
            
            self.web_tab_btn.show()

        if hasattr(ui, 'logo_separator'):
            ui.logo_separator.hide()

        if hasattr(ui, 'separator_min'):
            ui.separator_min.hide()
        
        if hasattr(ui, 'tab_news_btn') and hasattr(ui, 'tabs_layout'):
            ui.tab_news_btn.setStyleSheet(common_btn_style)
            ui.tab_news_btn.setFlat(True)
            ui.tab_news_btn.setFixedSize(30, 30)
            ui.tab_news_btn.setText("")
            ui.tab_news_btn.setIcon(QtGui.QIcon(self.app.ui.resource_path("assets/icons/home.png")))
            ui.tab_news_btn.setIconSize(QtCore.QSize(24, 24))
            if ui.tabs_layout.indexOf(ui.tab_news_btn) != -1:
                ui.tabs_layout.removeWidget(ui.tab_news_btn)
            ui.tabs_layout.insertWidget(0, ui.tab_news_btn)

        if hasattr(ui, 'tab_settings_btn') and hasattr(ui, 'tabs_layout'):
            ui.tab_settings_btn.setStyleSheet(common_btn_style)
            ui.tab_settings_btn.setFlat(True)
            ui.tab_settings_btn.setFixedSize(30, 30)
            ui.tab_settings_btn.setText("")
            ui.tab_settings_btn.setIcon(QtGui.QIcon(self.app.ui.resource_path("assets/icons/settings.png")))
            ui.tab_settings_btn.setIconSize(QtCore.QSize(24, 24))
            if ui.tabs_layout.indexOf(ui.tab_settings_btn) != -1:
                ui.tabs_layout.removeWidget(ui.tab_settings_btn)
            ui.tabs_layout.insertWidget(2, ui.tab_settings_btn)

        if hasattr(ui, 'close_btn') and hasattr(ui, 'tabs_layout'):
            ui.close_btn.setText("")
            ui.close_btn.setIcon(QtGui.QIcon(self.app.ui.resource_path("assets/icons/exit.png")))
            ui.close_btn.setIconSize(QtCore.QSize(24, 24))
            ui.close_btn.setFixedSize(30, 30)
            ui.close_btn.setFlat(True)
            ui.close_btn.setStyleSheet(common_btn_style)
            if ui.tabs_layout.indexOf(ui.close_btn) != -1:
                ui.tabs_layout.removeWidget(ui.close_btn)
            ui.tabs_layout.insertWidget(3, ui.close_btn)

        if hasattr(ui, 'play_btn') and hasattr(ui, 'header_frame'):
            ui.play_btn.setParent(ui.header_frame)
            ui.play_btn.setFixedSize(120, 35)


            center_x = (ui.header_frame.width() - ui.play_btn.width()) // 2
            center_y = (ui.header_frame.height() - ui.play_btn.height()) // 2
            
            ui.play_btn.move(center_x, center_y)

            side_spacing = 10

            old = ui.play_btn

            ui.play_btn = AutoFontButton(old.text(), ui.header_frame)
            ui.play_btn.setObjectName(old.objectName())
            ui.play_btn.setFixedSize(old.size())
            ui.play_btn.move(old.pos())
            ui.play_btn.clicked.connect(old.click)
            ui.play_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            ui.play_btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(20,20,20,20);
                        color: white;
                    }
                    QPushButton:checked {
                        background-color: #75bf0f;
                        color: black;
                    }
                    """)
            old.hide()

            separator_style = "background-color: rgba(255, 255, 255, 150);"

            if hasattr(ui, 'tab_installed_mods_btn'):
                i_btn = ui.tab_installed_mods_btn
                if ui.tabs_layout.indexOf(i_btn) != -1:
                    ui.tabs_layout.removeWidget(i_btn)
                i_btn.setParent(ui.header_frame)
                i_btn.setFixedSize(90, 30)
                i_btn_x = center_x + ui.play_btn.width() + side_spacing
                i_btn_y = (ui.header_frame.height() - i_btn.height()) // 2
                i_btn.move(i_btn_x, i_btn_y)
                i_btn.setStyleSheet(ui.play_btn.styleSheet())

                if not hasattr(self, 'right_separator'):
                    self.right_separator = QtWidgets.QFrame(ui.header_frame)
                    self.right_separator.setFrameShape(QtWidgets.QFrame.Shape.VLine)
                    self.right_separator.setStyleSheet(separator_style)
                    self.right_separator.setGeometry(i_btn.x() + i_btn.width() + side_spacing,
                                                     (ui.header_frame.height() - 20) // 2, 1, 20)

            if hasattr(ui, 'modrinth_plugin_tab_btn') and ui.modrinth_plugin_tab_btn:
                m_btn = ui.modrinth_plugin_tab_btn


                if ui.tabs_layout.indexOf(m_btn) != -1:
                    ui.tabs_layout.removeWidget(m_btn)
                m_btn.setParent(ui.header_frame)
                m_btn.setFixedSize(90, 30)
                m_btn_x = center_x - m_btn.width() - side_spacing
                m_btn_y = (ui.header_frame.height() - m_btn.height()) // 2
                m_btn.move(m_btn_x, m_btn_y)

                m_btn.setStyleSheet(ui.play_btn.styleSheet())

                if not hasattr(self, 'left_separator'):
                    self.left_separator = QtWidgets.QFrame(ui.header_frame)
                    self.left_separator.setFrameShape(QtWidgets.QFrame.Shape.VLine)
                    self.left_separator.setStyleSheet(separator_style)
                    self.left_separator.setGeometry(m_btn.x() - side_spacing, (ui.header_frame.height() - 20) // 2, 1, 20)
            else:
                ui.tab_installed_mods_btn.hide()
                self.right_separator.hide()


        if hasattr(ui, 'online_frame') and hasattr(ui, 'ping_frame') and hasattr(ui, 'header_frame'):
            ui.online_frame.setParent(ui.header_frame)
            ui.ping_frame.setParent(ui.header_frame)

            ui.online_frame.setFixedSize(165, 32)
            ui.ping_frame.setFixedSize(65, 32)

            ui.online_frame.setStyleSheet("""
                QFrame {
                    background-color: rgba(40, 40, 40, 165);
                    border-radius: 4px;
                    border: none;
                }
            """)
            ui.ping_frame.setStyleSheet("border: none; border-radius: 4px;")

            spacing = 5
            ping_x = ui.header_frame.width() - spacing - ui.ping_frame.width()
            online_x = ping_x - spacing - ui.online_frame.width()
            y_pos = (ui.header_frame.height() - 32) // 2

            ui.online_frame.move(online_x, y_pos)
            ui.ping_frame.move(ping_x, y_pos)

            if ui.online_frame.layout():
                ui.online_frame.layout().setContentsMargins(4, 0, 4, 0)
                ui.online_frame.layout().setSpacing(9)
            if ui.ping_frame.layout():
                ui.ping_frame.layout().setContentsMargins(5, 0, 5, 0)

            if hasattr(ui, 'online_gif_label'):
                ui.online_gif_label.setFixedSize(28, 28)
                if hasattr(ui, 'static_pixmap') and not ui.static_pixmap.isNull():
                    ui.static_pixmap = ui.static_pixmap.scaled(32, 32, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
                    ui.online_gif_label.setPixmap(ui.static_pixmap)
                if hasattr(ui, 'movie'):
                    ui.movie.setScaledSize(QtCore.QSize(32, 32))
            if hasattr(ui, 'online_label'):
                ui.online_label.setFont(QFont("sans-serif", 10, QFont.Weight.Bold))
            if hasattr(ui, 'ping_label'):
                ui.ping_label.setFont(QFont("sans-serif", 9, QFont.Weight.Bold))

            if hasattr(ui, 'min_btn'):
                ui.min_btn.hide()

            ui.online_frame.show()
            ui.ping_frame.show()
            ui.online_frame.raise_()
            ui.ping_frame.raise_()

        if hasattr(ui, 'container_frame'):
            ui.container_frame.setStyleSheet("""
                QFrame {
                    background-color: rgba(40, 40, 40, 100);
                    border-radius: 10px;
                    border: 1px solid rgba(255, 255, 255, 40);
                }
            """)
            ui.container_frame.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)

        if hasattr(ui, 'fade_overlay'):
            ui.fade_overlay.setStyleSheet("""
                background: qlineargradient(
                    x1:0, y1:1, x2:0, y2:0,        
                    stop:0 rgba(40,40,40,255),     
                    stop:1 rgba(40,40,40,0)       
                );
                border: none;
                border-bottom-left-radius: 10px; 
                border-bottom-right-radius: 10px;
            """)
        if hasattr(ui, 'fade_overlay2'):
            ui.fade_overlay2.setStyleSheet("""
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(40,40,40,255),
                    stop:1 rgba(40,40,40,0)
                );
                border: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            """)

    def toggle_news(self):
        self.news_expanded = not self.news_expanded
        self.toggle_news_btn.is_collapsed_mode = not self.news_expanded
        self.toggle_news_btn.animate_rotation(not self.news_expanded)
        self.toggle_news_btn.setText("−" if self.news_expanded else "+")
        self._run_news_toggle_animation()

    # noinspection PyUnresolvedReferences
    def _run_news_toggle_animation(self):
        ui = self.app.ui
        if not hasattr(ui, 'container_frame'): return

        self._news_anim_token = getattr(self, '_news_anim_token', 0) + 1
        token = self._news_anim_token

        expanded_w, expanded_h = 420, 300
        collapsed_w, collapsed_h = 56, 56
        start_x, start_y = 20, 60

        if hasattr(self, 'news_anim_group') and self.news_anim_group.state() == QtCore.QAbstractAnimation.State.Running:
            self.news_anim_group.stop()

        self.news_anim_group = QtCore.QSequentialAnimationGroup()

        if not self.news_expanded:
            height_collapse_group = QtCore.QParallelAnimationGroup()
            
            anim_h_frame = QtCore.QPropertyAnimation(ui.container_frame, b"geometry")
            anim_h_frame.setDuration(200)
            anim_h_frame.setStartValue(ui.container_frame.geometry())
            anim_h_frame.setEndValue(QtCore.QRect(start_x, start_y, expanded_w, collapsed_h))
            
            anim_h_fade1 = QtCore.QPropertyAnimation(ui.fade_overlay, b"geometry")
            anim_h_fade1.setDuration(200)
            anim_h_fade1.setEndValue(QtCore.QRect(0, 0, expanded_w, collapsed_h))
            
            anim_h_fade2 = QtCore.QPropertyAnimation(ui.fade_overlay2, b"geometry")
            anim_h_fade2.setDuration(200)
            anim_h_fade2.setEndValue(QtCore.QRect(0, 0, expanded_w, collapsed_h))
            
            height_collapse_group.addAnimation(anim_h_frame)
            height_collapse_group.addAnimation(anim_h_fade1)
            height_collapse_group.addAnimation(anim_h_fade2)
            
            width_collapse_group = QtCore.QParallelAnimationGroup()
            
            anim_w_frame = QtCore.QPropertyAnimation(ui.container_frame, b"geometry")
            anim_w_frame.setDuration(200)
            anim_w_frame.setStartValue(QtCore.QRect(start_x, start_y, expanded_w, collapsed_h))
            anim_w_frame.setEndValue(QtCore.QRect(start_x, start_y, collapsed_w, collapsed_h))
            
            anim_w_fade1 = QtCore.QPropertyAnimation(ui.fade_overlay, b"geometry")
            anim_w_fade1.setDuration(200)
            anim_w_fade1.setEndValue(QtCore.QRect(0, 0, collapsed_w, collapsed_h))
            
            anim_w_fade2 = QtCore.QPropertyAnimation(ui.fade_overlay2, b"geometry")
            anim_w_fade2.setDuration(200)
            anim_w_fade2.setEndValue(QtCore.QRect(0, 0, collapsed_w, collapsed_h))
            
            width_collapse_group.addAnimation(anim_w_frame)
            width_collapse_group.addAnimation(anim_w_fade1)
            width_collapse_group.addAnimation(anim_w_fade2)
            
            self.news_anim_group.addAnimation(height_collapse_group)
            self.news_anim_group.addAnimation(width_collapse_group)
            
            height_collapse_group.finished.connect(ui.news_page.hide)
            QTimer.singleShot(200, lambda token=token: ui.news_content.layout().setEnabled(False) if token == self._news_anim_token else None)
            QTimer.singleShot(200, lambda token=token: self.toggle_news_btn.raise_() if token == self._news_anim_token else None)
            ui.news_page.show()

            ui.news_content.layout().activate()
            final_h = expanded_h

            width_expand_group = QtCore.QParallelAnimationGroup()
            
            anim_w_frame = QtCore.QPropertyAnimation(ui.container_frame, b"geometry")
            anim_w_frame.setDuration(200)
            anim_w_frame.setStartValue(ui.container_frame.geometry())
            anim_w_frame.setEndValue(QtCore.QRect(start_x, start_y, expanded_w, collapsed_h))
            
            anim_w_fade1 = QtCore.QPropertyAnimation(ui.fade_overlay, b"geometry")
            anim_w_fade1.setDuration(200)
            anim_w_fade1.setEndValue(QtCore.QRect(0, 0, expanded_w, collapsed_h))
            
            anim_w_fade2 = QtCore.QPropertyAnimation(ui.fade_overlay2, b"geometry")
            anim_w_fade2.setDuration(200)
            anim_w_fade2.setEndValue(QtCore.QRect(0, 0, expanded_w, collapsed_h))
            
            width_expand_group.addAnimation(anim_w_frame)
            width_expand_group.addAnimation(anim_w_fade1)
            width_expand_group.addAnimation(anim_w_fade2)
            
            height_expand_group = QtCore.QParallelAnimationGroup()
            
            anim_h_frame = QtCore.QPropertyAnimation(ui.container_frame, b"geometry")
            anim_h_frame.setDuration(200)
            anim_h_frame.setStartValue(QtCore.QRect(start_x, start_y, expanded_w, collapsed_h))
            anim_h_frame.setEndValue(QtCore.QRect(start_x, start_y, expanded_w, final_h))
            
            anim_h_fade1 = QtCore.QPropertyAnimation(ui.fade_overlay, b"geometry")
            anim_h_fade1.setDuration(200)
            anim_h_fade1.setEndValue(QtCore.QRect(0, final_h - 50, expanded_w - 10, 50))
            
            anim_h_fade2 = QtCore.QPropertyAnimation(ui.fade_overlay2, b"geometry")
            anim_h_fade2.setDuration(200)
            anim_h_fade2.setEndValue(QtCore.QRect(0, 0, expanded_w, 50))
            
            height_expand_group.addAnimation(anim_h_frame)
            height_expand_group.addAnimation(anim_h_fade1)
            height_expand_group.addAnimation(anim_h_fade2)
            
            self.news_anim_group.addAnimation(width_expand_group)
            self.news_anim_group.addAnimation(height_expand_group)
            
            self.toggle_news_btn.raise_()
            QTimer.singleShot(200, lambda token=token: ui.news_content.layout().setEnabled(True) if token == self._news_anim_token else None)

        def finalize(token=token):
            if token != self._news_anim_token:
                return
            if self.news_expanded:
                ui.container_frame.setGeometry(start_x, start_y, expanded_w, expanded_h)
                ui.fade_overlay.setGeometry(0, expanded_h - 50, expanded_w, 50)
                ui.fade_overlay2.setGeometry(0, 0, expanded_w, 50)
                ui.news_page.show()
                ui.news_content.layout().setEnabled(True)
            else:
                ui.container_frame.setGeometry(start_x, start_y, collapsed_w, collapsed_h)
                ui.fade_overlay.setGeometry(0, 0, collapsed_w, collapsed_h)
                ui.fade_overlay2.setGeometry(0, 0, collapsed_w, collapsed_h)
                ui.news_page.hide()
                ui.news_content.layout().setEnabled(False)
            self.toggle_news_btn.raise_()

        self.news_anim_group.finished.connect(finalize)
        self.news_anim_group.start()

    def on_web_tab_clicked(self):
        if not self._ensure_web_view():
            return
        ui = self.app.ui
        ui._current_tab_index = -1

        ui.bg3d.pause_render()
        
        ui.tab_news_btn.setChecked(False)
        ui.tab_settings_btn.setChecked(False)
        ui.tab_installed_mods_btn.setChecked(False)
        if hasattr(ui, 'modrinth_plugin_tab_btn') and ui.modrinth_plugin_tab_btn:
            ui.modrinth_plugin_tab_btn.setChecked(False)
            
        ui.container_frame.hide()
        ui.installed_mods_container.hide()
        ui.settings_container.hide()
        ui.information_container.hide()
        ui.moresettings_container.hide()
        ui.plugins_manager_container.hide()
        if hasattr(ui, 'modrinth_container') and ui.modrinth_container:
            ui.modrinth_container.hide()

        if hasattr(ui, 'buttons_block'):
            ui.buttons_block.hide()
        if hasattr(ui, 'waitlist') and ui.waitlist:
            ui.waitlist.hide()
            
        ui.dim_layer.show()
        self._animate_web_view(True)

    def _animate_web_view(self, show: bool):
        if not hasattr(self, 'web_view'):
            return
            
        ui = self.app.ui
        
        if hasattr(self, '_web_anim_group'):
            self._web_anim_group.stop()
            
        effect = self.web_view.graphicsEffect()
        if not isinstance(effect, QtWidgets.QGraphicsOpacityEffect):
            effect = QtWidgets.QGraphicsOpacityEffect(self.web_view)
            self.web_view.setGraphicsEffect(effect)
            
        target_pos = QtCore.QPoint(0, 40)
        slide_offset = 20
        
        group = QtCore.QParallelAnimationGroup()
        
        opacity_anim = QtCore.QPropertyAnimation(effect, b"opacity")
        opacity_anim.setDuration(300)
        
        pos_anim = QtCore.QPropertyAnimation(self.web_view, b"pos")
        pos_anim.setDuration(300)
        pos_anim.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        
        if show:
            self.web_view.show()
            self.web_view.raise_()
            ui.header_frame.raise_()
            
            opacity_anim.setStartValue(0.0)
            opacity_anim.setEndValue(1.0)
            
            pos_anim.setStartValue(QtCore.QPoint(target_pos.x() + slide_offset, target_pos.y()))
            pos_anim.setEndValue(target_pos)
        else:
            opacity_anim.setStartValue(effect.opacity())
            opacity_anim.setEndValue(0.0)
            
            pos_anim.setStartValue(self.web_view.pos())
            pos_anim.setEndValue(QtCore.QPoint(target_pos.x() + slide_offset, target_pos.y()))
            group.finished.connect(self.web_view.hide)
            
        group.addAnimation(opacity_anim)
        group.addAnimation(pos_anim)
        self._web_anim_group = group
        group.start()

    def on_other_tab_clicked(self):
        if hasattr(self, 'web_view') and self.web_view.isVisible():
            self.app.ui.bg3d.resume_render()
            self._animate_web_view(False)
            self.web_tab_btn.setChecked(False)
            self.web_view.setUrl(QUrl("https://cm2news.xyz"))
