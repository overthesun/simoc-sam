import time
import asyncio

from datetime import datetime
from abc import ABC, abstractmethod

import socketio


class BaseSensor(ABC):
    """The base class Sensors should inherit from."""
    @property
    @abstractmethod
    def sensor_type(self):
        """The sensor type (e.g. model name)."""
        # override this with a regular class attr in the subclasses
        raise NotImplementedError()

    @property
    @abstractmethod
    def reading_info(self):
        """Information about the values returned by read_sensor_data."""
        # override this with a regular class attr in the subclasses
        raise NotImplementedError()

    def __init__(self, *, name=None, verbose=False):
        self.sensor_name = name
        self.verbose = verbose
        # the total number of values read through iter_readings
        self.reading_num = 0

    def __enter__(self):
        # use this to initialize the sensor and return self
        return self

    def __exit__(self, type, value, traceback):
        # use this to clean up
        return False  # let exceptions propagate

    def get_timestamp(self):
        """Return the current timestamp as a string."""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')

    def sensor_info(self):
        """Return information about the sensor and the value it returns."""
        return {
            'sensor_type': self.sensor_type,
            'sensor_name': self.sensor_name,
            'reading_info': self.reading_info,
        }

    @abstractmethod
    def read_sensor_data(self):
        """Read sensor data and return them as a dict."""
        raise NotImplementedError()

    def iter_readings(self, *, delay, n=0,
                      add_timestamp=True, add_stepnum=True):
        """
        Yield n readings with the given delay (in seconds) between readings.

        If n is 0, yield readings forever.  If add_timestamp is true, add a
        'timestamp' field with the value returned by self.get_timestamp().
        If add_stepnum is true, add an auto-incrementing 'step_num' field.

        """
        read_forever = not n
        while True:
            data = self.read_sensor_data()
            if not data:
                continue  # keep trying until we get a reading
            if add_timestamp:
                data['timestamp'] = self.get_timestamp()
            if add_stepnum:
                data['step_num'] = self.reading_num
            yield data
            self.reading_num += 1
            if not read_forever:
                n -= 1
                if n == 0:
                    break
            time.sleep(delay)


class SIOWrapper:

    def __init__(self, sensor, *, read_delay=1, batch_size=10, verbose=False):
        self.sensor = sensor
        self.read_delay = read_delay  # how long to wait between readings
        self.batch_size = batch_size  # how many readings in a batch
        self.verbose = verbose  # toggle verbose output
        # the batch is an instance attribute so that readings are not lost
        # if send_data() is interrupted and then restarted
        self.batch = []
        # instantiate the AsyncClient and register events
        self.sio = sio = socketio.AsyncClient()
        self.sensor_ns = socketio.AsyncClientNamespace('/sensor')
        self.sio.register_namespace(self.sensor_ns)
        #self.sio.sleep(1.0)
        sio.event(self.connect)
        sio.event(self.disconnect)
        sio.on('send-data')(self.send_data)

    def print(self, *args, **kwargs):
        """Receive and print if self.verbose is true."""
        if self.verbose:
            print(*args, **kwargs)

    async def start(self, port):
        """Open the connection with the sio server."""
        # connect to the server and wait
        await self.sio.connect(f'http://localhost:{port}')
        await self.sio.wait()

    async def connect(self):
        """Called when the sensor connects to the server."""
        self.print('Connected to server')
        self.print('Registering sensor')
        sensor_info = self.sensor.sensor_info()
        await self.sio.emit('register-sensor', sensor_info, namespace='/sensor')

    async def disconnect(self):
        """Called when the sensor disconnects from the server."""
        self.print('Server disconnected')

    async def send_data(self, n=0):
        """Called when the server requests data, runs in an endless loop."""
        self.print('Server requested data')
        # set the delay to 0 because iter_readings uses blocking time.sleep
        # and replace it with a non-blocking asyncio.sleep in the for loop
        for reading in self.sensor.iter_readings(delay=0, n=n):
            self.batch.append(reading)
            if len(self.batch) >= self.batch_size:
                if not self.sio.connected:
                    self.print('No longer connected to a server, '
                               'stop reading/sending data')
                    return
                self.print(f'Sending a {len(self.batch)}-readings batch')
                await self.sio.emit('sensor-batch', self.batch, namespace='/sensor')
                self.batch = []
            # wait for the next sensor reading
            await asyncio.sleep(self.read_delay)
