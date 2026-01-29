"""Misc utility functions."""

import json
import time
import asyncio
import warnings

from .sensors import utils as sensor_utils

_i2c_cache = {}


def uptime():
    """Return uptime string in HH:MM:SS format."""
    t = int(time.monotonic())
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"Up {h:02}:{m:02}:{s:02}"


async def read_jsonl_file(file_path):
    """Async generator that yields new lines from a JSONL file (like tail -f).

    Waits for file creation if it doesn't exist, then continuously monitors
    and yields new JSON entries as they're appended to the file.
    """
    try:
        # if file doesn't exist, wait for it to be created
        while not file_path.exists():
            print(f'Waiting for log file to be created: {file_path}')
            await asyncio.sleep(1)
        print(f'Starting to monitor log file for new lines: {file_path}')
        with open(file_path, buffering=1) as f:
            # seek to end of file and monitor for new lines
            f.seek(0, 2)
            while True:
                line = f.readline()
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as e:
                        print(f'Error parsing JSON from {file_path}: {e}')
                        continue
                else:
                    # no new line, wait a bit before checking again
                    await asyncio.sleep(1)
    except Exception as e:
        print(f'Error reading log file {file_path}: {e}')


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
        return sorted(get_i2c().scan())
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
