from __future__ import annotations

import pytest
from pytest_regressions.data_regression import DataRegressionFixture

import gdsfactory as gf
from gdsfactory.component import Component
from gdsfactory.difftest import difftest


def test_type0() -> Component:
    c = gf.pcells.straight_heater_metal(length=100.0)
    return gf.routing.add_pads_top(component=c, port_names=("e1",))


pcells = [test_type0]


@pytest.fixture(params=pcells, scope="function")
def component(request) -> Component:
    return request.param()


def test_gds(component: Component) -> None:
    """Avoid regressions in GDS geometry shapes and layers."""
    difftest(component)


def test_settings(component: Component, data_regression: DataRegressionFixture) -> None:
    """Avoid regressions when exporting settings."""
    data_regression.check(component.to_dict())


if __name__ == "__main__":
    c = test_type0()
    c.show(show_ports=True)
