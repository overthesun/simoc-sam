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

import adafruit_sgp30

from basesensor import BaseSensor
from utils import start_sensor


class SGP30(BaseSensor):
    sensor_type = 'SGP30'
    reading_info = {
        'H2': dict(label='Hydrogen', unit='Raw Ticks'), # Hydrogen gas concentration in undefined units
        'ethanol': dict(label='ethanol', unit='Raw Ticks'), # Ethanol Concentration in undefined units
        'eCO2': dict(label='eCO2', unit='ppm'), # Estimated CO2 based on other common associated compounds
        'VolatileOrganicCompounds': dict(label='VOC', unit='ppb') # Total Volatile Organic Compounds
    }
    """Represent a SGP30 sensor"""
    def __init__(self, *, name='SGP30', verbose=False):
        """Initialize the sensor."""
        super().__init__(name=name, verbose=verbose)
        i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
        self.sensor = adafruit_sgp30.Adafruit_SGP30(i2c)
        self.sensor.iaq_init()
        self.sensor.set_iaq_baseline(0x8973, 0x8AEE) # Numbers from adafruit example

    def read_sensor_data(self):
        """Return sensor data (H2, Ethanol, eCO2, TVOC) as a dict."""
        hydrogen = self.sensor.H2 # "Raw Ticks
        ethanol = self.sensor.Ethanol # "Raw Ticks
        eCO2 = self.sensor.eCO2 # ppm
        TVOC = self.sensor.TVOC # ppb
        if self.verbose:
            print(f'H2: {hydrogen:4.0f} Ticks;')
            print(f'ethanol: {ethanol:2.1f} Ticks;') 
            print(f'eCO2: {eCO2:2.1f} ppm;')
            print(f'TVOC: {TVOC:2.1f} ppb')
        return {"H2":hydrogen, "ethanol":ethanol,
                "eCO2":eCO2,"VolatileOrganicCompounds":TVOC}

if __name__ == '__main__':
    start_sensor(SGP30)
