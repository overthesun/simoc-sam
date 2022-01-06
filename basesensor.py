import sys
import time
import random
import asyncio

from datetime import datetime
from abc import ABC, abstractmethod

import socketio


class BaseSensor(ABC):
    """The base class Sensors should inherit from."""
    def __init__(self):
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

    @abstractmethod
    def read_sensor_data(self):
        """Read sensor data and return them as a dict."""
        return NotImplemented

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
        await self.sio.emit('register-sensor')

    async def disconnect(self):
        """Called when the sensor disconnects from the server."""
        self.print('Server disconnected')

    async def send_data(self):
        """Called when the server requests data, runs in an endless loop."""
        self.print('Server requested data')
        # set the delay to 0 because iter_readings uses blocking time.sleep
        # and replace it with a non-blocking asyncio.sleep in the for loop
        for reading in self.sensor.iter_readings(delay=0):
            self.batch.append(reading)
            if len(self.batch) >= self.batch_size:
                if not self.sio.connected:
                    self.print('Not longer connected to a server, '
                               'stop reading/sending data')
                    return
                self.print(f'Sending a {len(self.batch)}-readings batch')
                await self.sio.emit('sensor-batch', self.batch)
                self.batch = []
            # wait for the next sensor reading
            await asyncio.sleep(self.read_delay)


class MockSensor(BaseSensor):
    """A mock server that generates random CO2/temperature/humidity data."""
    def __init__(self, *, base_co2=500, base_temp=20, base_hum=50, verbose=False):
        super().__init__()
        self.co2_ppm = base_co2
        self.temp = base_temp
        self.hum_perc = base_hum
        self.verbose = verbose

    def read_sensor_data(self):
        # add/remove random values to/from the previous ones
        self.co2_ppm += random.randint(1, 50) * random.choice([-1, 0, +1])
        self.temp += random.random() * random.choice([-1, 0, +1])
        self.hum_perc += random.randint(1, 10) * random.choice([-1, 0, +1])
        # clip values to be within range
        self.co2_ppm = float(max(0, min(self.co2_ppm, 5000)))
        self.temp = float(max(15, min(self.temp, 25)))
        self.hum_perc = float(max(0, min(self.hum_perc, 100)))
        if self.verbose:
            print(f'CO2: {self.co2_ppm:4.0f}ppm; Temperature: '
                  f'{self.temp:2.1f}°C; Humidity: {self.hum_perc:2.1f}%')
        return dict(co2_ppm=self.co2_ppm, temp=self.temp,
                    hum_perc=self.hum_perc)


if __name__ == '__main__':
    port = sys.argv[1] if len(sys.argv) > 1 else 8000
    with MockSensor(verbose=True) as sensor:
        siowrapper = SIOWrapper(sensor, verbose=True)
        asyncio.run(siowrapper.start(port))
