import ctypes

import numpy as np
from OpenGL.GL import *

from .texture import Texture
from .model import ModelData
from .vertex import VERTEX_SIZE


FLOAT_SIZE = 4
STRIDE = VERTEX_SIZE * FLOAT_SIZE


class Mesh:
    """
    OpenGL Mesh.

    Отвечает только за GPU-ресурсы.
    Ничего не знает про OBJ, trimesh и загрузчики.
    """

    def __init__(self, model: ModelData):
        self.model = model

        self.texture = None

        self.vao = 0
        self.vbo = 0
        self.ebo = 0

        self.index_count = len(model.indices)

        self.uploaded = False

    # ------------------------------------------------------------------

    def upload(self):
        """
        Загружает модель в видеопамять.
        Вызывать только после создания OpenGL контекста.
        """

        if self.uploaded:
            return

        # ---------- Texture ----------

        if self.model.texture_path:
            self.texture = Texture(self.model.texture_path)

        # ---------- VAO ----------

        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)

        # ---------- VBO ----------

        self.vbo = glGenBuffers(1)

        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)

        glBufferData(
            GL_ARRAY_BUFFER,
            self.model.vertices.nbytes,
            self.model.vertices,
            GL_STATIC_DRAW,
        )

        # ---------- EBO ----------

        self.ebo = glGenBuffers(1)

        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, self.ebo)

        glBufferData(
            GL_ELEMENT_ARRAY_BUFFER,
            self.model.indices.nbytes,
            self.model.indices,
            GL_STATIC_DRAW,
        )

        # --------------------------------------------------------------
        # layout(location = 0) -> position
        # --------------------------------------------------------------

        glEnableVertexAttribArray(0)

        glVertexAttribPointer(
            0,
            3,
            GL_FLOAT,
            GL_FALSE,
            STRIDE,
            ctypes.c_void_p(0),
        )

        # --------------------------------------------------------------
        # layout(location = 1) -> normal
        # --------------------------------------------------------------

        glEnableVertexAttribArray(1)

        glVertexAttribPointer(
            1,
            3,
            GL_FLOAT,
            GL_FALSE,
            STRIDE,
            ctypes.c_void_p(3 * FLOAT_SIZE),
        )

        # --------------------------------------------------------------
        # layout(location = 2) -> uv
        # --------------------------------------------------------------

        glEnableVertexAttribArray(2)

        glVertexAttribPointer(
            2,
            2,
            GL_FLOAT,
            GL_FALSE,
            STRIDE,
            ctypes.c_void_p(6 * FLOAT_SIZE),
        )

        glBindVertexArray(0)

        self.uploaded = True

    # ------------------------------------------------------------------

    def bind(self):
        """
        Подготавливает меш к рендеру.
        """

        if not self.uploaded:
            return

        if self.texture is not None:
            self.texture.bind(0)

        glBindVertexArray(self.vao)

    # ------------------------------------------------------------------

    def unbind(self):
        """
        Отвязывает ресурсы OpenGL.
        """

        glBindVertexArray(0)

        glBindTexture(GL_TEXTURE_2D, 0)

    # ------------------------------------------------------------------

    def render(self):
        """
        Отрисовка меша.
        """

        if not self.uploaded:
            return

        self.bind()

        glDrawElements(
            GL_TRIANGLES,
            self.index_count,
            GL_UNSIGNED_INT,
            None
        )

        self.unbind()

    # ------------------------------------------------------------------

    def destroy(self):
        """
        Освобождение GPU ресурсов.
        """

        if self.texture is not None:
            self.texture.release()
            self.texture = None

        if self.vbo:
            glDeleteBuffers(1, [self.vbo])
            self.vbo = 0

        if self.ebo:
            glDeleteBuffers(1, [self.ebo])
            self.ebo = 0

        if self.vao:
            glDeleteVertexArrays(1, [self.vao])
            self.vao = 0

        self.uploaded = False


    @property
    def radius(self):
        return self.model.radius

    @property
    def center(self):
        return self.model.center

    @property
    def vertex_count(self):
        return len(self.model.vertices)

    @property
    def triangle_count(self):
        return self.index_count // 3

    def release_cpu_data(self):
        self.model.vertices = None
        self.model.indices = None