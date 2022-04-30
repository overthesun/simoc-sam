import re
import asyncio
import argparse
import configparser

from datetime import datetime
from contextlib import ExitStack

from basesensor import SIOWrapper


def check_for_MCP2221():
    """Check to see if the MCP2221 is connected"""
    import subprocess
    return "MCP2221" in str(subprocess.check_output("lsusb"))

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


def alphanum(string):
    """Return a string with non-alphanumeric characters removed"""
    return re.sub(r'[^a-zA-Z0-9]', '', string)

def format_sensor_id(location, sensor_type, sensor_name):
    return f'{location}_{sensor_type}_{sensor_name}'

def get_sensor_id(sensor_info, active_sensors=[], serial_length=5):
    """Return a unique, non-random id for each location/type/device"""

    # The location is a unique identifier for the device where the class
    # instance of the sensor is running (e.g. a Raspberry Pi), and should be
    # descriptive (e.g. 'greenhouse').
    location = alphanum(sensor_info.get('location') or 'loc0')
    # Hardcoded into the class instance.
    sensor_type = alphanum(sensor_info.get('sensor_type', 'sensor0'))
    # The sensor name is a unique identifier for the sensor itself, in case two
    # sensors of the same type are connected at the same location.
    serial_no = sensor_info.get('serial_no', None)
    if serial_no is not None:
        serial_no = alphanum(serial_no)[:serial_length]
    else:
        serial_no = 0
        while True:
            id = format_sensor_id(location, sensor_type, serial_no)
            if id not in active_sensors:
                break
            else:
                serial_no += 1
    return format_sensor_id(location, sensor_type, serial_no)

def get_sensor_info_from_cfg(sensor_type, cfg_file='config.cfg'):
    config = configparser.ConfigParser()
    config.read(cfg_file)
    sensor_info = dict()
    for name, section in config.items():
        if name.lower() == 'host':
            location = section.get('location')
            if location is not None:
                sensor_info['location'] = location
        elif name.lower().startswith('sensor') and 'type' in section:
            if section['type'].lower() == sensor_type.lower():
                sensor_info.update(section)
    return sensor_info

def parse_args(*, read_delay=1, port=8081):
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--read-delay', default=read_delay,
                        dest='delay', metavar='DELAY', type=int,
                        help='How many seconds between readings.')
    parser.add_argument('--host', default="localhost", type=str,
                        help='The IP of the host where sioserver is running.')
    parser.add_argument('--port', default=None, type=str,
                        help='The port used to connect to the socketio server.')
    parser.add_argument('--no-sio', action='store_true',
                        help='Run the sensor without socketio.')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose output for sensor and socketio.')
    parser.add_argument('--verbose-sensor', action='store_true',
                        help='Enable verbose output for the sensor.')
    parser.add_argument('--verbose-sio', action='store_true',
                        help='Enable verbose output for the socketio.')

    args = parser.parse_args()
    if args.verbose:
        args.verbose_sensor = args.verbose_sio = True
    if args.no_sio and args.port is not None:
        parser.error("Can't specify the socketio port with --no-sio.")
    if not args.no_sio and args.port is None:
        args.port = port
    return args


def start_sensor(sensor_cls, *pargs, **kwargs):
    args = parse_args()
    sensor_info = get_sensor_info_from_cfg(sensor_cls.sensor_type)
    # get the name/desc from the config unless the user passed them as kwargs
    for attr in ['location', 'name', 'description']:
        if attr not in kwargs and sensor_info and attr in sensor_info:
            kwargs[attr] = sensor_info[attr]
    # Use ExitStack from contextlib, line 116, use with statement on many classes at once
    with sensor_cls(verbose=args.verbose_sensor, *pargs, **kwargs) as sensor:
        if args.no_sio:
            for reading in sensor.iter_readings(delay=args.delay):
                pass  # the sensor already prints the readings when verbose
        else:
            delay, verbose, port, host = args.delay, args.verbose_sio, args.port, args.host
            siowrapper = SIOWrapper(sensor, read_delay=delay, verbose=verbose)
            # asyncio.gather
            asyncio.run(siowrapper.start(port, host))

def start_sensors(sensor_classes, *pargs, **kwargs):
    args = parse_args()
    sensors_info = []
    for (sensor_cls, _) in sensor_classes:
        sensor_info = get_sensor_info_from_cfg(sensor_cls.sensor_type)
        for attr in ['location', 'name', 'description']:
            if attr not in kwargs and sensor_info and attr in sensor_info:
                kwargs[attr] = sensor_info[attr]
        sensors_info.append(sensor_info)
    with ExitStack() as stack:
        v = args.verbose_sensor
        sensors = [stack.enter_context(sensor_cls(verbose=v, device=device, *pargs, **kwargs))
                   for (sensor_cls, device) in sensor_classes]
        delay, verbose, port, host = args.delay, args.verbose_sio, args.port, args.host
        wrappers = [SIOWrapper(sensor, read_delay=delay, verbose=verbose)
                    for sensor in sensors]
        asyncio.gather(*[wrapper.start(port, host) for wrapper in wrappers])
