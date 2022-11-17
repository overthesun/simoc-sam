import asyncio
import argparse
import configparser

from datetime import datetime

from .basesensor import SIOWrapper


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


def parse_args(*, read_delay=1, port=8081):
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--read-delay', default=read_delay,
                        dest='delay', metavar='DELAY', type=int,
                        help='How many seconds between readings.')
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
    for name, section in config.items():
        if not name.lower().startswith('sensor'):
            continue  # not a section about sensors
        if section['type'].lower() == sensor_type.lower():
            return dict(section)


def start_sensor(sensor_cls, *pargs, **kwargs):
    args = parse_args()
    sensor_info = get_sensor_info_from_cfg(sensor_cls.sensor_type)
    # get the name/desc from the config unless the user passed them as kwargs
    # TODO: add cmd line options for name/desc that override the cfg too
    for attr in ['name', 'description']:
        if attr not in kwargs and sensor_info and attr in sensor_info:
            kwargs[attr] = sensor_info[attr]
    with sensor_cls(verbose=args.verbose_sensor, *pargs, **kwargs) as sensor:
        if args.no_sio:
            for reading in sensor.iter_readings(delay=args.delay):
                pass  # the sensor already prints the readings when verbose
        else:
            delay, verbose, port = args.delay, args.verbose_sio, args.port
            siowrapper = SIOWrapper(sensor, read_delay=delay, verbose=verbose)
            asyncio.run(siowrapper.start(port))
