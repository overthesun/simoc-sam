"""Driver for the SGP-30 H2/Ethanol sensor."""

import os
import sys

from . import utils

board = utils.import_board()

try:
    import busio
except RuntimeError:
    sys.exit("Failed to import 'busio'.  Is the sensor plugged in?")

import adafruit_sgp30

from .basesensor import BaseSensor
from .utils import start_sensor


def tick_conversion_ethanol(signal_output):
    """Get raw ticks from sensor and converts to ppm."""
    # 20997 is an experimetal value in a room assumed to have "typical" concentration
    # of 14.85 ppm, although this is an unmeasured assumption.
    signal_reference = 20997
    e = 2.71828   # Euler's number
    # Equation provided by Sensirion datasheet for SGP-30
    return 0.4 * (e**((20997-signal_output)/512))

def tick_conversion_H2(signal_output):
    """Get raw ticks from sensor and converts to ppm."""
    # 14296 is an experimental value in room assumed to have "typical" concentration
    # of 1.25 ppm although this is an unmeasured assumption.
    signal_reference = 14296
    e = 2.71828  # Euler's number
    # Equation provided by Sensirion datasheet for SGP-30
    return 0.5 * (e**((signal_reference-signal_output)/512))


class SGP30(BaseSensor):
    """Represent a SGP30 sensor."""
    sensor_type = 'SGP30'
    reading_info = {
        'H2': dict(label='Hydrogen', unit='ppm'),
        'ethanol': dict(label='ethanol', unit='ppm'),
        # Estimated CO2 based on other common associated compounds
        'eCO2': dict(label='eCO2', unit='ppm'),
        # Total Volatile Organic Compounds
        'VolatileOrganicCompounds': dict(label='VOC', unit='ppb')
    }
    def __init__(self, *, name='SGP30', verbose=False):
        """Initialize the sensor."""
        super().__init__(name=name, verbose=verbose)
        i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
        self.sensor = adafruit_sgp30.Adafruit_SGP30(i2c)
        self.sensor.iaq_init()
        self.sensor.set_iaq_baseline(0x8973, 0x8AEE)  # Numbers from adafruit example

    def read_sensor_data(self):
        """Return sensor data (H2, Ethanol, eCO2, TVOC) as a dict."""
        # Get a raw sensor reading for hydrogen
        hydrogen_ticks = self.sensor.H2  # Raw Ticks
        # Use Sensirion equation to convert to ppm
        hydrogen = tick_conversion_H2(hydrogen_ticks)
        # Get a raw sensor reading for ethanol
        ethanol_ticks = self.sensor.Ethanol  # Raw Ticks
        # Use Sensiron equation to convert to ppm
        ethanol = tick_conversion_ethanol(ethanol_ticks)
        # Get from the sensor the estimated values of CO2 and volatile
        # organic compounds. (Interpreted from H2 an Ethanol)
        eCO2 = self.sensor.eCO2  # ppm
        TVOC = self.sensor.TVOC  # ppb
        if self.verbose:
                print(f'[{self.sensor_type}] '
                      f'H2: {hydrogen:2.1f} ppm;',
                      f'ethanol: {ethanol:2.1f} ppm;',
                      f'eCO2: {eCO2:2.1f} ppm;',
                      f'TVOC: {TVOC:2.1f} ppb')
        return {"H2": hydrogen, "ethanol": ethanol,
                "eCO2": eCO2, "VolatileOrganicCompounds": TVOC}

if __name__ == '__main__':
    start_sensor(SGP30)
