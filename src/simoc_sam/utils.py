"""Misc utility functions."""

import warnings

from .sensors import utils as sensor_utils

_i2c_cache = {}
def get_i2c():
    """Get or create a cached I2C bus instance."""
    if 'i2c' not in _i2c_cache:
        board = sensor_utils.import_board()
        busio = sensor_utils.import_busio()
        _i2c_cache['i2c'] = busio.I2C(board.SCL, board.SDA)
    return _i2c_cache['i2c']


def get_i2c_addresses():
    """Scan I2C bus for connected devices and return their I2C addresses."""
    try:
        return get_i2c().scan()
    except (AttributeError, ValueError, OSError, RuntimeError) as err:
        raise RuntimeError(f'I2C scan failed: {err}') from err


def get_i2c_names():
    """Scan I2C bus and return the names of connected devices."""
    return [i2c_to_device_name(i2c_addr) for i2c_addr in get_i2c_addresses()]


def i2c_to_device_name(addr):
    """Resolve an I2C address to a device name."""
    names = sensor_utils.I2C_TO_SENSOR_NAMES.get(addr, [])
    if not names:
        return '<unknown>'
    if len(names) == 1:
        return names[0]
    # multiple devices with the same address -- probe chip ID to disambiguate
    i2c = get_i2c()
    for name in names:
        info = sensor_utils.SENSOR_DATA[name]
        if info.chip_id_register is not None and info.chip_id is not None:
            try:
                result = bytearray(1)
                i2c.writeto_then_readfrom(addr, bytes([info.chip_id_register]), result)
                if result[0] == info.chip_id:
                    return name
            except (OSError, RuntimeError):
                continue
    # Could not disambiguate - warn and return first candidate's key
    warnings.warn(
        f"Failed to disambiguate sensor at address {addr:#02x}. "
        f"Candidates: {names}. Defaulting to '{names[0]}'.",
        RuntimeWarning
    )
    return names[0]
