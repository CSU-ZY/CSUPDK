from typing import List, Tuple

import gdsfactory as gf
from gdsfactory.cell import cell
from gdsfactory.component import Component
from gdsfactory.port import port_array
from gdsfactory.routing.routing import route_basic
from gdsfactory.routing.utils import direction_ports_from_list_ports, flip
from gdsfactory.types import PortName


@cell
def fanout_component(
    component: Component,
    port_names: Tuple[PortName, ...],
    pitch: Tuple[float, float] = (0.0, 20.0),
    dx: float = 20.0,
    rename_ports: bool = True,
    **kwargs,
) -> Component:
    """Returns component with Sbend fanout routes.

    Args:
        component: to package
        ports: list of ports
        pitch: target port spacing for new component
        dx: how far the fanout in x direction
        rename_ports: renames ports
        kwargs: for route_basic
    """

    c = Component()
    comp = component() if callable(component) else component
    ref = c.add_ref(comp)
    ref.movey(-comp.y)

    ports1 = [p for p in ref.ports.values() if p.name in port_names]
    port = ports1[0]
    port_extended_x = port.get_extended_midpoint(dx)[0]
    port_settings = port.settings.copy()

    port_settings.pop("name")
    port_settings.update(midpoint=(port_extended_x, 0))
    port_settings.update(orientation=(port.angle + 180) % 360)

    ports2 = port_array(n=len(ports1), pitch=pitch, **port_settings)

    for i, (p1, p2) in enumerate(zip(ports1, ports2)):
        path = route_basic(port1=p1, port2=p2, **kwargs)
        path_ref = path.ref()
        c.add(path_ref)
        c.add_port(f"new_{i}", port=flip(p2))

    for port in ref.ports.values():
        if port.name not in port_names:
            c.add_port(port.name, port=port)

    if rename_ports:
        c.auto_rename_ports()
    return c


def fanout_ports(
    ports: List[gf.Port],
    pitch: Tuple[float, float] = (0.0, 20.0),
    dx: float = 20.0,
    **kwargs,
) -> List[gf.types.Route]:
    """Returns fanout Sbend routes.

    Args:
        ports: list of ports
        pitch: target port spacing for new component
        dx: how far the fanout
        kwargs: for route_basic
    """
    routes = []
    ports1 = ports
    port = ports1[0]
    port_extended_x = port.get_extended_midpoint(dx)[0]
    port_settings = port.settings.copy()

    port_settings.pop("name")
    port_settings.update(midpoint=(port_extended_x, 0))
    port_settings.update(orientation=(port.angle + 180) % 360)
    ports2 = port_array(n=len(ports1), pitch=pitch, **port_settings)

    for p1, p2 in zip(ports1, ports2):
        route = gf.routing.get_route_sbend(p1, p2)
        routes.append(route)
    return routes


def test_fanout_ports():
    c = gf.components.mmi2x2()
    ports = c.get_ports_dict(orientation=0)
    port_names = list(ports.keys())
    c2 = fanout_component(component=c, port_names=port_names)
    d = direction_ports_from_list_ports(c2.get_ports_list())
    assert len(d["E"]) == 2, len(d["E"]) == 2
    assert len(d["W"]) == 2, len(d["W"]) == 2


if __name__ == "__main__":
    test_fanout_ports()

    # c =gf.components.coupler(gap=1.0)
    # c = gf.components.nxn(west=4)
    # c = gf.components.nxn(west=4, layer=gf.LAYER.SLAB90)
    # c = gf.components.mmi2x2()

    # cc = fanout_component(
    #     component=c, port_names=tuple(c.get_ports_dict(orientation=0).keys())
    # )
    # print(len(cc.ports))
    # cc.show()

    # c = gf.components.nxn(west=4, layer=gf.LAYER.SLAB90)
    # routes = fanout_ports(ports=c.get_ports_list(orientation=180))

    # for route in routes:
    #     c.add(route.references)
    # c.show(show_ports=True)
    # print(cc.ports.keys())
