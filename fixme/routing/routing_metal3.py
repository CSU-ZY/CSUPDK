"""
FIXME: electrical connections should ignore port orientation
"""

import gdsfactory as gf


if __name__ == "__main__":

    c = gf.Component("ports_none_orientation")
    # c1 = c << gf.components.pad(port_orientation=0)
    # c2 = c << gf.components.pad(port_orientation=180)

    c1 = c << gf.components.pad(port_orientation=None)
    c2 = c << gf.components.pad(port_orientation=None)
    c2.movex(200)
    c2.movey(100)

    route = gf.routing.get_route_from_waypoints(
        c1.ports["pad"],
        c2.ports["pad"],
        waypoints=[c1.ports["pad"]],
    )
    c.add(route.references)
    c.show(show_ports=True)

    # print(c2.ports['pad'].center)
