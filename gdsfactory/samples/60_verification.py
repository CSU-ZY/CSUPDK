import gdsfactory as gf

if __name__ == "__main__":
    c = gf.Component()
    s = c << gf.components.straight(width=1)

    b1 = c << gf.components.bend_euler()
    b1.connect("o1", s["o2"], allow_width_mismatch=True)

    b2 = c << gf.components.bend_euler()
    b2.connect("o1", s["o1"], allow_width_mismatch=True)

    gc = gf.components.grating_coupler_elliptical_te()
    gc1 = c << gc
    gc2 = c << gc

    gc1.connect("o1", b1.ports["o2"])
    gc2.connect("o1", b2.ports["o2"])
    c.show()
