"""You can define a path as list of points.

To create a component you need to extrude the path with a cross-section.
"""
from __future__ import annotations

import sys
from collections.abc import Callable, Iterable
from functools import partial
from inspect import getmembers
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from gdsfactory.component import Component

nm = 1e-3

Layer = tuple[int, int]
Layers = tuple[Layer, ...]
WidthTypes = Literal["sine", "linear", "parabolic"]

LayerSpec = Layer | str
LayerSpecs = list[LayerSpec] | tuple[LayerSpec, ...]

Floats = tuple[float, ...]
port_names_electrical = ("e1", "e2")
port_types_electrical = ("electrical", "electrical")
cladding_layers_optical = None
cladding_offsets_optical = None
cladding_simplify_optical = None


class Section(BaseModel):
    """CrossSection to extrude a path with a waveguide.

    Parameters:
        width: of the section (um) or parameterized function from 0 to 1. \
                the width at t==0 is the width at the beginning of the Path. \
                the width at t==1 is the width at the end.
        offset: center offset (um) or function parameterized function from 0 to 1. \
                the offset at t==0 is the offset at the beginning of the Path. \
                the offset at t==1 is the offset at the end.
        insets: distance (um) in x to inset section relative to end of the Path \
                (i.e. (start inset, stop_inset)).
        layer: layer spec. If None does not draw the main section.
        port_names: Optional port names.
        port_types: optical, electrical, ...
        name: Optional Section name.
        hidden: hide layer.
        simplify: Optional Tolerance value for the simplification algorithm. \
                All points that can be removed without changing the resulting. \
                polygon by more than the value listed here will be removed.


    .. code::

          0   offset
          |<-------------->|
          |              _____
          |             |     |
          |             |layer|
          |             |_____|
          |              <---->
                         width
    """

    width: float
    offset: float = 0
    insets: tuple | None = None
    layer: LayerSpec | LayerSpecs | None = None
    port_names: tuple[str | None, str | None] = (None, None)
    port_types: tuple[str, str] = ("optical", "optical")
    name: str | None = None
    hidden: bool = False
    simplify: float | None = None

    model_config = ConfigDict(extra="forbid", frozen=True)


class ComponentAlongPath(BaseModel):
    """A ComponentAlongPath object to place along an extruded path.

    Parameters:
        component: to repeat along the path. The unrotated version should be oriented \
                for placement on a horizontal line.
        spacing: distance between component placements
        padding: minimum distance from the path start to the first component.
        y_offset: offset in y direction (um).
    """

    component: object
    spacing: float
    padding: float = 0.0
    offset: float = 0.0


Sections = tuple[Section, ...]


class CrossSection(BaseModel):
    """Waveguide information to extrude a path.

    Parameters:
        sections: tuple of Sections(width, offset, layer, ports).
        components_along_path: list[ComponentAlongPath] = Field(default_factory=list): list of ComponentAlongPaths(component, spacing, padding, offset).
        radius: route bend radius (um).
        info: dictionary with extra information.
        add_pins_function_name: name of the function to add pins to the component.
        min_length: defaults to 1nm = 10e-3um for routing.
        start_straight_length: straight length at the beginning of the route.
        end_straight_length: end length at the beginning of the route.
        width_wide: wide waveguides width (um) for low loss routing.
        auto_widen: taper to wide waveguides for low loss routing.
        auto_widen_minimum_length: minimum straight length for auto_widen.
        taper_length: taper_length for auto_widen.
        gap: minimum gap between waveguides.
    """

    sections: tuple[Section, ...] = Field(default_factory=tuple)
    components_along_path: list[ComponentAlongPath] = Field(default_factory=list)
    radius: float | None = None
    bbox_layers: LayerSpecs | None = None
    bbox_offsets: Floats | None = None

    info: dict[str, Any] = Field(default_factory=dict)
    add_pins_function_name: str | None = None

    min_length: float = 10e-3
    start_straight_length: float = 10e-3
    end_straight_length: float = 10e-3
    width_wide: float | None = None
    auto_widen: bool = False
    auto_widen_minimum_length: float = 200.0
    taper_length: float = 10.0
    gap: float = 3.0

    model_config = ConfigDict(extra="forbid", frozen=True)

    @classmethod
    def validate_x(cls, v):
        return v

    @property
    def width(self):
        return self.sections[0].width

    @property
    def layer(self):
        return self.sections[0].layer

    def copy(self, width: float | None = None):
        """ "Returns a copy of the cross_section with a new width or the same by default."""
        if width is not None:
            sections = [s.model_copy() for s in self.sections]
            sections[0] = sections[0].model_copy(update={"width": width})
            return self.model_copy(update={"sections": sections})
        return self.model_copy()

    def add_pins(self, component: Component) -> Component:
        if self.add_pins_function_name is None:
            return component
        from gdsfactory import add_pins

        if not hasattr(add_pins, self.add_pins_function_name):
            raise ValueError(
                f"add_pins_function_name={self.add_pins_function_name} not found in add_pins"
            )
        return getattr(add_pins, self.add_pins_function_name)(component=component)

    def add_bbox(
        self,
        component,
        top: float | None = None,
        bottom: float | None = None,
        right: float | None = None,
        left: float | None = None,
    ) -> Component:
        """Add bounding box layers to a component.

        Args:
            component: to add layers.
            top: top padding.
            bottom: bottom padding.
            right: right padding.
            left: left padding.
        """
        from gdsfactory.add_padding import get_padding_points

        c = component
        if self.bbox_layers and self.bbox_offsets:
            padding = []
            for offset in self.bbox_offsets:
                points = get_padding_points(
                    component=c,
                    default=0,
                    top=top or offset,
                    bottom=bottom or offset,
                    left=left or offset,
                    right=right or offset,
                )
                padding.append(points)

            for layer, points in zip(self.bbox_layers, padding):
                c.add_polygon(points, layer=layer)
        return c

    def get_xmin_xmax(self):
        """Returns the min and max extent of the cross_section across all sections."""
        main_width = self.width
        main_offset = self.offset
        xmin = main_offset - main_width / 2
        xmax = main_offset + main_width / 2
        for section in self.sections:
            width = section.width
            offset = section.offset
            xmin = min(xmin, offset - width / 2)
            xmax = max(xmax, offset + width / 2)

        return xmin, xmax


CrossSectionSpec = CrossSection | str | dict[str, Any]


class Transition(BaseModel):
    """Waveguide information to extrude a path between two CrossSection.

    cladding_layers follow path shape

    Parameters:
        cross_section1: input cross_section.
        cross_section2: output cross_section.
        width_type: sine or linear. Sets the type of width transition used if widths are different \
                between the two input CrossSections.
    """

    cross_section1: CrossSectionSpec
    cross_section2: CrossSectionSpec
    width_type: WidthTypes = "sine"


def cross_section(
    width: float = 0.5,
    offset: float = 0,
    layer: LayerSpec | None = "WG",
    sections: tuple[Section, ...] | None = None,
    port_names: tuple[str, str] = ("o1", "o2"),
    port_types: tuple[str, str] = ("optical", "optical"),
    bbox_layers: LayerSpecs | None = None,
    bbox_offsets: Floats | None = None,
    cladding_layers: LayerSpecs | None = None,
    cladding_offsets: Floats | None = None,
    cladding_simplify: Floats | None = None,
    radius: float | None = 10.0,
    add_pins_function_name: str | None = None,
    **kwargs,
) -> CrossSection:
    """Return CrossSection.

    Args:
        width: main Section width (um).
        offset: main Section center offset (um).
        layer: main section layer.
        sections: list of Sections(width, offset, layer, ports).
        port_names: for input and output ('o1', 'o2').
        port_types: for input and output: electrical, optical, vertical_te ...
        bbox_layers: list of layers bounding boxes to extrude.
        bbox_offsets: list of offset from bounding box edge.
        cladding_layers: list of layers to extrude.
        cladding_offsets: list of offset from main Section edge.
        cladding_simplify: Optional Tolerance value for the simplification algorithm. \
                All points that can be removed without changing the resulting. \
                polygon by more than the value listed here will be removed.
        radius: routing bend radius (um).
        add_pins_function_name: name of the function to add pins to the component.

    Keyword Args:
        info: dictionary with extra information.
        add_pins_function_name: name of the function to add pins to the component.
        min_length: defaults to 1nm = 10e-3um for routing.
        start_straight_length: straight length at the beginning of the route.
        end_straight_length: end length at the beginning of the route.
        width_wide: wide waveguides width (um) for low loss routing.
        auto_widen: taper to wide waveguides for low loss routing.
        auto_widen_minimum_length: minimum straight length for auto_widen.
        taper_length: taper_length for auto_widen.
        gap: minimum gap between waveguides.


    .. plot::
        :include-source:

        import gdsfactory as gf

        xs = gf.cross_section.cross_section(width=0.5, offset=0, layer='WG')
        p = gf.path.arc(radius=10, angle=45)
        c = p.extrude(xs)
        c.plot()
    """
    sections = list(sections or [])
    cladding_layers = cladding_layers or ()
    cladding_offsets = cladding_offsets or ()
    cladding_simplify = cladding_simplify or ()

    s = [
        Section(
            width=width,
            offset=offset,
            layer=layer,
            port_names=port_names,
            port_types=port_types,
        )
    ] + sections
    s += [
        Section(width=width + 2 * offset, layer=layer, simplify=simplify)
        for layer, offset, simplify in zip(
            cladding_layers, cladding_offsets, cladding_simplify
        )
    ]
    return CrossSection(
        sections=tuple(s),
        radius=radius,
        bbox_layers=bbox_layers,
        bbox_offsets=bbox_offsets,
        add_pins_function_name=add_pins_function_name,
        **kwargs,
    )


radius_nitride = 20
radius_rib = 20

strip = partial(cross_section, add_pins_function_name="add_pins_inside1nm")
rib = partial(
    strip,
    sections=(Section(width=6, layer="SLAB90", name="slab", simplify=50 * nm),),
)
rib2 = partial(
    strip,
    cladding_layers=("SLAB90",),
    cladding_offsets=(3,),
    cladding_simplify=(50 * nm,),
)
nitride = partial(strip, layer="WGN", width=1.0)
strip_rib_tip = partial(
    strip,
    sections=(Section(width=0.2, layer="SLAB90", name="slab"),),
)

# L shaped waveguide (slab only on one side of the core)
l_wg = partial(
    strip,
    sections=(Section(width=4, layer="SLAB90", name="slab", offset=-2 - 0.25),),
)


def slot(
    width: float = 0.5,
    layer: LayerSpec = "WG",
    slot_width: float = 0.04,
    sections: tuple[Section, ...] | None = None,
) -> CrossSection:
    """Return CrossSection Slot (with an etched region in the center).

    Args:
        width: main Section width (um) or function parameterized from 0 to 1. \
                the width at t==0 is the width at the beginning of the Path. \
                the width at t==1 is the width at the end.
        layer: main section layer.
        slot_width: in um.
        sections: list of Sections(width, offset, layer, ports).

    .. plot::
        :include-source:

        import gdsfactory as gf

        xs = gf.cross_section.slot(width=0.5, slot_width=0.05, layer='WG')
        p = gf.path.arc(radius=10, angle=45)
        c = p.extrude(xs)
        c.plot()
    """
    rail_width = (width - slot_width) / 2
    rail_offset = (rail_width + slot_width) / 2

    sections = sections or ()
    sections += (
        Section(width=rail_width, offset=rail_offset, layer=layer, name="left_rail"),
        Section(width=rail_width, offset=-rail_offset, layer=layer, name="right rail"),
    )

    return strip(
        width=width,
        layer=None,
        sections=sections,
    )


metal1 = partial(
    cross_section,
    layer="M1",
    width=10.0,
    port_names=port_names_electrical,
    port_types=port_types_electrical,
)
metal2 = partial(
    metal1,
    layer="M2",
)
metal3 = partial(
    metal1,
    layer="M3",
)
heater_metal = partial(
    metal1,
    width=2.5,
    layer="HEATER",
)

metal_routing = metal3
npp = partial(metal1, layer="NPP", width=0.5)

metal_slotted = partial(
    cross_section,
    width=10,
    offset=0,
    layer="M3",
    sections=(
        Section(width=10, layer="M3", offset=11),
        Section(width=10, layer="M3", offset=-11),
    ),
)


def pin(
    width: float = 0.5,
    layer: LayerSpec = "WG",
    layer_slab: LayerSpec = "SLAB90",
    via_stack_width: float = 9.0,
    via_stack_gap: float = 0.55,
    slab_gap: float = -0.2,
    layer_via: LayerSpec | None = None,
    via_width: float = 1,
    via_offsets: tuple[float, ...] | None = None,
    sections: tuple[Section, ...] | None = None,
) -> CrossSection:
    """Rib PIN doped cross_section.

    Args:
        width: ridge width.
        layer: ridge layer.
        layer_slab: slab layer.
        via_stack_width: in um.
        via_stack_gap: offset from via_stack to ridge edge.
        slab_gap: extra slab gap (negative: via_stack goes beyond slab).
        layer_via: for via.
        via_width: in um.
        via_offsets: in um.
        kwargs: other cross_section settings.

    https://doi.org/10.1364/OE.26.029983

    .. code::

                                      layer
                                |<----width--->|
                                 _______________ via_stack_gap           slab_gap
                                |              |<----------->|             <-->
        ___ ____________________|              |__________________________|___
       |   |         |                                       |            |   |
       |   |    P++  |         undoped silicon               |     N++    |   |
       |___|_________|_______________________________________|____________|___|
                                                              <----------->
                                                              via_stack_width
       <---------------------------------------------------------------------->
                                   slab_width

    .. plot::
        :include-source:

        import gdsfactory as gf

        xs = gf.cross_section.pin(width=0.5, via_stack_gap=1, via_stack_width=1)
        p = gf.path.arc(radius=10, angle=45)
        c = p.extrude(xs)
        c.plot()
    """
    slab_width = width + 2 * via_stack_gap + 2 * via_stack_width - 2 * slab_gap
    width / 2 + via_stack_gap + via_stack_width / 2

    sections = sections or ()
    sections += (Section(width=slab_width, layer=layer_slab, name="slab"),)
    if layer_via and via_width and via_offsets:
        sections += (
            Section(
                layer=layer_via,
                width=via_width,
                offset=offset,
            )
            for offset in via_offsets
        )

    return strip(
        width=width,
        layer=layer,
        sections=sections,
    )


def pn(
    width: float = 0.5,
    layer: LayerSpec = "WG",
    layer_slab: LayerSpec = "SLAB90",
    gap_low_doping: float = 0.0,
    gap_medium_doping: float | None = 0.5,
    gap_high_doping: float | None = 1.0,
    offset_low_doping: float | None = 0.0,
    width_doping: float = 8.0,
    width_slab: float = 7.0,
    layer_p: LayerSpec | None = "P",
    layer_pp: LayerSpec | None = "PP",
    layer_ppp: LayerSpec | None = "PPP",
    layer_n: LayerSpec | None = "N",
    layer_np: LayerSpec | None = "NP",
    layer_npp: LayerSpec | None = "NPP",
    layer_via: LayerSpec | None = None,
    width_via: float = 1.0,
    layer_metal: LayerSpec | None = None,
    width_metal: float = 1.0,
    port_names: tuple[str, str] = ("o1", "o2"),
    sections: tuple[Section, ...] | None = None,
    cladding_layers: LayerSpecs | None = None,
    cladding_offsets: Floats | None = None,
    cladding_simplify: Floats | None = None,
) -> CrossSection:
    """Rib PN doped cross_section.

    Args:
        width: width of the ridge in um.
        layer: ridge layer.
        layer_slab: slab layer.
        gap_low_doping: from waveguide center to low doping. Only used for PIN.
        gap_medium_doping: from waveguide center to medium doping. None removes it.
        gap_high_doping: from center to high doping. None removes it.
        offset_low_doping: from center to junction center.
        width_doping: in um.
        width_slab: in um.
        layer_p: p doping layer.
        layer_pp: p+ doping layer.
        layer_ppp: p++ doping layer.
        layer_n: n doping layer.
        layer_np: n+ doping layer.
        layer_npp: n++ doping layer.
        layer_via: via layer.
        width_via: via width in um.
        layer_metal: metal layer.
        width_metal: metal width in um.
        port_names: input and output port names.
        sections: optional list of sections.
        cladding_layers: optional list of cladding layers.
        cladding_offsets: optional list of cladding offsets.
        cladding_simplify: Optional Tolerance value for the simplification algorithm. \
                All points that can be removed without changing the resulting\
                polygon by more than the value listed here will be removed.

    .. code::

                              offset_low_doping
                                <------>
                               |       |
                              wg     junction
                            center   center
                               |       |
                 ______________|_______|______
                 |             |       |     |
        _________|             |       |     |_________________|
              P                |       |               N       |
          width_p              |       |            width_n    |
        <----------------------------->|<--------------------->|
                               |               |       N+      |
                               |               |    width_n    |
                               |               |<------------->|
                               |<------------->|
                               gap_medium_doping

    .. plot::
        :include-source:

        import gdsfactory as gf

        xs = gf.cross_section.pn(width=0.5, gap_low_doping=0, width_doping=2.)
        p = gf.path.arc(radius=10, angle=45)
        c = p.extrude(xs)
        c.plot()
    """
    slab = Section(width=width_slab, offset=0, layer=layer_slab)

    sections = list(sections) or []
    sections += [slab]
    base_offset_low_doping = width_doping / 2 + gap_low_doping / 4
    width_low_doping = width_doping - gap_low_doping / 2

    if layer_n:
        n = Section(
            width=width_low_doping + offset_low_doping,
            offset=+base_offset_low_doping - offset_low_doping / 2,
            layer=layer_n,
        )
        sections.append(n)
    if layer_p:
        p = Section(
            width=width_low_doping - offset_low_doping,
            offset=-base_offset_low_doping - offset_low_doping / 2,
            layer=layer_p,
        )
        sections.append(p)

    if gap_medium_doping is not None:
        width_medium_doping = width_doping - gap_medium_doping
        offset_medium_doping = width_medium_doping / 2 + gap_medium_doping

        if layer_np is not None:
            np = Section(
                width=width_medium_doping,
                offset=+offset_medium_doping,
                layer=layer_np,
            )
            sections.append(np)
        if layer_pp is not None:
            pp = Section(
                width=width_medium_doping,
                offset=-offset_medium_doping,
                layer=layer_pp,
            )
            sections.append(pp)

    if gap_high_doping is not None:
        width_high_doping = width_doping - gap_high_doping
        offset_high_doping = width_high_doping / 2 + gap_high_doping
        if layer_npp is not None:
            npp = Section(
                width=width_high_doping, offset=+offset_high_doping, layer=layer_npp
            )
            sections.append(npp)
        if layer_ppp is not None:
            ppp = Section(
                width=width_high_doping, offset=-offset_high_doping, layer=layer_ppp
            )
            sections.append(ppp)

    if layer_via is not None:
        offset = width_high_doping + gap_high_doping - width_via / 2
        via_top = Section(width=width_via, offset=+offset, layer=layer_via)
        via_bot = Section(width=width_via, offset=-offset, layer=layer_via)
        sections.append(via_top)
        sections.append(via_bot)

    if layer_metal is not None:
        offset = width_high_doping + gap_high_doping - width_metal / 2
        port_types = ("electrical", "electrical")
        metal_top = Section(
            width=width_via,
            offset=+offset,
            layer=layer_metal,
            port_types=port_types,
            port_names=("e1_top", "e2_top"),
        )
        metal_bot = Section(
            width=width_via,
            offset=-offset,
            layer=layer_metal,
            port_types=port_types,
            port_names=("e1_bot", "e2_bot"),
        )
        sections.append(metal_top)
        sections.append(metal_bot)

    return cross_section(
        width=width,
        offset=0,
        layer=layer,
        port_names=port_names,
        sections=tuple(sections),
        cladding_offsets=cladding_offsets,
        cladding_layers=cladding_layers,
        cladding_simplify=cladding_simplify,
    )


def pn_with_trenches(
    width: float = 0.5,
    layer: LayerSpec | None = None,
    layer_trench: LayerSpec = "DEEP_ETCH",
    gap_low_doping: float = 0.0,
    gap_medium_doping: float | None = 0.5,
    gap_high_doping: float | None = 1.0,
    offset_low_doping: float | None = 0.0,
    width_doping: float = 8.0,
    width_slab: float = 7.0,
    width_trench: float = 2.0,
    layer_p: LayerSpec | None = "P",
    layer_pp: LayerSpec | None = "PP",
    layer_ppp: LayerSpec | None = "PPP",
    layer_n: LayerSpec | None = "N",
    layer_np: LayerSpec | None = "NP",
    layer_npp: LayerSpec | None = "NPP",
    layer_via: LayerSpec | None = None,
    width_via: float = 1.0,
    layer_metal: LayerSpec | None = None,
    width_metal: float = 1.0,
    port_names: tuple[str, str] = ("o1", "o2"),
    cladding_layers: Layers | None = cladding_layers_optical,
    cladding_offsets: Floats | None = cladding_offsets_optical,
    cladding_simplify: Floats | None = cladding_simplify_optical,
    wg_marking_layer: LayerSpec | None = None,
    sections: Sections | None = None,
    **kwargs,
) -> CrossSection:
    """Rib PN doped cross_section.

    Args:
        width: width of the ridge in um.
        layer: ridge layer. None adds only ridge.
        layer_trench: layer to etch trenches.
        gap_low_doping: from waveguide center to low doping. Only used for PIN.
        gap_medium_doping: from waveguide center to medium doping. None removes it.
        gap_high_doping: from center to high doping. None removes it.
        offset_low_doping: from center to junction center.
        width_doping: in um.
        width_slab: in um.
        width_trench: in um.
        layer_p: p doping layer.
        layer_pp: p+ doping layer.
        layer_ppp: p++ doping layer.
        layer_n: n doping layer.
        layer_np: n+ doping layer.
        layer_npp: n++ doping layer.
        layer_via: via layer.
        width_via: via width in um.
        layer_metal: metal layer.
        width_metal: metal width in um.
        port_names: input and output port names.
        cladding_layers: optional list of cladding layers.
        cladding_offsets: optional list of cladding offsets.
        cladding_simplify: Optional Tolerance value for the simplification algorithm.\
                All points that can be removed without changing the resulting. \
                polygon by more than the value listed here will be removed.
        kwargs: cross_section settings.

    .. code::

                                   offset_low_doping
                                     <------>
                                    |       |
                                   wg     junction
                                 center   center
                                    |       |
        _____         ______________|_______ ______         ________
             |        |             |       |     |         |       |
             |________|             |             |_________|       |
                   P                |       |               N       |
               width_p              |                    width_n    |
          <-------------------------------->|<--------------------->|
             <------->              |               |       N+      |
            width_trench            |               |    width_n    |
                                    |               |<------------->|
                                    |<------------->|
                                    gap_medium_doping
       <------------------------------------------------------------>
                                width_slab

    .. plot::
        :include-source:

        import gdsfactory as gf

        xs = gf.cross_section.pn_with_trenches(width=0.5, gap_low_doping=0, width_doping=2.)
        p = gf.path.arc(radius=10, angle=45)
        c = p.extrude(xs)
        c.plot()
    """
    trench_offset = width / 2 + width_trench / 2
    sections = list(sections or [])
    sections += [Section(width=width_slab, layer=layer)]
    sections += [
        Section(width=width_trench, offset=offset, layer=layer_trench)
        for offset in [+trench_offset, -trench_offset]
    ]

    if wg_marking_layer is not None:
        sections += [Section(width=width, offset=0, layer=wg_marking_layer)]

    base_offset_low_doping = width_doping / 2 + gap_low_doping / 4
    width_low_doping = width_doping - gap_low_doping / 2

    if layer_n:
        n = Section(
            width=width_low_doping + offset_low_doping,
            offset=+base_offset_low_doping - offset_low_doping / 2,
            layer=layer_n,
        )
        sections.append(n)
    if layer_p:
        p = Section(
            width=width_low_doping - offset_low_doping,
            offset=-base_offset_low_doping - offset_low_doping / 2,
            layer=layer_p,
        )
        sections.append(p)

    if gap_medium_doping is not None:
        width_medium_doping = width_doping - gap_medium_doping
        offset_medium_doping = width_medium_doping / 2 + gap_medium_doping

        if layer_np:
            np = Section(
                width=width_medium_doping,
                offset=+offset_medium_doping,
                layer=layer_np,
            )
            sections.append(np)
        if layer_pp:
            pp = Section(
                width=width_medium_doping,
                offset=-offset_medium_doping,
                layer=layer_pp,
            )
            sections.append(pp)

    if gap_high_doping is not None:
        width_high_doping = width_doping - gap_high_doping
        offset_high_doping = width_high_doping / 2 + gap_high_doping
        if layer_npp:
            npp = Section(
                width=width_high_doping, offset=+offset_high_doping, layer=layer_npp
            )
            sections.append(npp)
        if layer_ppp:
            ppp = Section(
                width=width_high_doping, offset=-offset_high_doping, layer=layer_ppp
            )
            sections.append(ppp)

    if layer_via is not None:
        offset = width_high_doping + gap_high_doping - width_via / 2
        via_top = Section(width=width_via, offset=+offset, layer=layer_via)
        via_bot = Section(width=width_via, offset=-offset, layer=layer_via)
        sections.append(via_top)
        sections.append(via_bot)

    if layer_metal is not None:
        offset = width_high_doping + gap_high_doping - width_metal / 2
        port_types = ("electrical", "electrical")
        metal_top = Section(
            width=width_via,
            offset=+offset,
            layer=layer_metal,
            port_types=port_types,
            port_names=("e1_top", "e2_top"),
        )
        metal_bot = Section(
            width=width_via,
            offset=-offset,
            layer=layer_metal,
            port_types=port_types,
            port_names=("e1_bot", "e2_bot"),
        )
        sections.append(metal_top)
        sections.append(metal_bot)

    return CrossSection(
        width=width,
        offset=0,
        layer=layer,
        port_names=port_names,
        sections=tuple(sections),
        cladding_offsets=cladding_offsets,
        cladding_simplify=cladding_simplify,
        cladding_layers=cladding_layers,
    )


def pn_with_trenches_asymmetric(
    width: float = 0.5,
    layer: LayerSpec | None = None,
    layer_trench: LayerSpec = "DEEP_ETCH",
    gap_low_doping: float | tuple[float, float] = (0.0, 0.0),
    gap_medium_doping: float | tuple[float, float] | None = (0.5, 0.2),
    gap_high_doping: float | tuple[float, float] | None = (1.0, 0.8),
    width_doping: float = 8.0,
    width_slab: float = 7.0,
    width_trench: float = 2.0,
    layer_p: LayerSpec | None = "P",
    layer_pp: LayerSpec | None = "PP",
    layer_ppp: LayerSpec | None = "PPP",
    layer_n: LayerSpec | None = "N",
    layer_np: LayerSpec | None = "NP",
    layer_npp: LayerSpec | None = "NPP",
    layer_via: LayerSpec | None = None,
    width_via: float = 1.0,
    layer_metal: LayerSpec | None = None,
    width_metal: float = 1.0,
    port_names: tuple[str, str] = ("o1", "o2"),
    cladding_layers: Layers | None = cladding_layers_optical,
    cladding_offsets: Floats | None = cladding_offsets_optical,
    wg_marking_layer: LayerSpec | None = None,
    **kwargs,
) -> CrossSection:
    """Rib PN doped cross_section with asymmetric dimensions left and right.

    Args:
        width: width of the ridge in um.
        layer: ridge layer. None adds only ridge.
        layer_trench: layer to etch trenches.
        gap_low_doping: from waveguide center to low doping. Only used for PIN. \
                If a list, it considers the first element is [p_side, n_side]. If a number, \
                it assumes the same for both sides.
        gap_medium_doping: from waveguide center to medium doping. None removes it. \
                If a list, it considers the first element is [p_side, n_side]. \
                If a number, it assumes the same for both sides.
        gap_high_doping: from center to high doping. None removes it. \
                If a list, it considers the first element is [p_side, n_side].\
                If a number, it assumes the same for both sides.
        width_doping: in um.
        width_slab: in um.
        width_trench: in um.
        layer_p: p doping layer.
        layer_pp: p+ doping layer.
        layer_ppp: p++ doping layer.
        layer_n: n doping layer.
        layer_np: n+ doping layer.
        layer_npp: n++ doping layer.
        layer_via: via layer.
        width_via: via width in um.
        layer_metal: metal layer.
        width_metal: metal width in um.
        port_names: input and output port names.
        cladding_layers: optional list of cladding layers.
        cladding_offsets: optional list of cladding offsets.
        kwargs: cross_section settings.

    .. code::

                                   gap_low_doping[1]
                                     <------>
                                    |       |
                                   wg     junction
                                 center   center
                                    |       |
        _____         ______________|_______ ______         ________
             |        |             |       |     |         |       |
             |________|             |             |_________|       |
                   P                |       |               N       |
               width_p              |                    width_n    |
          <-------------------------------->|<--------------------->|
             <------->              |               |       N+      |
            width_trench            |               |    width_n    |
                                    |               |<------------->|
                                    |<------------->|
                                    gap_medium_doping[1]
       <------------------------------------------------------------>
                                width_slab

    .. plot::
        :include-source:

        import gdsfactory as gf

        xs = gf.cross_section.pn_with_trenches_assymmetric(width=0.5, gap_low_doping=0, width_doping=2.)
        p = gf.path.arc(radius=10, angle=45)
        c = p.extrude(xs)
        c.plot()
    """

    # Trenches
    trench_offset = width / 2 + width_trench / 2
    sections = kwargs.pop("sections", [])
    sections += [Section(width=width_slab, layer=layer)]
    sections += [
        Section(width=width_trench, offset=offset, layer=layer_trench)
        for offset in [+trench_offset, -trench_offset]
    ]

    if wg_marking_layer is not None:
        sections += [Section(width=width, offset=0, layer=wg_marking_layer)]

    # Low doping
    if not isinstance(gap_low_doping, list | tuple):
        gap_low_doping = [gap_low_doping] * 2

    if layer_n:
        width_low_doping_n = width_doping - gap_low_doping[1]
        n = Section(
            width=width_low_doping_n,
            offset=width_low_doping_n / 2 + gap_low_doping[1],
            layer=layer_n,
        )
        sections.append(n)
    if layer_p:
        width_low_doping_p = width_doping - gap_low_doping[0]
        p = Section(
            width=width_low_doping_p,
            offset=-(width_low_doping_p / 2 + gap_low_doping[0]),
            layer=layer_p,
        )
        sections.append(p)

    if gap_medium_doping is not None:
        if not isinstance(gap_medium_doping, list | tuple):
            gap_medium_doping = [gap_medium_doping] * 2

        if layer_np:
            width_np = width_doping - gap_medium_doping[1]
            np = Section(
                width=width_np,
                offset=width_np / 2 + gap_medium_doping[1],
                layer=layer_np,
            )
            sections.append(np)
        if layer_pp:
            width_pp = width_doping - gap_medium_doping[0]
            pp = Section(
                width=width_pp,
                offset=-(width_pp / 2 + gap_medium_doping[0]),
                layer=layer_pp,
            )
            sections.append(pp)

    if gap_high_doping is not None:
        if not isinstance(gap_high_doping, list | tuple):
            gap_high_doping = [gap_high_doping] * 2

        if layer_npp:
            width_npp = width_doping - gap_high_doping[1]
            npp = Section(
                width=width_npp,
                offset=width_npp / 2 + gap_high_doping[1],
                layer=layer_npp,
            )
            sections.append(npp)
        if layer_ppp:
            width_ppp = width_doping - gap_high_doping[0]
            ppp = Section(
                width=width_ppp,
                offset=-(width_ppp / 2 + gap_high_doping[0]),
                layer=layer_ppp,
            )
            sections.append(ppp)

    if layer_via is not None:
        offset_top = width_npp + gap_high_doping[1] - width_via / 2
        offset_bot = width_ppp + gap_high_doping[0] - width_via / 2
        via_top = Section(width=width_via, offset=+offset_top, layer=layer_via)
        via_bot = Section(width=width_via, offset=-offset_bot, layer=layer_via)
        sections.append(via_top)
        sections.append(via_bot)

    if layer_metal is not None:
        offset_top = width_npp + gap_high_doping[1] - width_metal / 2
        offset_bot = width_ppp + gap_high_doping[0] - width_metal / 2
        port_types = ("electrical", "electrical")
        metal_top = Section(
            width=width_via,
            offset=+offset_top,
            layer=layer_metal,
            port_types=port_types,
            port_names=("e1_top", "e2_top"),
        )
        metal_bot = Section(
            width=width_via,
            offset=-offset_bot,
            layer=layer_metal,
            port_types=port_types,
            port_names=("e1_bot", "e2_bot"),
        )
        sections.append(metal_top)
        sections.append(metal_bot)

    return CrossSection(
        width=width,
        offset=0,
        layer=layer,
        port_names=port_names,
        sections=sections,
        cladding_offsets=cladding_offsets,
        cladding_layers=cladding_layers,
        **kwargs,
    )


def l_wg_doped_with_trenches(
    width: float = 0.5,
    layer: LayerSpec | None = None,
    layer_trench: LayerSpec = "DEEP_ETCH",
    gap_low_doping: float = 0.0,
    gap_medium_doping: float | None = 0.5,
    gap_high_doping: float | None = 1.0,
    width_doping: float = 8.0,
    width_slab: float = 7.0,
    width_trench: float = 2.0,
    layer_low: LayerSpec = "P",
    layer_mid: LayerSpec = "PP",
    layer_high: LayerSpec = "PPP",
    layer_via: LayerSpec | None = None,
    width_via: float = 1.0,
    layer_metal: LayerSpec | None = None,
    width_metal: float = 1.0,
    port_names: tuple[str, str] = ("o1", "o2"),
    cladding_layers: Layers | None = cladding_layers_optical,
    cladding_offsets: Floats | None = cladding_offsets_optical,
    wg_marking_layer: LayerSpec | None = None,
    **kwargs,
) -> CrossSection:
    """L waveguide PN doped cross_section.

    Args:
        width: width of the ridge in um.
        layer: ridge layer. None adds only ridge.
        layer_trench: layer to etch trenches.
        gap_low_doping: from waveguide outer edge to low doping. Only used for PIN.
        gap_medium_doping: from waveguide edge to medium doping. None removes it.
        gap_high_doping: from edge to high doping. None removes it.
        width_doping: in um.
        width_slab: in um.
        width_trench: in um.
        layer_low: low doping layer.
        layer_mid: mid doping layer.
        layer_high: high doping layer.
        layer_via: via layer.
        width_via: via width in um.
        layer_metal: metal layer.
        width_metal: metal width in um.
        port_names: input and output port names.
        cladding_layers: optional list of cladding layers.
        cladding_offsets: optional list of cladding offsets.
        wg_marking_layer: layer to mark where the actual guiding section is.
        kwargs: cross_section settings.

    .. code::

                                          gap_low_doping
                                           <------>
                                                  |
                                                  wg
                                                 edge
                                                  |
        _____                       _______ ______
             |                     |              |
             |_____________________|              |
                                                  |
                                                  |
                                    <------------>
                                           width
             <--------------------->               |
            width_trench       |                   |
                               |                   |
                               |<----------------->|
                                  gap_medium_doping
                     |<--------------------------->|
                             gap_high_doping
       <------------------------------------------->
                        width_slab

    .. plot::
        :include-source:

        import gdsfactory as gf

        xs = gf.cross_section.pn_with_trenches(width=0.5, gap_low_doping=0, width_doping=2.)
        p = gf.path.arc(radius=10, angle=45)
        c = p.extrude(xs)
        c.plot()
    """

    trench_offset = -1 * (width / 2 + width_trench / 2)
    sections = kwargs.pop("sections", [])
    sections += [
        Section(width=width_slab, layer=layer, offset=-1 * (width_slab / 2 - width / 2))
    ]
    sections += [Section(width=width_trench, offset=trench_offset, layer=layer_trench)]

    if wg_marking_layer is not None:
        sections += [Section(width=width, offset=0, layer=wg_marking_layer)]

    offset_low_doping = width / 2 - gap_low_doping - width_doping / 2

    low_doping = Section(
        width=width_doping,
        offset=offset_low_doping,
        layer=layer_low,
    )

    sections.append(low_doping)

    if gap_medium_doping is not None:
        width_medium_doping = width_doping - gap_medium_doping
        offset_medium_doping = width / 2 - gap_medium_doping - width_medium_doping / 2

        mid_doping = Section(
            width=width_medium_doping,
            offset=offset_medium_doping,
            layer=layer_mid,
        )
        sections.append(mid_doping)

    if gap_high_doping is not None:
        width_high_doping = width_doping - gap_high_doping
        offset_high_doping = width / 2 - gap_high_doping - width_high_doping / 2

        high_doping = Section(
            width=width_high_doping, offset=+offset_high_doping, layer=layer_high
        )

        sections.append(high_doping)

    if layer_via is not None:
        offset = offset_high_doping - width_high_doping / 2 + width_via / 2
        via = Section(width=width_via, offset=+offset, layer=layer_via)
        sections.append(via)

    if layer_metal is not None:
        offset = offset_high_doping - width_high_doping / 2 + width_metal / 2
        port_types = ("electrical", "electrical")
        metal = Section(
            width=width_via,
            offset=+offset,
            layer=layer_metal,
            port_types=port_types,
            port_names=("e1_top", "e2_top"),
        )
        sections.append(metal)

    return CrossSection(
        width=width,
        offset=0,
        layer=layer,
        port_names=port_names,
        sections=sections,
        cladding_offsets=cladding_offsets,
        cladding_layers=cladding_layers,
        **kwargs,
    )


def strip_heater_metal_undercut(
    width: float = 0.5,
    layer: LayerSpec = "WG",
    heater_width: float = 2.5,
    trench_width: float = 6.5,
    trench_gap: float = 2.0,
    layer_heater: LayerSpec = "HEATER",
    layer_trench: LayerSpec = "DEEPTRENCH",
    sections: Sections | None = None,
) -> CrossSection:
    """Returns strip cross_section with top metal and undercut trenches on both.

    sides.

    dimensions from https://doi.org/10.1364/OE.18.020298

    Args:
        width: waveguide width.
        layer: waveguide layer.
        heater_width: of metal heater.
        trench_width: in um.
        trench_gap: from waveguide edge to trench edge.
        layer_heater: heater layer.
        layer_trench: tench layer.
        kwargs: cross_section settings.

    .. code::

              |<-------heater_width--------->|
               ______________________________
              |                              |
              |         layer_heater         |
              |______________________________|

                   |<------width------>|
                    ____________________ trench_gap
                   |                   |<----------->|              |
                   |                   |             |   undercut   |
                   |       width       |             |              |
                   |                   |             |<------------>|
                   |___________________|             | trench_width |
                                                     |              |
                                                     |              |

    .. plot::
        :include-source:

        import gdsfactory as gf

        xs = gf.cross_section.strip_heater_metal_undercut(width=0.5, heater_width=2, trench_width=4, trench_gap=4)
        p = gf.path.arc(radius=10, angle=45)
        c = p.extrude(xs)
        c.plot()
    """
    trench_offset = trench_gap + trench_width / 2 + width / 2
    sections = list(sections or [])
    sections += [
        Section(
            layer=layer_heater,
            width=heater_width,
            port_names=port_names_electrical,
            port_types=port_types_electrical,
        ),
        Section(layer=layer_trench, width=trench_width, offset=+trench_offset),
        Section(layer=layer_trench, width=trench_width, offset=-trench_offset),
    ]

    return strip(
        width=width,
        layer=layer,
        sections=tuple(sections),
    )


def strip_heater_metal(
    width: float = 0.5,
    layer: LayerSpec = "WG",
    heater_width: float = 2.5,
    layer_heater: LayerSpec = "HEATER",
    sections: Sections | None = None,
) -> CrossSection:
    """Returns strip cross_section with top heater metal.

    dimensions from https://doi.org/10.1364/OE.18.020298

    Args:
        width: waveguide width (um).
        layer: waveguide layer.
        heater_width: of metal heater.
        layer_heater: for the metal.

    .. plot::
        :include-source:

        import gdsfactory as gf

        xs = gf.cross_section.strip_heater_metal(width=0.5, heater_width=2)
        p = gf.path.arc(radius=10, angle=45)
        c = p.extrude(xs)
        c.plot()
    """

    sections = list(sections or [])
    sections += [
        Section(
            layer=layer_heater,
            width=heater_width,
            port_names=port_names_electrical,
            port_types=port_types_electrical,
        )
    ]

    return strip(
        width=width,
        layer=layer,
        sections=sections,
        info=dict(heater_width=heater_width),
    )


def strip_heater_doped(
    width: float = 0.5,
    layer: LayerSpec = "WG",
    heater_width: float = 2.0,
    heater_gap: float = 0.8,
    layers_heater: LayerSpecs = ("WG", "NPP"),
    bbox_offsets_heater: tuple[float, ...] = (0, 0.1),
    sections: Sections | None = None,
    **kwargs,
) -> CrossSection:
    """Returns strip cross_section with N++ doped heaters on both sides.

    Args:
        width: in um.
        layer: waveguide spec.
        heater_width: in um.
        heater_gap: in um.
        layers_heater: for doped heater.
        bbox_offsets_heater: for each layers_heater.
        kwargs: cross_section settings.

    .. code::

                                  |<------width------>|
          ____________             ___________________               ______________
         |            |           |     undoped Si    |             |              |
         |layer_heater|           |  intrinsic region |<----------->| layer_heater |
         |____________|           |___________________|             |______________|
                                                                     <------------>
                                                        heater_gap     heater_width

    .. plot::
        :include-source:

        import gdsfactory as gf

        xs = gf.cross_section.strip_heater_doped(width=0.5, heater_width=2, heater_gap=0.5)
        p = gf.path.arc(radius=10, angle=45)
        c = p.extrude(xs)
        c.plot()
    """
    heater_offset = width / 2 + heater_gap + heater_width / 2

    sections = list(sections or [])
    sections += [
        Section(
            layer=layer,
            width=heater_width + 2 * cladding_offset,
            offset=+heater_offset,
        )
        for layer, cladding_offset in zip(layers_heater, bbox_offsets_heater)
    ]

    sections += [
        Section(
            layer=layer,
            width=heater_width + 2 * cladding_offset,
            offset=-heater_offset,
        )
        for layer, cladding_offset in zip(layers_heater, bbox_offsets_heater)
    ]

    return strip(
        width=width,
        layer=layer,
        sections=tuple(sections),
        **kwargs,
    )


strip_heater_doped_via_stack = partial(
    strip_heater_doped,
    layers_heater=("WG", "NPP", "VIAC"),
    bbox_offsets_heater=(0, 0.1, -0.2),
)


def rib_heater_doped(
    width: float = 0.5,
    layer: LayerSpec = "WG",
    heater_width: float = 2.0,
    heater_gap: float = 0.8,
    layer_heater: LayerSpec = "NPP",
    layer_slab: LayerSpec = "SLAB90",
    slab_gap: float = 0.2,
    with_top_heater: bool = True,
    with_bot_heater: bool = True,
    sections: Sections | None = None,
    **kwargs,
) -> CrossSection:
    """Returns rib cross_section with N++ doped heaters on both sides.

    dimensions from https://doi.org/10.1364/OE.27.010456

    .. code::

                                    |<------width------>|
                                     ____________________  heater_gap           slab_gap
                                    |                   |<----------->|             <-->
         ___ _______________________|                   |__________________________|___
        |   |            |                undoped Si                  |            |   |
        |   |layer_heater|                intrinsic region            |layer_heater|   |
        |___|____________|____________________________________________|____________|___|
                                                                       <---------->
                                                                        heater_width
        <------------------------------------------------------------------------------>
                                        slab_width

    .. plot::
        :include-source:

        import gdsfactory as gf

        xs = gf.cross_section.rib_heater_doped(width=0.5, heater_width=2, heater_gap=0.5, layer_heater='NPP')
        p = gf.path.arc(radius=10, angle=45)
        c = p.extrude(xs)
        c.plot()
    """
    heater_offset = width / 2 + heater_gap + heater_width / 2

    if with_bot_heater and with_top_heater:
        slab_width = width + 2 * heater_gap + 2 * heater_width + 2 * slab_gap
        slab_offset = 0
    elif with_top_heater:
        slab_width = width + heater_gap + heater_width + slab_gap
        slab_offset = -slab_width / 2
    elif with_bot_heater:
        slab_width = width + heater_gap + heater_width + slab_gap
        slab_offset = +slab_width / 2

    sections = list(sections or [])

    if with_bot_heater:
        sections += [
            Section(layer=layer_heater, width=heater_width, offset=+heater_offset)
        ]
    if with_top_heater:
        sections += [
            Section(layer=layer_heater, width=heater_width, offset=-heater_offset)
        ]
    sections += [
        Section(width=slab_width, layer=layer_slab, offset=slab_offset, name="slab")
    ]
    return strip(
        width=width,
        layer=layer,
        sections=tuple(sections),
        **kwargs,
    )


def rib_heater_doped_via_stack(
    width: float = 0.5,
    layer: LayerSpec = "WG",
    heater_width: float = 1.0,
    heater_gap: float = 0.8,
    layer_slab: LayerSpec = "SLAB90",
    layer_heater: LayerSpec = "NPP",
    via_stack_width: float = 2.0,
    via_stack_gap: float = 0.8,
    layers_via_stack: LayerSpecs = ("NPP", "VIAC"),
    bbox_offsets_via_stack: tuple[float, ...] = (0, -0.2),
    slab_gap: float = 0.2,
    slab_offset: float = 0,
    with_top_heater: bool = True,
    with_bot_heater: bool = True,
    sections: Sections | None = None,
) -> CrossSection:
    """Returns rib cross_section with N++ doped heaters on both sides.

    dimensions from https://doi.org/10.1364/OE.27.010456

    Args:
        width: in um.
        layer: for main waveguide section.
        heater_width: in um.
        heater_gap: in um.
        layer_slab: for pedestal.
        layer_heater: for doped heater.
        via_stack_width: for the contact.
        via_stack_gap: in um.
        layers_via_stack: for the contact.
        bbox_offsets_via_stack: for the contact.
        slab_gap: from heater edge.
        slab_offset: over the center of the slab.
        with_top_heater: adds top/left heater.
        with_bot_heater: adds bottom/right heater.

    .. code::

                                   |<----width------>|
       slab_gap                     __________________ via_stack_gap     via_stack width
       <-->                        |                 |<------------>|<--------------->
                                   |                 | heater_gap |
                                   |                 |<---------->|
        ___ _______________________|                 |___________________________ ____
       |   |            |              undoped Si                 |              |    |
       |   |layer_heater|              intrinsic region           |layer_heater  |    |
       |___|____________|_________________________________________|______________|____|
                                                                   <------------>
                                                                    heater_width
       <------------------------------------------------------------------------------>
                                       slab_width

    .. plot::
        :include-source:

        import gdsfactory as gf

        xs = gf.cross_section.rib_heater_doped_via_stack(width=0.5, heater_width=2, heater_gap=0.5, layer_heater='NPP')
        p = gf.path.arc(radius=10, angle=45)
        c = p.extrude(xs)
        c.plot()
    """
    if with_bot_heater and with_top_heater:
        slab_width = width + 2 * heater_gap + 2 * heater_width + 2 * slab_gap
    elif with_top_heater:
        slab_width = width + heater_gap + heater_width + slab_gap
        slab_offset -= slab_width / 2
    elif with_bot_heater:
        slab_width = width + heater_gap + heater_width + slab_gap
        slab_offset += slab_width / 2

    heater_offset = width / 2 + heater_gap + heater_width / 2
    via_stack_offset = width / 2 + via_stack_gap + via_stack_width / 2
    sections = list(sections or [])
    sections += [
        Section(width=slab_width, layer=layer_slab, offset=slab_offset, name="slab"),
    ]
    if with_bot_heater:
        sections += [
            Section(
                layer=layer_heater,
                width=heater_width,
                offset=+heater_offset,
            )
        ]

    if with_top_heater:
        sections += [
            Section(
                layer=layer_heater,
                width=heater_width,
                offset=-heater_offset,
            )
        ]

    if with_bot_heater:
        sections += [
            Section(
                layer=layer,
                width=heater_width + 2 * cladding_offset,
                offset=+via_stack_offset,
            )
            for layer, cladding_offset in zip(layers_via_stack, bbox_offsets_via_stack)
        ]

    if with_top_heater:
        sections += [
            Section(
                layer=layer,
                width=heater_width + 2 * cladding_offset,
                offset=-via_stack_offset,
            )
            for layer, cladding_offset in zip(layers_via_stack, bbox_offsets_via_stack)
        ]

    return strip(
        sections=tuple(sections),
        width=width,
        layer=layer,
    )


def pn_ge_detector_si_contacts(
    width_si: float = 6.0,
    layer_si: LayerSpec = "WG",
    width_ge: float = 3.0,
    layer_ge: LayerSpec = "GE",
    gap_low_doping: float = 0.6,
    gap_medium_doping: float | None = 0.9,
    gap_high_doping: float | None = 1.1,
    width_doping: float = 8.0,
    layer_p: LayerSpec = "P",
    layer_pp: LayerSpec = "PP",
    layer_ppp: LayerSpec = "PPP",
    layer_n: LayerSpec = "N",
    layer_np: LayerSpec = "NP",
    layer_npp: LayerSpec = "NPP",
    layer_via: LayerSpec | None = None,
    width_via: float = 1.0,
    layer_metal: LayerSpec | None = None,
    port_names: tuple[str, str] = ("o1", "o2"),
    cladding_layers: Layers | None = cladding_layers_optical,
    cladding_offsets: Floats | None = cladding_offsets_optical,
) -> CrossSection:
    """Linear Ge detector cross section based on a lateral p(i)n junction.

    It has silicon contacts (no contact on the Ge). The contacts need to be
    created in the component generating function (they can't be created here).

    See Chen et al., "High-Responsivity Low-Voltage 28-Gb/s Ge p-i-n Photodetector
    With Silicon Contacts", Journal of Lightwave Technology 33(4), 2015.

    Notice it is possible to have dopings going beyond the ridge waveguide. This
    is fine, and it is to account for the
    presence of the contacts. Such contacts can be subwavelength or not.

    Args:
        width_si: width of the full etch si in um.
        layer_si: si ridge layer.
        width_ge: width of the ge in um.
        layer_ge: ge layer.
        gap_low_doping: from waveguide center to low doping.
        gap_medium_doping: from waveguide center to medium doping. None removes it.
        gap_high_doping: from center to high doping. None removes it.
        width_doping: distance from waveguide center to the edge of the p (or n) doping in um.
        layer_p: p doping layer.
        layer_pp: p+ doping layer.
        layer_ppp: p++ doping layer.
        layer_n: n doping layer.
        layer_np: n+ doping layer.
        layer_npp: n++ doping layer.
        layer_via: via layer.
        width_via: via width in um.
        layer_metal: metal layer.

    .. code::

                                   layer_si
                           |<------width_si---->|

                                  layer_ge
                              |<--width_ge->|
                               ______________
                              |             |
                            __|_____________|___
                           |     |       |     |
                           |     |       |     |
                    P      |     |       |     |         N                |
                 width_p   |_____|_______|_____|           width_n        |
        <----------------------->|       |<------------------------------>|
                                     |<->|
                                     gap_low_doping
                                     |         |        N+                |
                                     |         |     width_np             |
                                     |         |<------------------------>|
                                     |<------->|
                                     |     gap_medium_doping
                                     |
                                     |<---------------------------------->|
                                                width_doping

    .. plot::
        :include-source:

        import gdsfactory as gf

        xs = gf.cross_section.pn()
        p = gf.path.arc(radius=10, angle=45)
        c = p.extrude(xs)
        c.plot()
    """
    width_low_doping = width_doping - gap_low_doping
    offset_low_doping = width_low_doping / 2 + gap_low_doping

    n = Section(width=width_low_doping, offset=+offset_low_doping, layer=layer_n)
    p = Section(width=width_low_doping, offset=-offset_low_doping, layer=layer_p)
    sections = [n, p]
    if gap_medium_doping is not None:
        width_medium_doping = width_doping - gap_medium_doping
        offset_medium_doping = width_medium_doping / 2 + gap_medium_doping

        np = Section(
            width=width_medium_doping,
            offset=+offset_medium_doping,
            layer=layer_np,
        )
        pp = Section(
            width=width_medium_doping,
            offset=-offset_medium_doping,
            layer=layer_pp,
        )
        sections.extend((np, pp))
    if gap_high_doping is not None:
        width_high_doping = width_doping - gap_high_doping
        offset_high_doping = width_high_doping / 2 + gap_high_doping
        npp = Section(
            width=width_high_doping, offset=+offset_high_doping, layer=layer_npp
        )
        ppp = Section(
            width=width_high_doping, offset=-offset_high_doping, layer=layer_ppp
        )
        sections.extend((npp, ppp))
    if layer_via is not None:
        offset = width_high_doping / 2 + gap_high_doping
        via_top = Section(width=width_via, offset=+offset, layer=layer_via)
        via_bot = Section(width=width_via, offset=-offset, layer=layer_via)
        sections.extend((via_top, via_bot))
    if layer_metal is not None:
        offset = width_high_doping / 2 + gap_high_doping
        port_types = ("electrical", "electrical")
        metal_top = Section(
            width=width_via,
            offset=+offset,
            layer=layer_metal,
            port_types=port_types,
            port_names=("e1_top", "e2_top"),
        )
        metal_bot = Section(
            width=width_via,
            offset=-offset,
            layer=layer_metal,
            port_types=port_types,
            port_names=("e1_bot", "e2_bot"),
        )
        sections.extend((metal_top, metal_bot))

    # Add the Ge
    s = Section(width=width_ge, offset=0, layer=layer_ge)
    sections.append(s)

    return CrossSection(
        width=width_si,
        offset=0,
        layer=layer_si,
        port_names=port_names,
        sections=sections,
        cladding_offsets=cladding_offsets,
        cladding_layers=cladding_layers,
    )


CrossSectionFactory = Callable[..., CrossSection]


def get_cross_sections(
    modules, verbose: bool = False
) -> dict[str, CrossSectionFactory]:
    """Returns cross_sections from a module or list of modules.

    Args:
        modules: module or iterable of modules.
        verbose: prints in case any errors occur.
    """
    modules = modules if isinstance(modules, Iterable) else [modules]

    xs = {}
    for module in modules:
        for t in getmembers(module):
            if isinstance(t[1], CrossSection):
                xs[t[0]] = t[1]
    return xs


xs_sc = strip()
xs_rc = rib(bbox_layers=["DEVREC"], bbox_offsets=[0.0])
xs_rc2 = rib2()

xs_sc_heater_metal = strip_heater_metal()
xs_sc_heater_metal_undercut = strip_heater_metal_undercut()
xs_slot = slot()

xs_heater_metal = heater_metal()
xs_metal_routing = xs_m1 = metal1()
xs_m2 = metal2()
xs_m3 = metal3()
cross_sections = get_cross_sections(sys.modules[__name__])


def test_copy() -> None:
    import gdsfactory as gf

    p = gf.path.straight()
    copied_cs = gf.cross_section.strip().copy()
    gf.path.extrude(p, cross_section=copied_cs)


if __name__ == "__main__":
    import gdsfactory as gf

    xs = gf.cross_section.pin(
        width=0.5,
        # gap_low_doping=0.05,
        # width_doping=2.0,
        # offset_low_doping=0,
    )
    # xs = pn_with_trenches(width=0.3)
    # xs = slot(width=0.3)
    # xs = rib_with_trenches()
    p = gf.path.straight()
    print(xs.copy(width=10))
    # c = p.extrude(xs)
    # xs = l_with_trenches(
    #     width=0.5,
    #     width_trench=2.0,
    #     width_slab=7.0,
    # )
    # p = gf.path.straight()
    # c = p.extrude(xs)
    # xs = l_wg_doped_with_trenches(
    #     layer="WG", width=0.5, width_trench=2.0, width_slab=7.0, gap_low_doping=0.1
    # )
    # p = gf.path.straight()
    # c = p.extrude(cross_section=xs)
    # xs = rib_with_trenches() # FIXME
    # c = gf.components.straight(cross_section=xs)
    # c = gf.components.straight(cross_section="strip")

    # xs = l_wg()
    # p = gf.path.straight()
    # c = p.extrude(xs)
    # c.show(show_ports=True)
    # x = CrossSection(width=0.5)
"xs_sc"
