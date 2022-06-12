import asyncio

from datetime import datetime

from basesensor import SIOWrapper

def start_sensor(sensor_cls, *pargs, **kwargs):
    args = parse_args()
    with sensor_cls(verbose=args.verbose_sensor, *pargs, **kwargs) as sensor:
        if args.no_sio:
            for reading in sensor.iter_readings(delay=args.delay):
                pass  # the sensor already prints the readings when verbose
        else:
            delay, verbose, port = args.delay, args.verbose_sio, args.port
            siowrapper = SIOWrapper(sensor, read_delay=delay, verbose=verbose)
            asyncio.run(siowrapper.start(port))
