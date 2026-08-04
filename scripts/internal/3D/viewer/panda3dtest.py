import sys
from dataclasses import dataclass, field
import gltf
from panda3d.core import VirtualFileSystem
import simplepbr
from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt, QTimer, QRect
from PyQt6.QtGui import QCursor
from panda3d import direct
from panda3d.core import Filename, get_model_path
from panda3d.core import loadPrcFileData, WindowProperties, Vec3, Vec4, AmbientLight, DirectionalLight, Shader, \
    PointLight, TransparencyAttrib, AntialiasAttrib, TextNode, Point2, DynamicTextFont, NodePath, \
    LoaderFileTypeRegistry, TexturePool, DepthOffsetAttrib
import os
from direct.showbase.ShowBase import ShowBase

loadPrcFileData("", """
framebuffer-srgb true
framebuffer-multisample true
multisamples 8
""")

os.environ['PANDA_LOADER_PREFER_ASSIMP'] = '0'

loadPrcFileData("", "notify-level-assimp debug")
loadPrcFileData("", "notify-level-loader debug")
loadPrcFileData("", "load-file-type p3assimp #f")
loadPrcFileData("", "model-cache-dir #f")


def get_base_path():
    try:
        return sys._MEIPASS
    except Exception:
        return os.path.dirname(os.path.abspath(__file__))


get_model_path().prepend_directory(Filename.from_os_specific(get_base_path()))

if hasattr(sys, '_MEIPASS'):
    vfs = VirtualFileSystem.getGlobalPtr()
    vfs.mount(Filename.from_os_specific(sys._MEIPASS), ".", 0)
    vfs.mount(Filename.from_os_specific(sys._MEIPASS), "/", 0)
    vfs.mount(Filename.from_os_specific(os.path.join(sys._MEIPASS, "simplepbr")), "/simplepbr", 0)
    vfs.mount(Filename.from_os_specific(os.path.join(sys._MEIPASS, "shaders")), "/shaders", 0)
    pbr_path = os.path.join(sys._MEIPASS, 'simplepbr')
    if os.path.exists(pbr_path):
        get_model_path().append_directory(pbr_path)


@dataclass
class ParallaxConfig:
    model_path: str = "background.glb"
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


class BasePandaWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        self.panda = None
        self._timer = None

        QTimer.singleShot(0, self._internal_init_panda)

    def _internal_init_panda(self):
        hwnd = int(self.winId())
        os.environ["PANDA_WINDOW_HANDLE"] = str(hwnd)
        os.environ["PANDA_WINDOW_PARENT"] = "1"

        self.panda = ShowBase(windowType="none")

        props = WindowProperties()
        props.setParentWindow(hwnd)
        props.setOrigin(0, 0)
        props.setSize(self.width(), self.height())
        self.panda.openDefaultWindow(props=props)

        pline = simplepbr.init(
            enable_shadows=True,
            use_normal_maps=True,
            use_occlusion_maps=True,
            max_lights=8,
            sdr_lut_factor=10.0
        )
        print(f"DEBUG: simplepbr pipeline initialized: {pline is not None}")

        self.panda.render.setAntialias(AntialiasAttrib.MAuto)

        print(self.panda.win.getGsg().getDriverVendor())
        print(self.panda.win.getGsg().getDriverRenderer())
        print(self.panda.win.getGsg().getDriverVersion())
        self.panda.disableMouse()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.panda.taskMgr.step)
        self._timer.start(20)
        self.setup_scene()

    def setup_scene(self):
        pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.panda and self.panda.win:
            props = WindowProperties()
            props.setSize(self.width(), self.height())
            self.panda.win.requestProperties(props)


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
        font = DynamicTextFont("minecraft.ttf")
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


class ParallaxPandaWidget(BasePandaWidget):
    def __init__(self, config: ParallaxConfig = None, parent=None):
        self.cfg = config or ParallaxConfig()

        self.cur_h = self.cfg.base_h
        self.cur_p = self.cfg.base_p
        self.parallax_enabled = True

        super().__init__(parent)

    def setup_scene(self):

        registry = LoaderFileTypeRegistry.getGlobalPtr()
        old_type = registry.getTypeFromExtension("glb")
        if old_type:
            registry.unregisterType(old_type)

        registry.registerType(gltf._loader.GltfLoader())

        print(f"DEBUG: Active loader for glb: {registry.getTypeFromExtension('glb')}")
        TexturePool.releaseAllTextures()

        path = Filename.from_os_specific(
            os.path.join(get_base_path(), self.cfg.model_path)
        )

        self.model = self.panda.loader.loadModel(path)
        self.model.reparentTo(self.panda.render)
        self.model.setScale(self.cfg.model_scale)
        self.model.setPos(self.cfg.model_pos)

        print("Empty:", self.model.isEmpty())
        textures = self.model.findAllTextures()
        print("Textures:", len(textures))

        self.player_label = BillboardLabel(
            self.panda,
            "Steve",
            Vec3(-100, -130, 80),
            scale=30
        )
        self.player_label.np.setPos(-100, -130, 80)

        print(self.model.analyze())

        self.panda.render.clearLight()
        self._setup_lights()

        self.panda.taskMgr.add(self._parallax_task, "parallax_task")

        self.sky_dome = self.panda.loader.loadModel("models/smiley")
        self.sky_dome.reparentTo(self.panda.render)
        self.sky_dome.setScale(500)
        self.sky_dome.setTwoSided(True)
        self.sky_dome.setDepthWrite(False)
        self.sky_dome.setBin("background", 0)

        sky_shader = Shader.load(Shader.SL_GLSL, vertex="shaders/sky.vert",
                                 fragment="shaders/sky.frag"
                                 )
        self.sky_dome.setShader(sky_shader)

        self.sun_direction = -self.sun_light_node.getQuat().getForward()
        self.sun_direction.normalize()

        self.sky_dome.setShaderInput("sun_dir", self.sun_direction)

        self.panda.render.setShaderInput("lights", self.sun_light_node)

    def _setup_lights(self):
        amb = AmbientLight("ambient_light")
        amb.setColor(self.cfg.ambient_color)
        self.ambient_light_node = self.panda.render.attachNewNode(amb)
        self.panda.render.setLight(self.ambient_light_node)

        sun = DirectionalLight("sun_light")
        sun.setColor(self.cfg.sun_color)
        sun.setShadowCaster(True, 4096, 4096)

        lens = sun.getLens()
        lens.setFilmSize(500, 500)
        lens.setNearFar(1, 500)

        self.model.setAttrib(
            DepthOffsetAttrib.make(2)
        )

        self.sun_light_node = self.panda.render.attachNewNode(sun)
        self.sun_light_node.setHpr(self.cfg.sun_hpr)
        self.panda.render.setLight(self.sun_light_node)

        for np in self.model.findAllMatches("**"):
            if "water" in np.getName().lower():
                np.setTransparency(TransparencyAttrib.MAlpha)
                np.setDepthWrite(False)

    def _parallax_task(self, task):
        global_mouse_pos = QCursor.pos()

        widget_global_top_left = self.mapToGlobal(self.rect().topLeft())
        widget_rect = QRect(widget_global_top_left, self.size())
        if self.parallax_enabled:
            if widget_rect.contains(global_mouse_pos):
                local_pos = self.mapFromGlobal(global_mouse_pos)
                mx = (local_pos.x() / self.width() - 0.5) * -2
                my = (local_pos.y() / self.height() - 0.5) * -2
            else:
                mx = my = 0.0

            target_h = self.cfg.base_h + mx * self.cfg.max_angle
            target_p = self.cfg.base_p + my * self.cfg.max_angle

            self.cur_h += (target_h - self.cur_h) * self.cfg.smoothness
            self.cur_p += (target_p - self.cur_p) * self.cfg.smoothness

            self.panda.camera.setPos(self.cfg.camera_pos)
            self.panda.camera.setHpr(self.cur_h, self.cur_p, self.cfg.base_r)
            if not hasattr(self, "textnodetest"):
                self.textnodetest = BillboardLabel(self.panda, "hen1ck")
                self.textnodetest.reparentTo(self.panda.render)
                self.textnodetest.setPos(-101.6, -130, 63.3)
                self.textnodetest.setScale(1.5)

            return task.cont
        else:
            self.panda.camera.setHpr(
                self.cfg.base_h,
                self.cfg.base_p,
                self.cfg.base_r
            )
            return task.cont

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

# if __name__ == "__main__":
#     app = QtWidgets.QApplication(sys.argv)
#     win = QtWidgets.QMainWindow()
#
#     custom_config = ParallaxConfig(
#         model_path="background.glb",
#         max_angle=4.0,
#         smoothness=0.08,
#         sun_color=Vec4(0.5, 0.35, 0.2, 1)
#     )
#
#     pw = ParallaxPandaWidget(config=custom_config)
#     win.setCentralWidget(pw)
#
#     win.resize(1024, 580)
#     win.show()
#     sys.exit(app.exec())
