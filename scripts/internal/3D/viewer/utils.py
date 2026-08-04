import os
from pathlib import Path


IMAGE_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".tga",
    ".webp",
)


def ensure_exists(path: str):
    """
    Проверяет существование файла.
    """

    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    return path


def change_extension(path: str, ext: str):
    """
    model.obj -> model.mtl
    """

    return str(Path(path).with_suffix(ext))


def read_mtl_texture(mtl_path: str):
    """
    Ищет map_Kd в MTL.

    Возвращает абсолютный путь к текстуре
    или None.
    """

    ensure_exists(mtl_path)

    folder = os.path.dirname(mtl_path)

    with open(mtl_path, "r", encoding="utf8") as file:

        for line in file:

            line = line.strip()

            if not line.startswith("map_Kd"):
                continue

            texture = line.split(maxsplit=1)[1]

            texture = texture.replace("\\", os.sep)

            texture = os.path.join(folder, texture)

            if os.path.isfile(texture):
                return texture

    return None


def find_texture(obj_path: str):
    """
    Автоматически ищет текстуру.

    1. model.mtl
    2. map_Kd
    """

    mtl = change_extension(obj_path, ".mtl")

    if os.path.isfile(mtl):

        texture = read_mtl_texture(mtl)

        if texture:
            return texture

    return None


def normalize_path(path: str):
    """
    Делает абсолютный путь.
    """

    return os.path.abspath(
        os.path.expanduser(path)
    )
