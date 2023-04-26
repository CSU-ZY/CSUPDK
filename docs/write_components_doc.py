import inspect
import pathlib

import gdsfactory as gf
from gdsfactory.serialization import clean_value_json


filepath = pathlib.Path(__file__).parent.absolute() / "pcells.rst"

skip = {}

skip_plot = [
    "component_lattice",
    "component_sequence",
    "extend_port",
    "extend_ports_list",
]

skip_settings = {"vias"}


with open(filepath, "w+") as f:
    f.write(
        """

Here are some generic Parametric cells.

You can customize them your fab or use them as an inspiration to build your own.


Parametric cells
=============================
"""
    )

    for name in sorted(gf.pcells.cells.keys()):
        if name in skip or name.startswith("_"):
            continue
        print(name)
        sig = inspect.signature(gf.pcells.cells[name])
        kwargs = ", ".join(
            [
                f"{p}={repr(clean_value_json(sig.parameters[p].default))}"
                for p in sig.parameters
                if isinstance(sig.parameters[p].default, (int, float, str, tuple))
                and p not in skip_settings
            ]
        )
        if name in skip_plot:
            f.write(
                f"""

{name}
----------------------------------------------------

.. autofunction:: gdsfactory.pcells.{name}

"""
            )
        else:
            f.write(
                f"""

{name}
----------------------------------------------------

.. autofunction:: gdsfactory.pcells.{name}

.. plot::
  :include-source:

  import gdsfactory as gf

  c = gf.pcells.{name}({kwargs})
  c.plot_matplotlib()

"""
            )
