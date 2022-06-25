import asyncio
import configparser
import argparse

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
            await asyncio.gather(*[wrapper.start(port, host) for wrapper in wrappers])
    asyncio.run(start_concurrently())

def check_for_MCP2221():
    """Check to see if the MCP2221 is connected"""
    import subprocess
    return "MCP2221" in str(subprocess.check_output("lsusb"))

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
