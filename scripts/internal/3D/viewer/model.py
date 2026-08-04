from dataclasses import dataclass
import numpy as np


@dataclass(slots=True)
class ModelData:

    vertices: np.ndarray

    indices: np.ndarray

    center: np.ndarray

    radius: float

    texture_path: str | None