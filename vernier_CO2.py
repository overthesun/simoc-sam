# Implement the driver for the SCD-30 CO2/temperature/humidity sensor,
# connected through an MCP2221.

import os
import sys
import utils

from basesensor import BaseSensor
from utils import start_sensor

# Import the gdx functions from Vernier
from gdx import gdx

class VernierCO2(BaseSensor):
    sensor_type = 'Vernier CO2 Gas'
    reading_info = {
        'co2': dict(label='CO2', unit='ppm'),
        'temp': dict(label='Temperature', unit='°C'),
        'rel_hum': dict(label='Relative Humidity', unit='%'),
    }

    def __init__(self, *, name='Vernier CO2 Gas', **kwargs):
        """Initialize the sensor."""
        super().__init__(name=name, **kwargs)
        self.device = gdx.gdx() 
        self.device.open_usb()
        # To run CO2, temp, and humidity
        self.device.select_sensors([1,2,3])
        # Set polling rate to 1000 ms
        self.device.start(1000)
        self.last_reading = dict(co2=0, temp=0, rel_hum=0)

    def read_sensor_data(self):
        """Return sensor data (CO2, temperature, humidity) as a dict."""
        measurements = self.device.read()
        if measurements is not None:
            co2_ppm = measurements[0]
            temp = measurements[1]
            rel_hum = measurements[2]
            self.last_reading = dict(co2=co2_ppm, temp=temp, rel_hum=rel_hum)
        if self.verbose:
            print(f'CO2: {co2_ppm:4.0f}ppm; Temperature: ',
                  f'{temp:2.1f}°C; Humidity: {rel_hum:2.1f}%; [{self.sensor_type}]')
        return dict(co2=co2_ppm, temp=temp, rel_hum=rel_hum)


if __name__ == '__main__':
    start_sensor(VernierCO2)
