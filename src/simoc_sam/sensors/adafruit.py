import os
import asyncio
import importlib

from contextlib import ExitStack

from . import utils
from .basesensor import SIOWrapper

board = utils.import_board()

import busio

from adafruit_blinka.microcontroller.mcp2221.mcp2221 import MCP2221

device_to_i2c_addr = dict(
    bme688=0x77,
    sgp30=0x58,
    scd30=0x61,
)
i2c_addr_to_device = dict(zip(device_to_i2c_addr.values(),
                              device_to_i2c_addr.keys()))

async def main():
    addresses = MCP2221.available_paths()

    sensors_classes = []
    for address in addresses:
        try:
            bus = busio.I2C(bus_id=address)
        except (OSError, RuntimeError) as e:
            print(f'Error opening {address}')
            continue
        i2c_devices = bus.scan()
        print(f'{address=}; {bus=}; {i2c_devices=}')
        if i2c_devices:
            print(f'{len(i2c_devices)} device(s) found on <{address.decode()}>:')
            for i2c_addr in i2c_devices:
                device = i2c_addr_to_device[i2c_addr]
                print(f'  * {device} ({i2c_addr:#x})')
                mod = importlib.import_module(f'simoc_sam.sensors.{device}')
                #print(f'Imported {mod}')
                sensors_classes.append(getattr(mod, device.upper()))
        else:
            print(f'No device found on <{address.decode()}>.')
            bus.deinit()
    print(sensors_classes)
    args = utils.parse_args()
    delay, verbose = args.delay, args.verbose_sio
    host, port = args.host, args.port
    with ExitStack() as stack:
        sensors = [stack.enter_context(sensor_cls(verbose=args.verbose_sensor))
                   for sensor_cls in sensors_classes]
        siowrappers = [SIOWrapper(sensor, read_delay=delay, verbose=verbose)
                       for sensor in sensors]
        await asyncio.gather(*[siow.start(host, port) for siow in siowrappers])

asyncio.run(main())
