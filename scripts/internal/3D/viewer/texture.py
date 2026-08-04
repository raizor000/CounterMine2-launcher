from OpenGL.GL import *
from OpenGL.raw.GL.EXT.texture_filter_anisotropic import GL_TEXTURE_MAX_ANISOTROPY_EXT, \
    GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT
from PIL import Image


class Texture:
    def __init__(self, path):
        self.path = path
        self.id = glGenTextures(1)

        self.width = 0
        self.height = 0

        self.load()

    def load(self):
        image = Image.open(self.path)

        # OBJ обычно хранит текстуры так
        image = image.convert("RGBA")
        image = image.transpose(Image.FLIP_TOP_BOTTOM)

        self.width, self.height = image.size
        data = image.tobytes()

        glBindTexture(GL_TEXTURE_2D, self.id)

        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            self.width,
            self.height,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            data
        )

        glGenerateMipmap(GL_TEXTURE_2D)

        # Фильтрация
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        # Повторение текстуры
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)

        # Если драйвер поддерживает — включаем анизотропную фильтрацию
        try:
            max_aniso = glGetFloatv(GL_MAX_TEXTURE_MAX_ANISOTROPY_EXT)
            glTexParameterf(
                GL_TEXTURE_2D,
                GL_TEXTURE_MAX_ANISOTROPY_EXT,
                max_aniso
            )
        except Exception:
            pass

        glBindTexture(GL_TEXTURE_2D, 0)

    def bind(self, slot=0):
        glActiveTexture(GL_TEXTURE0 + slot)
        glBindTexture(GL_TEXTURE_2D, self.id)

    def release(self):
        if self.id:
            glDeleteTextures([self.id])
            self.id = 0