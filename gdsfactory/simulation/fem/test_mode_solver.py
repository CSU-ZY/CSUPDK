import numpy as np

from gdsfactory.generic_tech import get_layer_stack_generic
from gdsfactory.simulation.fem.mode_solver import compute_cross_section_modes
from gdsfactory.technology import LayerStack


def test_compute_cross_section_mode():

    filtered_layerstack = LayerStack(
        layers={
            k: get_layer_stack_generic().layers[k]
            for k in (
                "core",
                "clad",
                "slab90",
                "box",
            )
        }
    )

    filtered_layerstack.layers["core"].thickness = 0.2

    resolutions = {
        "core": {"resolution": 0.02, "distance": 2},
        "clad": {"resolution": 0.2, "distance": 1},
        "box": {"resolution": 0.2, "distance": 1},
        "slab90": {"resolution": 0.05, "distance": 1},
    }
    lams, basis, xs = compute_cross_section_modes(
        cross_section="rib",
        layerstack=filtered_layerstack,
        wl=1.55,
        num_modes=4,
        order=1,
        radius=np.inf,
        filename="mesh.msh",
        resolutions=resolutions,
    )

    assert len(lams) == 4


if __name__ == "__main__":

    test_compute_cross_section_mode()
