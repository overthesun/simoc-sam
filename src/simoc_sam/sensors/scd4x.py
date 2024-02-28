"""Driver for the SCD-4x CO2/temperature/humidity sensor."""

import sys

from . import utils

board = utils.import_board()

try:
    import busio
except RuntimeError:
    sys.exit("Failed to import 'busio', is the sensor plugged in?")

import adafruit_scd4x

from .basesensor import BaseSensor
from .utils import start_sensor


class SCD4X(BaseSensor):
    """Represent a SCD-4X sensor."""
    sensor_type = 'SCD-41'  # could be an SCD-40 too, but we only have SCD-41s
    reading_info = {
        'co2': dict(label='CO2', unit='ppm'),
        'temp': dict(label='Temperature', unit='°C'),
        'rel_hum': dict(label='Relative Humidity', unit='%'),
    }
    def __init__(self, *, name='SCD-41', description=None, verbose=False):
        """Initialize the sensor."""
        super().__init__(name=name, description=description, verbose=verbose)
        i2c = board.I2C()
        self.scd = adafruit_scd4x.SCD4X(i2c)
        self.scd.start_periodic_measurement()

    def read_sensor_data(self):
        """Return sensor data (CO2, temperature, humidity) as a dict."""
        co2_ppm = self.scd.CO2
        temp = self.scd.temperature # in °C
        rel_hum = self.scd.relative_humidity
        if co2_ppm is None or temp is None or rel_hum is None:
            return  # sensor not ready yet
        if self.verbose:
            print(f'[{self.sensor_type}] CO2: {co2_ppm:4.0f}ppm; '
                  f'Temperature: {temp:2.1f}°C; Humidity: {rel_hum:2.1f}%')
        return dict(co2=co2_ppm, temp=temp, rel_hum=rel_hum)


if __name__ == '__main__':
    start_sensor(SCD4X)
