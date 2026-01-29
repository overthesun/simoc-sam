"""Utilities for display drivers."""

import pathlib

from collections import defaultdict
from dataclasses import dataclass

import tomli


@dataclass
class DisplayData:
    name: str
    description: str
    module: str
    width: int
    height: int
    i2c_address: int
    reset_pin: str = None


DISPLAYS_TOML = pathlib.Path(__file__).with_name('displays.toml')


def load_display_data(file_path=DISPLAYS_TOML):
    """Load display configuration from displays.toml."""
    with open(file_path, 'rb') as f:
        displays = tomli.load(f)
    display_data = {}
    for display_key, display_info in displays.items():
        display_data[display_key] = DisplayData(
            name=display_info['name'],
            description=display_info['description'],
            module=display_info['module'],
            width=display_info['width'],
            height=display_info['height'],
            i2c_address=display_info.get('i2c_address'),
            reset_pin=display_info.get('reset_pin'),
        )
    return display_data


DISPLAY_DATA = load_display_data()
I2C_TO_DISPLAY_NAMES = defaultdict(list)
for name, info in DISPLAY_DATA.items():
    I2C_TO_DISPLAY_NAMES[info.i2c_address].append(name)
