import numpy as np


VERTEX_SIZE = 8  # x y z nx ny nz u v


def build_vertex_buffer(mesh):
    """
    Преобразует trimesh.Trimesh в массив float32:

    x y z nx ny nz u v
    """

    vertices = mesh.vertices
    normals = mesh.vertex_normals

    if hasattr(mesh.visual, "uv") and mesh.visual.uv is not None:
        uvs = mesh.visual.uv
    else:
        uvs = np.zeros((len(vertices), 2), dtype=np.float32)

    result = np.empty((len(vertices), VERTEX_SIZE), dtype=np.float32)

    result[:, 0:3] = vertices
    result[:, 3:6] = normals
    result[:, 6:8] = uvs

    return result

def build_index_buffer(mesh):
    return mesh.faces.astype(np.uint32).flatten()

def center_mesh(mesh):
    bounds = mesh.bounds

    center = (bounds[0] + bounds[1]) / 2

    mesh.vertices -= center

    return center

def mesh_radius(mesh):
    bounds = mesh.bounds

    size = bounds[1] - bounds[0]

    return float(np.max(size))

