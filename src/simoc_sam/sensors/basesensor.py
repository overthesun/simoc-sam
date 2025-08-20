import time
import json
import random
import socket

from datetime import datetime
from abc import ABC, abstractmethod

import paho.mqtt.client as mqtt
from .. import config


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
        self.sensor_name = name or self.sensor_type
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

    def print(self, *args, **kwargs):
        """Print the args if self.verbose is True"""
        if self.verbose:
            print(*args, **kwargs)

    def print_reading(self, reading):
        data = []
        for name, info in self.reading_info.items():
            value = reading[name]
            if isinstance(value, float):
                value = format(value, '.1f')
            data.append(f"{info['label']}: {value}{info['unit']}")
        self.print(f"[{self.sensor_type}] {': '.join(data)}")

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
            try:
                data = self.read_sensor_data()
            except RuntimeError as err:
                self.print(f'Error reading data: {err}')
                data = None
            if not data:
                time.sleep(delay)
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


class MQTTWrapper:
    def __init__(self, sensor, *, read_delay=config.sensor_read_delay,
                 verbose=config.verbose_sensor, location=config.mqtt_topic_location):
        self.sensor = sensor
        self.read_delay = read_delay  # how long to wait between readings
        self.verbose = verbose  # toggle verbose output
        # aiomqtt still requires paho-mqtt 1.6
        # self.mqttc = mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqttc = mqttc = mqtt.Client()
        mqttc.on_connect = self.on_connect
        mqttc.on_disconnect = self.on_disconnect
        hostname = socket.gethostname()
        self.topic = f'{location}/{hostname}/{sensor.sensor_name}'
        self.log_fname = config.log_dir / f'{self.topic.replace("/", "_")}.jsonl'

    def print(self, *args, **kwargs):
        """Receive and print if self.verbose is true."""
        if self.verbose:
            print(*args, **kwargs)

    def log(self, payload):
        # TODO: implement better logging
        if not config.enable_jsonl_logging:
            return
        try:
            with open(self.log_fname, 'a') as f:
                f.write(f'{payload}\n')
        except Exception as err:
            self.print(f'Unable to write log file: {err}')

    def start(self, host, port):
        self.mqttc.loop_start()
        self.connect(host, port)

    def stop(self):
        self.mqttc.loop_stop()

    def on_connect(self, client, userdata, connect_flags,
                   reason_code, properties=None):
        if reason_code == 0:
            self.print("Connected to MQTT broker")
        else:
            self.print(f"Connection failed with code {reason_code}")

    # Callback function for disconnection
    def on_disconnect(self, client, userdata, disconnect_flags,
                      reason_code=None, properties=None):
        # with the old API the reason_code is actually assigned to
        # disconnect_flags, but we are not using it so it's ok
        self.print("Disconnected from MQTT broker")

    def connect(self, host, port):
        """Called when the sensor connects to the server."""
        try:
            self.print(f'Connecting to MQTT broker at {host}:{port}...')
            reason_code = self.mqttc.connect(host, port)
            if reason_code == 0:
                self.print(f'Connected to {host}:{port}')
            else:
                self.print(f'Connection failed with code: {reason_code}')
        except Exception as err:
            self.print(f'Connection failed with error: {err}')

    def send_data(self, n=0):
        """Called when the server requests data, runs in an endless loop."""
        self.print('Server requested data')
        # set the delay to 0 because iter_readings uses blocking time.sleep
        # and replace it with a non-blocking asyncio.sleep in the for loop
        readings = self.sensor.iter_readings(delay=self.read_delay, n=n)
        for reading in readings:
            try:
                jreading = json.dumps(reading)
                self.mqttc.publish(self.topic, payload=jreading)
                self.log(jreading)  # TODO: move this somewhere else
                self.print(reading)
            except Exception as err:
                self.print(f'No longer connected to the server ({err})...')
