from OpenGL.GL import *
from OpenGL.GL import glUniformMatrix4fv
import glm


class Shader:

    def __init__(self, vertex_path, fragment_path):

        with open(vertex_path, "r", encoding="utf8") as f:
            vertex_source = f.read()

        with open(fragment_path, "r", encoding="utf8") as f:
            fragment_source = f.read()

        self.program = self._create_program(
            vertex_source,
            fragment_source
        )

    def use(self):
        glUseProgram(self.program)

    def set_matrix(self, name, matrix):

        location = glGetUniformLocation(
            self.program,
            name
        )

        glUniformMatrix4fv(location, 1, GL_FALSE, glm.value_ptr(matrix))


    def set_vec3(self, name, value):

        location = glGetUniformLocation(
            self.program,
            name
        )

        glUniform3f(
            location,
            value.x,
            value.y,
            value.z
        )

    def set_int(self, name, value):

        location = glGetUniformLocation(
            self.program,
            name
        )

        glUniform1i(location, value)

    def _compile(self, source, shader_type):

        shader = glCreateShader(shader_type)

        glShaderSource(shader, source)

        glCompileShader(shader)

        if not glGetShaderiv(shader, GL_COMPILE_STATUS):

            error = glGetShaderInfoLog(shader).decode()

            raise RuntimeError(error)

        return shader

    def _create_program(self, vertex, fragment):

        vs = self._compile(vertex, GL_VERTEX_SHADER)

        fs = self._compile(fragment, GL_FRAGMENT_SHADER)

        program = glCreateProgram()

        glAttachShader(program, vs)

        glAttachShader(program, fs)

        glLinkProgram(program)

        if not glGetProgramiv(program, GL_LINK_STATUS):

            raise RuntimeError(
                glGetProgramInfoLog(program).decode()
            )

        glDeleteShader(vs)

        glDeleteShader(fs)

        return program