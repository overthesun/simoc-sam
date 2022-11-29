"""Driver for the BME688 Temp/Humidity/Pressure/Gas Resistance sensor."""

import os
import sys

from . import utils


if utils.check_for_MCP2221():
    # We don't want to import board again if MCP2221 is already running from
    # another script
    if 'BLINKA_MCP2221' not in os.environ:
        # set these before import board
        os.environ['BLINKA_MCP2221'] = '1'  # we are using MCP2221
        os.environ['BLINKA_MCP2221_RESET_DELAY'] = '-1'  # avoid resetting the sensor
        import board
else:
    import board

try:
    import busio
except RuntimeError:
    sys.exit("Failed to import 'busio', is the sensor plugged in?")

import adafruit_bme680

from .basesensor import BaseSensor
from .utils import start_sensor


class BME688(BaseSensor):
    """Represent a BME688 sensor"""
    sensor_type = 'BME688'
    reading_info = {
        'temp': dict(label='Temperature', unit='°C'),
        'rel_hum': dict(label='Relative Humidity', unit='%'),
        'gas_resistance' : dict(label='Gas Resistance', unit='Ohms'),
        'altitude': dict (label='Altitude', unit='m'),
        'pressure': dict(label='Pressure', unit='hPa'),
    }
    def __init__(self, *, name='BME688', **kwargs):
        """Initialize the sensor."""
        super().__init__(name=name, **kwargs)
        i2c = board.I2C()
        self.sensor = adafruit_bme680.Adafruit_BME680_I2C(i2c, debug=False)

    def read_sensor_data(self):
        """Return sensor data as a dict."""
        temperature = self.sensor.temperature  # °C
        humidity = self.sensor.relative_humidity  # %
        pressure = self.sensor.pressure  # hPa
        altitude = self.sensor.altitude  # m
        gas = self.sensor.gas  # Ohms
        if self.verbose:
            print(f'Pressure: {pressure:4.1f} hPa; Temperature: '
                  f'{temperature:2.1f}°C; Humidity: {humidity:2.1f}%; '
                  f'Altidude: {altitude:2.1f} m; '
                  f'Gas Resistance: {gas:2.1f} Ohms; [{self.sensor_type}]')
        return {"temp": temperature, "rel_hum": humidity, "gas_resistance": gas,
                "altitude": altitude, "pressure": pressure}

if __name__ == '__main__':
    start_sensor(BME688)
