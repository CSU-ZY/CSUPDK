""" gdsfactory loads a configuration from 3 files, high priority overwrites low priority:

1. A config.yml found in the current working directory (highest priority)
2. ~/.gdsfactory/config.yml specific for the machine
3. the default_config in pp/config.py (lowest priority)

`CONFIG` has all the paths that we do not care
`conf` has all the useful info
"""

__version__ = "2.2.2"
from typing import Any, Dict
import tempfile
import os
import io
import json
import subprocess
import pathlib
from pprint import pprint
import logging

import numpy as np
from omegaconf import OmegaConf
from git import Repo
from git import InvalidGitRepositoryError


connections: Dict[str, str] = {}  # global variable to store connections in a dict
home = pathlib.Path.home()
cwd = pathlib.Path.cwd()
module_path = pathlib.Path(__file__).parent.absolute()
repo_path = module_path.parent
home_path = pathlib.Path.home() / ".gdsfactory"

cwd_config = cwd / "config.yml"
module_config = module_path / "config.yml"
home_config = home_path / "config.yml"

dirpath_build = pathlib.Path(tempfile.TemporaryDirectory().name)
dirpath_test = pathlib.Path(tempfile.TemporaryDirectory().name)
MAX_NAME_LENGTH = 32


def clear_connections(connections=connections):
    """Clears the connections that have been stored in connections dict."""
    connections = {}
    return connections


def add_to_global_netlist(port1, port2) -> Dict[str, str]:
    """Add port1 to port2 connection to the connections global netlist dict.

    Args:
        port1: src port
        port1: dst port

    Returns:
        Dict: src_name

    """
    global connections

    src = port1.parent if port1.parent else port1
    dst = port2.parent if port2.parent else port2

    src_name = src.name if hasattr(src, "name") else src.parent.name
    dst_name = dst.name if hasattr(dst, "name") else dst.parent.name

    src_uid = src.parent.uid if hasattr(src, "parent") else -1
    dst_uid = dst.parent.uid if hasattr(dst, "parent") else -1

    src_uid = src.parent.uid if hasattr(src, "parent") else -1
    dst_uid = dst.parent.uid if hasattr(dst, "parent") else -1

    connections[
        f"{src_name},{src_uid},{int(src.x)},{int(src.y)},{port1.name},{port1.uid}"
    ] = f"{dst_name},{dst_uid},{int(dst.x)},{int(dst.y)},{port2.name},{port2.uid}"


conf = OmegaConf.load(
    io.StringIO(
        """
tech:
    name: generic
    cache_url:
    wg_expanded_width: 2.5
    taper_length: 35.0
    grid_unit: 1e-6
    grid_resolution: 1e-9
    bend_radius: 10.0
    cladding_offset: 0.0
"""
    )
)


if home_config.exists():
    config_home = OmegaConf.load(home_config)
    conf = OmegaConf.merge(conf, config_home)

if cwd_config.exists():
    config_cwd = OmegaConf.load(cwd_config)
    conf = OmegaConf.merge(conf, config_cwd)

conf.version = __version__

try:
    conf.git_hash = Repo(repo_path, search_parent_directories=True).head.object.hexsha
    conf.git_hash_cwd = Repo(cwd, search_parent_directories=True).head.object.hexsha
except InvalidGitRepositoryError:
    pass


CONFIG = dict(
    config_path=cwd_config.absolute(),
    repo_path=repo_path,
    module_path=module_path,
    gdsdir=module_path / "gds",
    font_path=module_path / "gds" / "alphabet.gds",
    masks_path=repo_path / "mask",
    version=__version__,
    home=home,
    cwd=cwd,
)

mask_name = "notDefined"

if "mask" in conf:
    mask_name = conf.mask.name
    mask_config_directory = cwd
    build_directory = mask_config_directory / "build"
    CONFIG["devices_directory"] = mask_config_directory / "devices"
    CONFIG["mask_gds"] = mask_config_directory / "build" / "mask" / f"{mask_name}.gds"
else:
    dirpath_build.mkdir(exist_ok=True)
    build_directory = dirpath_build
    mask_config_directory = dirpath_build

CONFIG["custom_components"] = conf.custom_components
CONFIG["gdslib"] = conf.gdslib or repo_path / "gdslib"
CONFIG["sp"] = CONFIG["gdslib"] / "sp"
CONFIG["gds"] = CONFIG["gdslib"] / "gds"
CONFIG["gdslib_test"] = dirpath_test

CONFIG["build_directory"] = build_directory
CONFIG["gds_directory"] = build_directory / "devices"
CONFIG["cache_doe_directory"] = build_directory / "cache_doe"
CONFIG["doe_directory"] = build_directory / "doe"
CONFIG["mask_directory"] = build_directory / "mask"
CONFIG["mask_gds"] = build_directory / "mask" / (mask_name + ".gds")
CONFIG["mask_config_directory"] = mask_config_directory
CONFIG["samples_path"] = module_path / "samples"
CONFIG["netlists"] = module_path / "samples" / "netlists"
CONFIG["components_path"] = module_path / "components"

if "gds_resources" in CONFIG:
    CONFIG["gds_resources"] = CONFIG["masks_path"] / CONFIG["gds_resources"]

build_directory.mkdir(exist_ok=True)
CONFIG["gds_directory"].mkdir(exist_ok=True)
CONFIG["doe_directory"].mkdir(exist_ok=True)
CONFIG["mask_directory"].mkdir(exist_ok=True)
CONFIG["gdslib_test"].mkdir(exist_ok=True)


logging.basicConfig(
    filename=CONFIG["build_directory"] / "log.log",
    filemode="w",
    format="%(name)s - %(levelname)s - %(message)s",
)
logging.warning("This will get logged to a file")


def print_config(key=None):
    if key:
        if CONFIG.get(key):
            print(CONFIG[key])
        else:
            print(f"`{key}` key not found in {cwd_config}")
    else:
        pprint(CONFIG)


def complex_encoder(z):
    if isinstance(z, pathlib.Path):
        return str(z)
    else:
        type_name = type(z)
        raise TypeError(f"Object {z} of type {type_name} is not serializable")


def write_config(config, json_out_path):
    with open(json_out_path, "w") as f:
        json.dump(config, f, indent=2, sort_keys=True, default=complex_encoder)


def call_if_func(f: Any, **kwargs) -> Any:
    return f(**kwargs) if callable(f) else f


def get_git_hash():
    """ Get the current git hash """
    try:
        with open(os.devnull, "w") as shutup:
            return (
                subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=shutup)
                .decode("utf-8")
                .strip("\n")
            )
    except subprocess.CalledProcessError:
        return "not_a_git_repo"


GRID_RESOLUTION = conf.tech.grid_resolution
GRID_PER_UNIT = conf.tech.grid_unit / GRID_RESOLUTION
GRID_ROUNDING_RESOLUTION = int(np.log10(GRID_PER_UNIT))
BEND_RADIUS = conf.tech.bend_radius
TAPER_LENGTH = conf.tech.taper_length
WG_EXPANDED_WIDTH = conf.tech.wg_expanded_width

materials = {
    "si": "Si (Silicon) - Palik",
    "sio2": "SiO2 (Glass) - Palik",
    "sin": "Si3N4 (Silicon Nitride) - Phillip",
}


if __name__ == "__main__":
    # print(conf)
    # print_config("gdslib")
    # print_config()
    # print(CONFIG["git_hash"])
    print(CONFIG["sp"])
    # print(CONFIG)
