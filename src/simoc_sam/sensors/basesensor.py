import time
import json
import random
import socket
import asyncio

from datetime import datetime
from abc import ABC, abstractmethod

import socketio

import paho.mqtt.client as mqtt


def random_id(length=6):
    """Return a random hexadecimal string of specified length"""
    return ''.join(random.choice('0123456789ABCDEF') for i in range(length))


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

    def __init__(self, *, name=None, id=None, description=None,
                 verbose=False):
        self.sensor_name = name
        self.sensor_id = id or random_id()
        self.sensor_desc = description
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
            'sensor_id': self.sensor_id,
            'sensor_desc': self.sensor_desc,
            'reading_info': self.reading_info,
        }

    @abstractmethod
    def read_sensor_data(self):
        """Read sensor data and return them as a dict."""
        raise NotImplementedError()

    def iter_readings(self, *, delay, n=0,
                      add_timestamp=True, add_n=True):
        """
        Yield n readings with the given delay (in seconds) between readings.

        If n is 0, yield readings forever.  If add_timestamp is true, add a
        'timestamp' field with the value returned by self.get_timestamp().
        If add_n is true, add an auto-incrementing 'n' field.

        """
        read_forever = not n
        while True:
            data = self.read_sensor_data()
            if not data:
                continue  # keep trying until we get a reading
            if add_timestamp:
                data['timestamp'] = self.get_timestamp()
            if add_n:
                data['n'] = self.reading_num
            yield data
            self.reading_num += 1
            if not read_forever:
                n -= 1
                if n == 0:
                    break
            time.sleep(delay)


class SIOWrapper:
    def __init__(self, sensor, *, read_delay=1, verbose=False):
        self.sensor = sensor
        self.read_delay = read_delay  # how long to wait between readings
        self.verbose = verbose  # toggle verbose output
        # instantiate the AsyncClient and register events
        self.sio = sio = socketio.AsyncClient()
        sio.event(self.connect)
        sio.event(self.disconnect)
        sio.on('send-data')(self.send_data)

    def print(self, *args, **kwargs):
        """Receive and print if self.verbose is true."""
        if self.verbose:
            print(*args, **kwargs)

    async def start(self, host, port):
        """Open the connection with the sio server."""
        # connect to the server and wait
        await self.sio.connect(f'http://{host}:{port}')
        await self.sio.wait()

    async def connect(self):
        """Called when the sensor connects to the server."""
        self.print('Connected to server')
        self.print('Registering sensor')
        sensor_info = self.sensor.sensor_info()
        await self.sio.emit('register-sensor', sensor_info)

    async def disconnect(self):
        """Called when the sensor disconnects from the server."""
        self.print('Server disconnected')

    async def send_data(self, n=0):
        """Called when the server requests data, runs in an endless loop."""
        self.print('Server requested data')
        # set the delay to 0 because iter_readings uses blocking time.sleep
        # and replace it with a non-blocking asyncio.sleep in the for loop
        readings = self.sensor.iter_readings(delay=0, n=n)
        for reading in readings:
            try:
                await self.sio.emit('sensor-reading', reading)
            except socketio.exceptions.BadNamespaceError:
                print('No longer connected to the server...')
                return
            # wait for the next sensor reading
            await asyncio.sleep(self.read_delay)


class MQTTWrapper:
    def __init__(self, sensor, *, host=None, port=None,
                 read_delay=1, verbose=False):
        self.sensor = sensor
        self.host = host
        self.port = port
        self.read_delay = read_delay  # how long to wait between readings
        self.verbose = verbose  # toggle verbose output
        self.mqttc = mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        mqttc.on_connect = self.on_connect
        mqttc.on_disconnect = self.on_disconnect
        self.connect()

    def print(self, *args, **kwargs):
        """Receive and print if self.verbose is true."""
        if self.verbose:
            print(*args, **kwargs)

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.print("Connected to MQTT broker")
        else:
            self.print(f"Connection failed with code {rc}")

    # Callback function for disconnection
    def on_disconnect(self, client, userdata, rc):
        self.print("Disconnected from MQTT broker")
        self.connect()

    def connect(self):
        """Called when the sensor connects to the server."""
        print(f'Connecting to MQTT broker at {self.host}:{self.port}...')
        rc = self.mqttc.connect(self.host, self.port)
        if rc == 0:
            self.print("Connected to MQTT broker")
        else:
            self.print(f"Connection failed with code {rc}")

    def send_data(self, n=0):
        """Called when the server requests data, runs in an endless loop."""
        self.print('Server requested data')
        # set the delay to 0 because iter_readings uses blocking time.sleep
        # and replace it with a non-blocking asyncio.sleep in the for loop
        hostname = socket.gethostname()
        readings = self.sensor.iter_readings(delay=0, n=n)
        for reading in readings:
            try:
                self.print(reading)
                self.mqttc.publish(f'sam/{hostname}/{self.sensor.sensor_name}',
                                   payload=json.dumps(reading), qos=0)
            except Exception as e:
                self.print(e)
                self.print('No longer connected to the server...')
                return
            # wait for the next sensor reading
            time.sleep(self.read_delay)
