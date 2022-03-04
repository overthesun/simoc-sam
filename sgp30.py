# Implement the driver for the SCD-30 CO2/temperature/humidity sensor,
# connected through an MCP2221.

import os
import sys
import utils


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

import adafruit_sgp30

from basesensor import BaseSensor
from utils import start_sensor


def tick_conversion_ethanol(signal_output):
    """ Gets raw ticks from sensor and converts to ppm """
    # 20997 is an experimetal value in a room assumed to have "typical" concentration
    # of 14.85 ppm, although this is an unmeasured assumption.
    signal_reference = 20997
    e = 2.71828  # Euler's number
    # Equation provided by Sensirion datasheet for SGP-30
    return 0.4*e**((20997-signal_output)/512)

def tick_conversion_H2(signal_output):
    """ Gets raw ticks from sensor and converts to ppm """
    # 14296 is an experimental value in room assumed to have "typical" concentration
    # of 1.25 ppm although this is an unmeasured assumption.
    signal_reference = 14296
    e = 2.71828 # Euler's number
    # Equation provided by Sensirion datasheet for SGP-30
    return 0.5*e**((signal_reference-signal_output)/512)

class SGP30(BaseSensor):
    sensor_type = 'SGP30'
    reading_info = {
        'H2': dict(label='Hydrogen', unit='ppm'),
        'ethanol': dict(label='ethanol', unit='ppm'),
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
        # Get a raw sensor reading for hydrogen
        hydrogen_ticks = self.sensor.H2 # "Raw Ticks
        # Use Sensirion equation to convert to ppm
        hydrogen = tick_conversion_H2(hydrogen_ticks)
        # Get a raw sensor reading for ethanol
        ethanol_ticks = self.sensor.Ethanol # "Raw Ticks
        # Use Sensiron equation to convert to ppm
        ethanol = tick_conversion_ethanol(ethanol_ticks)
        # Get from the sensor the estimated values of CO2 and volatile
        # organic compounds. (Interpreted from H2 an Ethanol)
        eCO2 = self.sensor.eCO2 # ppm
        TVOC = self.sensor.TVOC # ppb
        if self.verbose:
            print(f'H2: {hydrogen:2.1f} ppm;')
            print(f'ethanol: {ethanol:2.1f} ppm;')
            print(f'eCO2: {eCO2:2.1f} ppm;')
            print(f'TVOC: {TVOC:2.1f} ppb')
        return {"H2":hydrogen, "ethanol":ethanol,
                "eCO2":eCO2,"VolatileOrganicCompounds":TVOC}

if __name__ == '__main__':
    start_sensor(SGP30)
