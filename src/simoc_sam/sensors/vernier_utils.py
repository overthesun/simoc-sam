import asyncio

from contextlib import ExitStack

from .basesensor import SIOWrapper
from .utils import parse_args

def start_sensors(sensor_classes):
    """Initialize multiple Vernier sensors."""
    args = parse_args()
    async def start_concurrently():
        with ExitStack() as stack:
            v = args.verbose_sensor
            sensors = []
            for (sensor_cls, device, kwargs) in sensor_classes:
                sensors.append(stack.enter_context(sensor_cls(verbose=v, device=device, **kwargs)))
            delay, verbose, port = args.delay, args.verbose_sio, args.port
            wrappers = [SIOWrapper(sensor, read_delay=delay, verbose=verbose)
                        for sensor in sensors]
            await asyncio.gather(*[wrapper.start(port) for wrapper in wrappers])
    asyncio.run(start_concurrently())

class gdx_lite:
    """Provide the same methods/syntax as gdx for a single device

    gdx is a library (maintained by Vernier) is a wrapper for the GoDirect
    library which is designed to work specifically with Vernier sensors.
    However, it is intended that a single instance of gdx will initialize and
    read from all connected GoDirect sensors, whereas SIMOC-SAM's `basesensor`
    class is intended that sensors are read independently. Original gdx repo:
    (https://github.com/VernierST/godirect-examples/tree/main/python/gdx)

    This class (gdx_lite) was written based on the gdx to provide similar
    functionality while allowing for multiple instances. To accomplish this,
    GoDirect must be initialized and read externally, and devices passed to
    this class.
    """

    device = None         # A usb-connected Vernier device (e.g. GDX-CO2)
    enabled_sensors = []  # A list of active sensors (e.g. [1, 2, 3])

    def __init__(self, device):
        """Initialize with a pointer to the GoDirect device."""
        self.device = device

    def select_sensors(self, sensors=[]):
        """Choose which sensors will be read from.

        Each Vernier sensor actually includes multiple sensors, e.g. the
        VernierCO2 sensor takes readings for CO2, temperature and relative
        humidity.
        """
        self.enabled_sensors = sensors
        self.device.enable_sensors(self.enabled_sensors)

    def start(self, period=1000):
        """Begin reading data with (period) ms between readings."""
        self.device.start(period=period)

    def read(self):
        """Take single point readings from enabled sensors."""
        retvalues = []
        if self.device.read():
            for i, sensor in self.device.sensors.items():
                retvalues.append(sensor.values[-1])
        return retvalues

    def close(self):
        """Disconnect the device from GoDirect."""
        self.device.close()
