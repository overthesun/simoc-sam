# Implement the driver for the SCD-30 CO2/temperature/humidity sensor,
# connected through an MCP2221.

import os
import sys
import asyncio

# set these before import board
os.environ['BLINKA_MCP2221'] = '1'  # we are using MCP2221
os.environ['BLINKA_MCP2221_RESET_DELAY'] = '-1'  # avoid resetting the sensor

try:
    import busio
except RuntimeError:
    sys.exit("Failed to import 'busio', is the sensor plugged in?")

import board  # For MCP-2221
import adafruit_scd30

from basesensor import BaseSensor, SIOWrapper


class SCD30(BaseSensor):
    """Represent a SCD-30 sensors connected through a MCP2221."""
    def __init__(self, *, verbose=False):
        """Initialize the sensor."""
        super().__init__(verbose=verbose)
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
    port = sys.argv[1] if len(sys.argv) > 1 else 8000
    with SCD30(verbose=True) as sensor:
        siowrapper = SIOWrapper(sensor, verbose=True)
        asyncio.run(siowrapper.start(port))
