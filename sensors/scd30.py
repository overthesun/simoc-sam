# Implement the driver for the SCD-30 CO2/temperature/humidity sensor,
# connected through an MCP2221.

import os
import sys

# set these before import board
os.environ['BLINKA_MCP2221'] = '1'  # we are using MCP2221
os.environ['BLINKA_MCP2221_RESET_DELAY'] = '-1'  # avoid resetting the sensor

try:
    import busio
except RuntimeError:
    sys.exit("Failed to import 'busio', is the sensor plugged in?")

import board  # For MCP-2221
import adafruit_scd30

from basesensor import BaseSensor
from sensor_utils import start_sensor


class SCD30(BaseSensor):
    sensor_type = 'SCD-30'
    reading_info = {
        'co2': dict(label='CO2', unit='ppm'),
        'temp': dict(label='Temperature', unit='°C'),
        'rel_hum': dict(label='Relative Humidity', unit='%'),
    }
    """Represent a SCD-30 sensors connected through a MCP2221."""
    def __init__(self, *, name='SCD-30', verbose=False):
        """Initialize the sensor."""
        super().__init__(name=name, verbose=verbose)
        i2c = busio.I2C(board.SCL, board.SDA, frequency=50000)
        self.scd = adafruit_scd30.SCD30(i2c)

    def read_sensor_data(self):
        """Return sensor data (CO2, temperature, humidity) as a dict."""
        co2_ppm = self.scd.CO2
        temp = self.scd.temperature  # in °C
        rel_hum = self.scd.relative_humidity
        if self.verbose:
            print(f'CO2: {co2_ppm:4.0f}ppm; Temperature: '
                  f'{temp:2.1f}°C; Humidity: {rel_hum:2.1f}%')
        return dict(co2=co2_ppm, temp=temp, rel_hum=rel_hum)


if __name__ == '__main__':
    start_sensor(SCD30)
