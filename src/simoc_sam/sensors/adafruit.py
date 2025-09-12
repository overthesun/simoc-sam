# TODO:
# * verify if this script still works
# * add unit tests if it does, remove it otherwise

import os
import asyncio
import importlib

from contextlib import ExitStack

from . import utils
from .basesensor import MQTTWrapper

board = utils.import_board()

import busio

from adafruit_blinka.microcontroller.mcp2221.mcp2221 import MCP2221


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
                device = utils.I2C_TO_SENSOR[i2c_addr]
                print(f'  * {device.name} ({i2c_addr:#x})')
                mod = importlib.import_module(device.module)
                #print(f'Imported {mod}')
                sensors_classes.append(getattr(mod, device.name))
        else:
            print(f'No device found on <{address.decode()}>.')
            bus.deinit()
    print(sensors_classes)
    args = utils.parse_args()
    delay, verbose = args.delay, args.verbose_mqtt
    host, port = args.host, args.port
    with ExitStack() as stack:
        sensors = [stack.enter_context(sensor_cls(verbose=args.verbose_sensor))
                   for sensor_cls in sensors_classes]
        mqttwrappers = [MQTTWrapper(sensor, read_delay=delay, verbose=verbose)
                       for sensor in sensors]
        await asyncio.gather(*[mqttw.start(host, port) for mqttw in mqttwrappers])

asyncio.run(main())
