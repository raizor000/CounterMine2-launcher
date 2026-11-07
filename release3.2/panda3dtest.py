from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt, QTimer, QEvent, QRect
import sys, os

from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QApplication


class PandaWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_PaintOnScreen)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        from panda3d.core import loadPrcFileData

        loadPrcFileData("", "framebuffer-srgb true")

        self.panda = None
        self.mouse_x = 0.0
        self.mouse_y = 0.0
        self.cam_x = 300
        self.cam_y = 200
        self.base_h = 100  # поворот влево (градусы)
        self.base_p = -15  # лёгкий наклон вниз
        self.base_r = 0

        self.cur_h = self.base_h
        self.cur_p = self.base_p
        QApplication.instance().installEventFilter(self)

        self.mouse_inside = False
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        QTimer.singleShot(0, self.init_panda)  # ВАЖНО

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseMove:
            pos = self.mapFromGlobal(event.globalPos())
            self.mouse_inside = (
                    0 <= pos.x() <= self.width() and
                    0 <= pos.y() <= self.height()
            )
        return False

    def init_panda(self):
        hwnd = int(self.winId())
        os.environ["PANDA_WINDOW_HANDLE"] = str(hwnd)
        os.environ["PANDA_WINDOW_PARENT"] = "1"

        from direct.showbase.ShowBase import ShowBase
        self.panda = ShowBase(windowType="none")

        from panda3d.core import WindowProperties
        props = WindowProperties()
        props.setParentWindow(hwnd)
        props.setOrigin(0, 0)
        props.setSize(self.width(), self.height())

        self.panda.openDefaultWindow(props=props)
        from panda3d.core import Vec3

        from PyQt6.QtWidgets import QApplication
        self.app = QApplication.instance()

        self.panda.disableMouse()
        model = self.panda.loader.loadModel("3D/scene1.glb")
        model.reparentTo(self.panda.render)
        model.setScale(10)
        model.setPos(0, 0, 0)
        # model.setColor(1, 0, 0, 1)
        self.panda.disableMouse()



        self.panda.render.clearLight()
        from panda3d.core import AmbientLight, Vec4

        amb = AmbientLight("amb")
        amb.setColor(Vec4(0.25, 0.25, 0.25, 1))
        amb_np = self.panda.render.attachNewNode(amb)
        self.panda.render.setLight(amb_np)

        from panda3d.core import DirectionalLight

        # sun = DirectionalLight("sun")
        # sun.setColor(Vec4(0.9, 0.9, 0.9, 1))
        # sun_np = self.panda.render.attachNewNode(sun)
        # sun_np.setHpr(45, -90, 0)  # направление
        # self.panda.render.setLight(sun_np)

        fill = DirectionalLight("fill")
        fill.setColor(Vec4(0.3, 0.3, 0.35, 1))
        fill_np = self.panda.render.attachNewNode(fill)
        fill_np.setHpr(135, -30, 0)
        self.panda.render.setLight(fill_np)

        from panda3d.core import PointLight, Vec4

        pl = PointLight("lamp")
        pl.setColor(Vec4(0.9, 0.855, 0.81, 1))
        pl.setAttenuation((1, 0.025, 0.0012))

        pl_np = self.panda.render.attachNewNode(pl)
        pl_np.setPos(290, 80, 170)

        self.panda.render.setLight(pl_np)

        self.panda.render.clearLight()
        model.setShaderAuto()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.panda.taskMgr.step)
        self.timer.start(4)

        def cam_task(task):
            self.panda.camera.setH(task.time * 3)
            return task.cont
        # self.panda.taskMgr.add(cam_task, "cam")

        def parallax_task(task):
            # ГЛОБАЛЬНАЯ позиция мыши
            gpos = QCursor.pos()

            # ГЛОБАЛЬНЫЙ прямоугольник PandaWidget
            top_left = self.mapToGlobal(self.rect().topLeft())
            rect = QRect(top_left, self.size())

            if rect.contains(gpos):
                local = self.mapFromGlobal(gpos)
                mx = (local.x() / self.width() - 0.5) * -2
                my = (local.y() / self.height() - 0.5) * -2
            else:
                mx = my = 0

            max_angle = 6.0
            smooth = 0.02

            target_h = self.base_h + mx * max_angle
            target_p = self.base_p + my * max_angle

            self.cur_h += (target_h - self.cur_h) * smooth
            self.cur_p += (target_p - self.cur_p) * smooth

            self.panda.camera.setPos(290, 80, 70)
            self.panda.camera.setHpr(self.cur_h, self.cur_p, 0)

            return task.cont

        self.panda.taskMgr.add(parallax_task, "parallax")

    def resizeEvent(self, e):
        if self.panda and self.panda.win:
            wp = self.panda.win.getProperties()
            wp.setSize(self.width(), self.height())
            self.panda.win.requestProperties(wp)

    def enterEvent(self, event):
        self.mouse_inside = True

    def leaveEvent(self, event):
        self.mouse_inside = False


app = QtWidgets.QApplication(sys.argv)
win = QtWidgets.QMainWindow()
pw = PandaWidget()
win.setCentralWidget(pw)
win.resize(900, 600)
win.show()
sys.exit(app.exec())
