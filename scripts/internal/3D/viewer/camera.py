from pyglm import glm


class Camera:
    def __init__(self):
        # Положение камеры
        self.position = glm.vec3(0.0, 0.0, 5.0)

        # Точка, куда смотрим
        self.target = glm.vec3(0.0, 0.0, 0.0)

        # Верх
        self.up = glm.vec3(0.0, 1.0, 0.0)

        # Настройки перспективы
        self.fov = 45.0
        self.near = 0.1
        self.far = 1000.0
        self.aspect = 1.0

        # Параллакс
        self.parallax = glm.vec2(0.0)

    def resize(self, width: int, height: int):
        self.aspect = max(width, 1) / max(height, 1)

    def get_projection(self):
        return glm.perspective(
            glm.radians(self.fov),
            self.aspect,
            self.near,
            self.far
        )

    def get_view(self):
        pos = glm.vec3(
            self.position.x + self.parallax.x,
            self.position.y + self.parallax.y,
            self.position.z,
        )

        return glm.lookAt(
            pos,
            self.target,
            self.up
        )

    def set_parallax(self, x: float, y: float):
        self.parallax.x = x
        self.parallax.y = y

    def center_on_bounds(self, bounds):
        """
        bounds = (min_xyz, max_xyz)
        """

        minimum, maximum = bounds

        center = (minimum + maximum) / 2
        size = maximum - minimum

        radius = max(size)

        self.target = glm.vec3(*center)

        self.position = glm.vec3(
            center[0],
            center[1],
            center[2] + radius * 1.8
        )