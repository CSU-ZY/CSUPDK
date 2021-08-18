from functools import partial
from typing import Any, Dict, Optional, Tuple

from gdsfactory.cell import cell
from gdsfactory.component import Component
from gdsfactory.components.compass import compass
from gdsfactory.tech import LAYER
from gdsfactory.types import ComponentOrFactory, Layer, PortName


@cell
def pad(
    width: float = 100.0,
    height: Optional[float] = None,
    layer: Layer = LAYER.M3,
    layer_to_inclusion: Optional[Dict[Layer, float]] = None,
) -> Component:
    """Rectangular pad with 4 ports (1, 2, 3, 4)

    Args:
        width: pad width
        height: pad height
        layer: pad layer
        layer_to_inclusion: for example {(3,0): +3, (4, 0): -4} adds
            layer (3,0) 3um inside and layer (4,0) 4 um outside
    """
    height = height or width
    layer_to_inclusion = layer_to_inclusion or {}
    c = Component()
    rect = compass(size=(width, height), layer=layer)
    c_ref = c.add_ref(rect)
    c.add_ports(c_ref.ports)
    c.absorb(c_ref)

    for layer, inclusion in layer_to_inclusion.items():
        c.add_ref(
            compass(size=(width - 2 * inclusion, height - 2 * inclusion), layer=layer)
        )

    return c


@cell
def pad_array(
    pad: ComponentOrFactory = pad,
    pitch: float = 150.0,
    n: int = 6,
    port_names: Tuple[PortName, ...] = (4,),
    pad_settings: Optional[Dict[str, Any]] = None,
    axis: str = "x",
) -> Component:
    """Returns 1D array of rectangular pads

    Args:
        pad: pad element
        pitch: x spacing
        n: number of pads
        port_names: list of port names (1, 2, 3, 4) per pad
        pad_settings: settings for pad if pad is callable
        axis: x or y
    """
    c = Component()
    pad_settings = pad_settings or {}
    pad = pad(**pad_settings) if callable(pad) else pad
    port_names = list(port_names)

    for i in range(n):
        p = c << pad
        if axis == "x":
            p.x = i * pitch
        elif axis == "y":
            p.y = i * pitch
        else:
            raise ValueError(f"Invalid axis {axis} not in (x, y)")
        for port_name in port_names:
            port_name_new = f"{port_name}_{i}"
            c.add_port(name=port_name_new, port=p.ports[port_name])

    return c


pad_array180 = partial(pad_array, port_names=(1,))
pad_array90 = partial(pad_array, port_names=(2,))
pad_array0 = partial(pad_array, port_names=(3,))
pad_array270 = partial(pad_array, port_names=(4,))


@cell
def pad_array_2d(
    pad: ComponentOrFactory = pad,
    pitch_x: float = 150.0,
    pitch_y: float = 150.0,
    cols: int = 3,
    rows: int = 3,
    port_names: Tuple[PortName, ...] = (2,),
    **kwargs,
) -> Component:
    """Returns 2D array of rectangular pads

    Args:
        pad: pad element
        pitch_x: horizontal x spacing
        pitch_y: vertical y spacing
        cols: number of cols
        rows: number of rows
        port_names: list of port names (N, S, W, E) per pad
        **kwargs: settings for pad if pad is callable
    """
    c = Component()
    pad = pad(**kwargs) if callable(pad) else pad
    port_names = list(port_names)

    for j in range(rows):
        for i in range(cols):
            p = c << pad
            p.x = i * pitch_x
            p.y = j * pitch_y
            for port_name in port_names:
                if port_name not in p.ports:
                    raise ValueError(f"{port_name} not in {list(p.ports.keys())}")
                port_name_new = f"{port_name}_{j}_{i}"
                c.add_port(port=p.ports[port_name], name=port_name_new)

    return c


if __name__ == "__main__":
    # c = pad()

    # c = pad(layer_to_inclusion={(3, 0): 10})
    # print(c.ports)
    # c = pad(width=10, height=10)
    # print(c.ports.keys())
    # print(c.settings['spacing'])
    # c = pad_array_2d(cols=2, rows=3, port_names=(1,))
    c = pad_array270()
    c.show()
