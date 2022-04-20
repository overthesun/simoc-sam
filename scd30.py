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

import adafruit_scd30

from basesensor import BaseSensor
from utils import start_sensor


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
        self.prior_reading_co2 = -1.1
        self.prior_reading_rel_hum = -1.1
        self.prior_readig_temp = -1.1
        self.scd.altitutde = 1061 # Height of Biosphere 2 in meters
        self.scd.forced_recalibration_reference = 257 # Reading given by Vernier when SCD is reading 0

    def read_sensor_data(self):
        """Return sensor data (CO2, temperature, humidity) as a dict."""
        if self.scd.data_available:
            co2_ppm = self.scd.CO2
            temp = self.scd.temperature  # in °C
            rel_hum = self.scd.relative_humidity
            self.prior_reading_co2 = co2_ppm
            self.prior_reading_temp = temp
            self.prior_reading_rel_hum = rel_hum
        else:
            co2_ppm = self.prior_reading_co2
            temp = self.prior_reading_temp
            rel_hum =self.prior_reading_rel_hum
        if self.verbose:
            print(f'CO2: {co2_ppm:4.0f}ppm; Temperature: ',
                  f'{temp:2.1f}°C; Humidity: {rel_hum:2.1f}%; [{self.sensor_type}]')
        return dict(co2=co2_ppm, temp=temp, rel_hum=rel_hum)


if __name__ == '__main__':
    start_sensor(SCD30)
