import re
import asyncio
import configparser

from datetime import datetime
from contextlib import ExitStack

from basesensor import SIOWrapper

def start_sensor(sensor_cls, *pargs, **kwargs):
    args = parse_args()
    sensor_info = get_sensor_info_from_cfg(sensor_cls.sensor_type)
    # get the name/desc from the config unless the user passed them as kwargs
    for attr in ['location', 'name', 'description']:
        if attr not in kwargs and sensor_info and attr in sensor_info:
            kwargs[attr] = sensor_info[attr]
    with sensor_cls(verbose=args.verbose_sensor, *pargs, **kwargs) as sensor:
        if args.no_sio:
            for reading in sensor.iter_readings(delay=args.delay):
                pass  # the sensor already prints the readings when verbose
        else:
            delay, verbose, port, host = args.delay, args.verbose_sio, args.port, args.host
            siowrapper = SIOWrapper(sensor, read_delay=delay, verbose=verbose)
            asyncio.run(siowrapper.start(port, host))

def start_sensors(sensor_classes):
    args = parse_args()
    async def start_concurrently():
        with ExitStack() as stack:
            v = args.verbose_sensor
            sensors = []
            for (sensor_cls, device, kwargs) in sensor_classes:
                sensor_info = get_sensor_info_from_cfg(sensor_cls.sensor_type)
                for attr in ['location', 'name', 'description']:
                    if attr not in kwargs and sensor_info and attr in sensor_info:
                        kwargs[attr] = sensor_info[attr]
                sensors.append(stack.enter_context(sensor_cls(verbose=v, device=device, **kwargs)))
            delay, verbose, port, host = args.delay, args.verbose_sio, args.port, args.host
            wrappers = [SIOWrapper(sensor, read_delay=delay, verbose=verbose)
                        for sensor in sensors]
            await asyncio.gather(*[wrapper.start(port, host) for wrapper in 

def check_for_MCP2221():
    """Check to see if the MCP2221 is connected"""
    import subprocess
    return "MCP2221" in str(subprocess.check_output("lsusb"))

def alphanum(string):
    """Return a string with non-alphanumeric characters removed"""
    return re.sub(r'[^a-zA-Z0-9]', '', string)

def format_sensor_id(location, sensor_type, sensor_name):
    return f'{location}_{sensor_type}_{sensor_name}'

def get_sensor_id(sensor_info, active_sensors=[], serial_length=-1):
    """Return a unique, non-random id for each location/type/device"""

    # The location is a unique identifier for the device where the class
    # instance of the sensor is running (e.g. a Raspberry Pi), and should be
    # descriptive (e.g. 'greenhouse').
    location = alphanum(sensor_info.get('location') or 'loc0')
    # Hardcoded into the class instance.
    sensor_type = alphanum(sensor_info.get('sensor_type', 'sensor0'))
    # The sensor name is a unique identifier for the sensor itself, in case two
    # sensors of the same type are connected at the same location.
    serial_number = sensor_info.get('serial_number', None)
    if serial_number is not None:
        serial_number = alphanum(serial_number)[:serial_length]
    else:
        serial_number = 0
        while True:
            id = format_sensor_id(location, sensor_type, serial_number)
            if id not in active_sensors:
                break
            else:
                serial_number += 1
    return format_sensor_id(location, sensor_type, serial_number)

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

