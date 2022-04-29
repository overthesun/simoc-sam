# Implement the driver for the Vernier O2 Sensor, also measures temperature

import os
import sys
import utils

from basesensor import BaseSensor
from utils import start_sensor

# Import the gdx functions from Vernier
from gdx import gdx

class VernierO2(BaseSensor):
    sensor_type = 'Vernier O2 Gas'
    reading_info = {
        'o2': dict(label='O2', unit='%'),
        'temp': dict(label='Temperature', unit='°C'),
    }

    def __init__(self, *, name='Vernier O2 Gas', **kwargs):
        """Initialize the sensor."""
        super().__init__(name=name, **kwargs)
        self.device = gdx.gdx() 
        self.device.open_usb()
        # To run O2, temp, and humidity
        self.device.select_sensors([1,2,3])
        # Set polling rate to 1000 ms
        self.device.start(1000)
        self.last_reading = dict(o2=0, temp=0)

    def read_sensor_data(self):
        """Return sensor data (O2, temperature) as a dict."""
        measurements = self.device.read()
        if measurements is not None:
            o2_percent = measurements[0]
            # O2 - rTC would be measurements[1] but it is only recommended when
            # starting at room temperature with wild temp fluctuations expected
            temp = measurements[2]
            self.last_reading = dict(o2=o2_percent, temp=temp)
        if self.verbose:
            print(f'O2: {o2_percent:2.2f}%; Temperature: ',
                  f'{temp:2.1f}°C; [{self.sensor_type}]')
        return dict(o2=o2_percent, temp=temp)


if __name__ == '__main__':
    start_sensor(VernierO2)
