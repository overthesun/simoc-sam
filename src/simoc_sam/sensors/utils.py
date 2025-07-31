import os
import sys
import pathlib
import asyncio
import argparse
import subprocess

from typing import Dict, Any
from datetime import datetime
from dataclasses import dataclass, field

from .basesensor import MQTTWrapper

import tomli


def format_reading(reading, *, time_fmt='%H:%M:%S', sensor_info=None):
    """Format a sensor reading and return it as a string."""
    r = dict(reading)  # make a copy
    n = r.pop('n')
    dt = datetime.strptime(r.pop('timestamp'), '%Y-%m-%d %H:%M:%S.%f')
    timestamp = dt.strftime(time_fmt)
    sensor_name = sensor_info['sensor_name'] if sensor_info else '-'
    reading_info = sensor_info['reading_info'] if sensor_info else None
    result = []
    for key, value in r.items():
        v = f'{value:.2f}' if isinstance(value, float) else str(value)
        label, unit = key, ''
        if reading_info:
            label = reading_info[key]['label']
            unit = ' ' + reading_info[key]['unit']
        result.append(f'{label}: {v}{unit}')
    return f'{sensor_name}|{timestamp}|{n:<3}  {"; ".join(result)}'


def get_sensor_i2c_bus(sensor_i2c_addr, *args, **kwargs):
    import busio
    # this method is currently unused as it requires
    # https://github.com/adafruit/Adafruit_Blinka/pull/637 to work
    from adafruit_blinka.microcontroller.mcp2221.mcp2221 import MCP2221

    addresses = MCP2221.available_paths()
    for address in addresses:
        try:
            bus = busio.I2C(*args, **kwargs, bus_id=address)
        except (OSError, RuntimeError) as e:
            continue
        i2c_devices = bus.scan()
        if sensor_i2c_addr in i2c_devices:
            return bus
        else:
            bus.deinit()


@dataclass
class SensorData:
    name: str
    description: str
    module: str
    i2c_address: str
    data: Dict[str, Any] = field(default_factory=dict)

SENSORS_TOML = pathlib.Path(__file__).with_name('sensors.toml')

def load_sensor_data(file_path=SENSORS_TOML):
    with open(file_path, 'rb') as f:
        sensors = tomli.load(f)
    sensor_data = {}
    for sensor_name, sensor_info in sensors.items():
        sensor_data[sensor_name] = SensorData(
            name=sensor_info['name'],
            description=sensor_info['description'],
            module=sensor_info['module'],
            i2c_address=sensor_info['i2c_address'],
            data=sensor_info['data'],
        )
    return sensor_data

SENSOR_DATA = load_sensor_data()
I2C_TO_SENSOR = {info.i2c_address: info for info in SENSOR_DATA.values()}

def has_mcp2221():
    return b'MCP2221' in subprocess.check_output("lsusb")

def import_board():
    """Import the board module while checking for MCP2221s."""
    if has_mcp2221():
        os.environ['BLINKA_MCP2221'] = '1'
        os.environ['BLINKA_MCP2221_RESET_DELAY'] = '-1'
    import board
    return board

def import_busio():
    try:
        import busio
        return busio
    except RuntimeError:
        sys.exit("Failed to import 'busio', is the sensor plugged in?")

def get_mqtt_addr():
    addr = os.environ.get('MQTTSERVER_ADDR', 'sambridge1:1883')
    host, port = addr.split(':')
    return host, int(port)

def get_sioserver_addr():
    addr = os.environ.get('SIOSERVER_ADDR', 'localhost:8081')
    host, port = addr.split(':')
    return host, int(port)


def get_addr_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', help='The hostname of the server.')
    parser.add_argument('--port', type=int,
                        help='The port used by the server.')
    return parser


def parse_args(arguments=None, *, read_delay=10):
    parser = get_addr_argparser()
    parser.add_argument('-d', '--read-delay', default=read_delay,
                        dest='delay', metavar='DELAY', type=float,
                        help='How many seconds between readings.')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose output for sensor/MQTT.')
    parser.add_argument('--verbose-sensor', action='store_true',
                        help='Enable verbose output for the sensor.')
    parser.add_argument('--verbose-mqtt', action='store_true',
                        help='Enable verbose output for MQTT.')
    parser.add_argument('--mqtt', action='store_true',
                        help='Run the sensor with MQTT.')
    # TODO: put this in a separate parser
    parser.add_argument('--mqtt-topic', default='sam/#',
                        help='The MQTT topic to subscribe to.')
    args = parser.parse_args(arguments)
    if args.mqtt and (not args.host or not args.port):
        host, port = get_mqtt_addr()
        args.host = args.host or host
        args.port = args.port or port
    if args.verbose:
        args.verbose_sensor = args.verbose_mqtt = True
    return args


def start_sensor(sensor_cls, *pargs, **kwargs):
    args = parse_args()
    # TODO: add cmd line options for name/desc
    with sensor_cls(verbose=args.verbose_sensor, *pargs, **kwargs) as sensor:
        if args.mqtt:
            delay, verbose = args.delay, args.verbose_mqtt
            host, port = args.host, args.port
            mqttwrapper = MQTTWrapper(sensor, read_delay=delay, verbose=verbose)
            mqttwrapper.start(host, port)
            try:
                mqttwrapper.send_data()
            except KeyboardInterrupt:
                print('Sensor stopped')
            mqttwrapper.stop()
        else:
            for reading in sensor.iter_readings(delay=args.delay):
                pass  # the sensor already prints the readings when verbose
