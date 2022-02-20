# Implement the driver for the SCD-30 CO2/temperature/humidity sensor,
# connected through an MCP2221.

import os
import sys
import utils


if utils.check_for_MCP2221():
    # set these before import board
    os.environ['BLINKA_MCP2221'] = '1'  # we are using MCP2221
    os.environ['BLINKA_MCP2221_RESET_DELAY'] = '-1'  # avoid resetting the sensor

import board

try:
    import busio
except RuntimeError:
    sys.exit("Failed to import 'busio', is the sensor plugged in?")

import adafruit_bme680

from basesensor import BaseSensor
from utils import start_sensor

class BME688(BaseSensor):
    sensor_type = 'BME688'
    reading_info = {
        'temp': dict(label='Temperature', unit='°C'),
        'rel_hum': dict(label='Relative Humidity', unit='%'),
        'gasResistance' : dict(label='Gas Resistance', unit='Ohms'),
        'altitude': dict (label='altitude', unit='m'),
        'pressure': dict(label='Pressure', unit="hPa"),
    }
    """Represent a BME688 sensor"""
    def __init__(self, *, name='BME688', verbose=False):
        """Initialize the sensor."""
        super().__init__(name=name, verbose=verbose)
        i2c= board.I2C()
        self.sensor = adafruit_bme680.Adafruit_BME680_I2C(i2c, debug=False)

    def read_sensor_data(self):
        """Return sensor data (H2, Ethanol, eCO2, TVOC) as a dict."""
        temperature = self.sensor.temperature # "*C"
        humidity = self.sensor.relative_humidity # "%"
        pressure = self.sensor.pressure # "hPa"
        altitude = self.sensor.altitude # "m"
        gas = self.sensor.gas #"Ohms"
        if self.verbose:
            print(f'Pressure: {pressure:4.1f} hPa; Temperature: '
                  f'{temperature:2.1f}°C; Humidity: {humidity:2.1f}% '
                  f'Altidude: {altitude:2.1f} m '
                  f'Gas Resistance: {gas:2.1f} Ohms ')
        return {"temp":temperature, "rel_hum":humidity,
                "gasResistance":gas,"altitude":altitude, "pressure":pressure}

if __name__ == '__main__':
    start_sensor(BME688)
