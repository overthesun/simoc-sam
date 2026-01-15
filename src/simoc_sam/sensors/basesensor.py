import time
import json
import random
import socket

from datetime import datetime
from abc import ABC, abstractmethod

import paho.mqtt.client as mqtt
from .. import config


def get_log_path(sensor_name):
    hostname = socket.gethostname()
    fname = f'{config.location}_{hostname}_{sensor_name}.jsonl'
    return config.log_dir / fname


class BaseSensor(ABC):
    """The base class Sensors should inherit from."""

    def __init_subclass__(cls, **kwargs):
        """Set sensor name, type, and reading info."""
        from . import utils  # import here to avoid circular import
        super().__init_subclass__(**kwargs)
        # subclasses can specify a custom sensor name
        if not hasattr(cls, 'name'):
            cls.name = cls.__name__.lower()
        if cls.name in utils.SENSOR_DATA:
            sensor_data = utils.SENSOR_DATA[cls.name]
            cls.type = sensor_data.name
            cls.reading_info = sensor_data.data
        else:
            # type and reading_info must be manually set if not in sensors.toml
            if not (hasattr(cls, 'type') and hasattr(cls, 'reading_info')):
                raise ValueError(f'Sensor {cls.name!r} must be added to sensors.toml '
                                 f'or type and reading_info must be set.')
        # auto-generate (sub)class docstring if not already set
        if cls.__doc__ is None:
            cls.__doc__ = f'Represent a {cls.type} sensor.'

    def __init__(self, *, description=None, verbose=False):
        """Initialize the sensor."""
        hostname = socket.gethostname()
        self.id = f'{config.location}.{hostname}.{self.name}'
        self.description = description
        self.verbose = verbose
        # the total number of values read through iter_readings
        self.reading_num = 0
        self.log_path = get_log_path(self.sensor_name)
        if config.enable_jsonl_logging:
            config.log_dir.mkdir(exist_ok=True)  # ensure the log dir exists

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
            'sensor_type': self.type,
            'sensor_name': self.name,
            'sensor_id': self.id,
            'sensor_desc': self.description,
            'reading_info': self.reading_info,
        }

    def print(self, *args, **kwargs):
        """Print the args if self.verbose is True"""
        if self.verbose:
            print(*args, **kwargs)

    def log(self, payload):
        try:
            with open(self.log_path, 'a') as f:
                f.write(f'{payload}\n')
        except Exception as err:
            self.print(f'Unable to write log file: {err}')

    def print_reading(self, reading):
        data = []
        for name, info in self.reading_info.items():
            if name not in reading:
                continue
            value = reading[name]
            if isinstance(value, float):
                value = format(value, '.1f')
            data.append(f"{info['label']}: {value}{info['unit']}")
        self.print(f"[{self.type}] {'; '.join(data)}")

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
            if config.enable_jsonl_logging:
                self.log(json.dumps(data))
            yield data
            self.reading_num += 1
            if not read_forever:
                n -= 1
                if n == 0:
                    break
            time.sleep(delay)


class MQTTWrapper:
    def __init__(self, sensor, *, read_delay=config.sensor_read_delay,
                 verbose=config.verbose_sensor, location=config.location,
                 secure=config.mqtt_secure, certs_dir=config.mqtt_certs_dir):
        self.sensor = sensor
        self.read_delay = read_delay  # how long to wait between readings
        self.verbose = verbose  # toggle verbose output
        # aiomqtt still requires paho-mqtt 1.6
        # self.mqttc = mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqttc = mqttc = mqtt.Client()
        if secure:
            self.print("Using secure MQTT connection")
            self.mqttc.tls_set(ca_certs=str(certs_dir / 'ca.crt'),
                               certfile=str(certs_dir / 'client.crt'),
                               keyfile=str(certs_dir / 'client.key'))
        mqttc.on_connect = self.on_connect
        mqttc.on_disconnect = self.on_disconnect
        hostname = socket.gethostname()
        self.topic = f'{location}/{hostname}/{sensor.name}'

    def print(self, *args, **kwargs):
        """Receive and print if self.verbose is true."""
        if self.verbose:
            print(*args, **kwargs)

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
                self.print(reading)
            except Exception as err:
                self.print(f'No longer connected to the server ({err})...')
