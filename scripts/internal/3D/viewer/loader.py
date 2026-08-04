import trimesh

from .vertex import *
from .utils import *
from .model import ModelData


def load_obj(path: str):

    ensure_exists(path)

    mesh = trimesh.load_mesh(path)

    mesh.remove_unreferenced_vertices()

    mesh.fix_normals()

    center = center_mesh(mesh)

    radius = mesh_radius(mesh)

    vertices = build_vertex_buffer(mesh)

    indices = build_index_buffer(mesh).astype(np.uint32)

    texture = find_texture(path)

    return ModelData(
        vertices,
        indices,
        center,
        radius,
        texture
    )

