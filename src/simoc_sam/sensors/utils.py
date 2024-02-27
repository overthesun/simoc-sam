import os
import asyncio
import argparse
import subprocess

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


def check_for_MCP2221():
    """Check to see if the MCP2221 is connected"""
    return b'MCP2221' in subprocess.check_output("lsusb")


def get_sioserver_addr():
    addr = os.environ.get('SIOSERVER_ADDR', 'localhost:8081')
    host, port = addr.split(':')
    return host, port


def get_addr_argparser():
    SIO_HOST, SIO_PORT = get_sioserver_addr()
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default=SIO_HOST,
                        help='The hostname of the sioserver.')
    parser.add_argument('--port', default=SIO_PORT, type=int,
                        help='The port used by the sioserver.')
    return parser


def parse_args(*, read_delay=1, port=8081):
    parser = get_addr_argparser()
    parser.add_argument('-d', '--read-delay', default=read_delay,
                        dest='delay', metavar='DELAY', type=float,
                        help='How many seconds between readings.')
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
    if not args.no_sio and args.port is None:
        args.port = port
    return args


def start_sensor(sensor_cls, *pargs, **kwargs):
    args = parse_args()
    # TODO: add cmd line options for name/desc
    with sensor_cls(verbose=args.verbose_sensor, *pargs, **kwargs) as sensor:
        if args.no_sio:
            for reading in sensor.iter_readings(delay=args.delay):
                pass  # the sensor already prints the readings when verbose
        else:
            delay, verbose = args.delay, args.verbose_sio
            host, port = args.host, args.port
            siowrapper = SIOWrapper(sensor, read_delay=delay, verbose=verbose)
            asyncio.run(siowrapper.start(host, port))
