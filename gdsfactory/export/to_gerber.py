"""Based on Gerber file spec.

https://www.ucamco.com/files/downloads/file_en/456/gerber-layer-format-specification-revision-2022-02_en.pdf.

See Also:
- https://github.com/opiopan/pcb-tools-extension
- https://github.com/jamesbowman/cuflow/blob/master/gerber.py
"""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from gdsfactory import Component


class GerberLayer(BaseModel):
    name: str
    function: list[str]
    polarity: Literal["Positive", "Negative"]


class GerberOptions(BaseModel):
    header: list[str] | None = None
    mode: Literal["mm", "in"] = "mm"
    resolution: float = 1e-6
    int_size: int = 4


# For generating a gerber job json file
class BoardOptions(BaseModel):
    size: tuple[float, float] | None = None
    n_layers: int = 2


resolutions = {1e-3: 3, 1e-4: 4, 1e-5: 5, 1e-6: 6}


def number(n: float) -> str:
    i = int(round(n * 10000))
    return "%07d" % i


def points(pp: list[tuple[float, float]]) -> str:
    out = ""
    d = "D02"
    for x, y in pp:
        out += f"X{number(x)}Y{number(y)}{d}*\n"
        d = "D01"
    return out


def rect(x0: float, y0: float, x1: float, y1: float) -> str:
    return "D10*\n" + points([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


def linestring(pp: list[tuple[float, float]]) -> str:
    return "D10*\n" + points(pp)


def polygon(pp: list[tuple[float, float]]) -> str:
    return "G36*\n" + points(pp) + "G37*\n" + "\n"


def to_gerber(
    component: Component,
    dirpath: Path,
    layermap_to_gerber_layer: dict[tuple[int, int], GerberLayer],
    options: GerberOptions = Field(default_factory=dict),
) -> None:
    """Writes each layer to a different Gerber file.

    Args:
        component: to export.
        dirpath: directory path.
        layermap_to_gerber_layer: map of GDS layer to GerberLayer.
        options: to save.
            header: List[str] | None = None
            mode: Literal["mm", "in"] = "mm"
            resolution: float = 1e-6
            int_size: int = 4
    """
    # Split references into polygons and circles (components will need to be recursively iterated through)
    # for ref in component.references:
    #     if ref.parent_cell.name.startswith("circle"):
    #         radius = ref.parent_cell.settings["radius"]
    #         center = ref.center
    # Each layer and a list of the polygons (as lists of points) on that layer
    layer_to_polygons = component.get_polygons_points()

    for layer_tup, layer in layermap_to_gerber_layer.items():
        filename = (dirpath / layer.name.replace(" ", "_")).with_suffix(".gbr")

        with open(filename, "w+") as f:
            header = options.header or [
                "Gerber file generated by gdsfactory",
                f"Component: {component.name}",
            ]

            # Write file spec info
            f.write("%TF.FileFunction," + ",".join(layer.function) + "*%\n")
            f.write(f"%TF.FilePolarity,{layer.polarity}*%\n")

            digits = resolutions[options.resolution]
            f.write(f"%FSLA{options.int_size}{digits}Y{options.int_size}{digits}X*%\n")

            # Write header comments
            f.writelines([f"G04 {line}*\n" for line in header])

            # Setup units/mode
            units = options.mode.upper()
            f.write(f"%MO{units}*%\n")
            f.write("%LPD*%")

            f.write("G01*\n")

            # Aperture definition
            f.write("%ADD10C,0.050000*%\n")

            # Only supports polygons for now
            if layer_tup in layer_to_polygons.keys():
                for poly in layer_to_polygons[layer_tup.layer]:
                    f.write(polygon(poly))

            # File end
            f.write("M02*\n")


if __name__ == "__main__":
    import gdsfactory as gf
    from gdsfactory.config import PATH
    from gdsfactory.technology import (
        LayerMap,
        LayerView,
        LayerViews,
    )
    from gdsfactory.typings import Layer

    class LayerMapPCB(LayerMap):
        F_Cu: Layer = (1, 0)
        In1_Cu: Layer = (2, 0)
        In2_Cu: Layer = (3, 0)
        B_Cu: Layer = (4, 0)
        F_Silkscreen: Layer = (11, 0)
        F_Mask: Layer = (21, 0)
        B_Mask: Layer = (22, 0)
        Edge_Cuts: Layer = (31, 0)

        DEVREC: Layer = (68, 0)
        PORT: Layer = (1, 10)
        PORTE: Layer = (1, 11)

    LAYER = LayerMapPCB

    class PCBViews(LayerViews):
        F_Cu: LayerView = LayerView(
            name="F_Cu",
            layer=tuple(LAYER.F_Cu),
            color="red",
        )
        In1_Cu: LayerView = LayerView(
            name="In1_Cu",
            layer=tuple(LAYER.In1_Cu),
            color="limegreen",
        )
        In2_Cu: LayerView = LayerView(
            name="In2_Cu",
            layer=tuple(LAYER.In2_Cu),
            color="goldenrod",
        )
        B_Cu: LayerView = LayerView(
            name="B_Cu",
            layer=tuple(LAYER.B_Cu),
            color="blue",
        )
        F_Silkscreen: LayerView = LayerView(
            name="F_Silkscreen",
            layer=tuple(LAYER.F_Silkscreen),
            color="khaki",
        )
        F_Mask: LayerView = LayerView(
            name="F_Mask",
            layer=tuple(LAYER.F_Mask),
            color="violet",
        )
        B_Mask: LayerView = LayerView(
            name="B_Mask",
            layer=LAYER.B_Mask,
            color="aqua",
        )
        Edge_Cuts: LayerView = LayerView(
            name="Edge_Cuts",
            layer=LAYER.Edge_Cuts,
            color="gold",
        )

    LAYER_VIEWS = PCBViews()

    # def get_pcb_layer_stack(
    #     copper_thickness: float = 0.035,
    #     core_thickness: float = 1,
    # ):
    #     return LayerStack(
    #         layers=dict(
    #             top_cu=LayerLevel(
    #                 layer=LAYER.F_Cu,
    #                 thickness=copper_thickness,
    #                 zmin=0.0,
    #                 material="cu",
    #             ),
    #             inner1_cu=LayerLevel(
    #                 layer=LAYER.In1_Cu,
    #                 thickness=copper_thickness,
    #                 zmin=0.0,
    #                 material="cu",
    #             ),
    #             inner_core=LayerLevel(
    #                 layer=LAYER.Edge_Cuts,
    #                 thickness=core_thickness,
    #                 zmin=-core_thickness / 2,
    #                 material="fr4",
    #             ),
    #             inner2_cu=LayerLevel(
    #                 layer=LAYER.In2_Cu,
    #                 thickness=copper_thickness,
    #                 zmin=0.0,
    #                 material="cu",
    #             ),
    #             bottom_cu=LayerLevel(
    #                 layer=LAYER.B_Cu,
    #                 thickness=copper_thickness,
    #                 zmin=0.0,
    #                 material="cu",
    #             ),
    #         )
    #     )
    #
    # LAYER_STACK = get_pcb_layer_stack()

    layermap_to_gerber = {
        LAYER.F_Cu: GerberLayer(
            name="F_Cu", function=["Copper", "L1", "Top"], polarity="Positive"
        ),
        LAYER.B_Cu: GerberLayer(
            name="B_Cu", function=["Copper", "L2", "Bot"], polarity="Positive"
        ),
        LAYER.F_Silkscreen: GerberLayer(
            name="F_Silkscreen", function=["Legend", "Top"], polarity="Positive"
        ),
        LAYER.F_Mask: GerberLayer(
            name="F_Mask", function=["SolderMask", "Top"], polarity="Negative"
        ),
        LAYER.B_Mask: GerberLayer(
            name="B_Mask", function=["SolderMask", "Bot"], polarity="Negative"
        ),
        LAYER.Edge_Cuts: GerberLayer(
            name="Edge_Cuts", function=["Profile"], polarity="Positive"
        ),
    }

    # from gdsfactory.install import install_klayout_technology
    # from gdsfactory.technology.klayout_tech import KLayoutTechnology
    # tech_dir = (pathlib.Path(__file__) / "..").resolve() / "klayout"
    # pcb_tech = KLayoutTechnology(name='PCB', layer_views=PCBViews())
    # pcb_tech.technology.dbu = 1e-3
    # pcb_tech.export_technology_files(tech_dir=str(tech_dir))
    #
    # install_klayout_technology(tech_dir=tech_dir, tech_name="PCB")

    c = gf.components.text(layer=LAYER.F_Cu)
    # c = LAYER_VIEWS.preview_layerset()

    gerber_path = PATH.repo / "extra" / "gerber"
    gerber_path.mkdir(exist_ok=True, parents=True)

    # This requires that the PCB technology (commented-out code above) is installed
    c.show()

    to_gerber(
        c,
        dirpath=gerber_path,
        layermap_to_gerber_layer=layermap_to_gerber,
        options=GerberOptions(resolution=1e-6),
    )
