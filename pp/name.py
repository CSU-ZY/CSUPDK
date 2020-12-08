""" define names, clean names and values
"""
import hashlib
from typing import Any

import numpy as np
from phidl import Device


def join_first_letters(name: str) -> str:
    """ join the first letter of a name separated with underscores (taper_length -> TL) """
    return "".join([x[0] for x in name.split("_") if x])


component_type_to_name = dict(import_phidl_component="phidl")


def get_component_name(component_type: str, **kwargs) -> str:
    name = component_type
    for k, v in component_type_to_name.items():
        name = name.replace(k, v)
    if kwargs:
        name += "_" + dict2name(**kwargs)
    return name


def dict2hash(**kwargs) -> str:
    ignore_from_name = kwargs.pop("ignore_from_name", [])
    h = hashlib.sha256()
    for key in sorted(kwargs):
        if key not in ignore_from_name:
            value = kwargs[key]
            value = clean_value(value)
            h.update(f"{key}{value}".encode())
    return h.hexdigest()


def dict2name(prefix: str = "", **kwargs) -> str:
    """Return name from a dict."""
    ignore_from_name = kwargs.pop("ignore_from_name", [])
    kv = []

    for key in sorted(kwargs):
        if key not in ignore_from_name:
            value = kwargs[key]
            key = join_first_letters(key)
            value = clean_value(value)
            kv += [f"{key.upper()}{value}"]
    label = prefix + "_".join(kv)
    return clean_name(label)


def assert_first_letters_are_different(**kwargs):
    """ avoids having name colissions of different args with the same first letter """
    first_letters = [join_first_letters(k) for k in kwargs.keys() if k != "layer"]
    assert len(set(first_letters)) == len(
        first_letters
    ), f"Possible Duplicated name because {kwargs.keys()} has repeated first letters {first_letters}"
    if not len(set(first_letters)) == len(first_letters):
        print(
            f"Possible Duplicated name because {kwargs.keys()} has repeated first letters {first_letters}"
        )


def clean_name(name: str) -> str:
    """Ensures that gds cells are composed of [a-zA-Z0-9]

    FIXME: only a few characters are currently replaced.
        This function has been updated only on case-by-case basis
    """
    replace_map = {
        " ": "_",
        "!": "_",
        "#": "_",
        "%": "_",
        "(": "",
        ")": "",
        "*": "_",
        ",": "_",
        "-": "m",
        ".": "p",
        "/": "_",
        ":": "_",
        "=": "",
        "@": "_",
        "[": "",
        "]": "",
    }
    for k, v in list(replace_map.items()):
        name = name.replace(k, v)
    return name


def clean_value(value: Any) -> str:
    """returns more readable value (integer)
    if number is < 1:
        returns number units in nm (integer)

    units are in um by default. Therefore when we multiply by 1e3 we get nm.
    """

    if isinstance(value, int):
        value = str(value)
    elif isinstance(value, (float, np.float64)):
        if 1 > value > 1e-3:
            value = f"{int(value*1e3)}n"
        else:
            value = f"{value:.2f}"
    elif isinstance(value, list):
        value = "_".join(clean_value(v) for v in value)
    elif isinstance(value, tuple):
        value = "_".join(clean_value(v) for v in value)
    elif isinstance(value, dict):
        value = dict2name(**value)
    elif isinstance(value, Device):
        value = clean_name(value.name)
    elif callable(value):
        value = value.__name__
    else:
        value = clean_name(str(value))
    return value


def test_clean_value():
    assert clean_value(0.5) == "500n"
    assert clean_value(5) == "5"


def test_clean_name():
    assert clean_name("wg(:_=_2852") == "wg___2852"


if __name__ == "__main__":
    # test_cell()
    import pp

    # print(clean_value(pp.c.waveguide))
    # c = pp.c.waveguide(polarization="TMeraer")
    # print(c.get_settings()["polarization"])

    c = pp.c.waveguide(length=11)
    print(c)
    # print(c)
    # pp.show(c)

    # print(clean_name("Waveguidenol1_(:_=_2852"))
    # print(clean_value(1.2))
    # print(clean_value(0.2))
    # print(clean_value([1, [2.4324324, 3]]))
    # print(clean_value([1, 2.4324324, 3]))
    # print(clean_value((0.001, 24)))
    # print(clean_value({"a": 1, "b": 2}))
